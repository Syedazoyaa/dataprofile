"""Tests for behavioural segmentation, filtering and population comparison."""
from fastapi.testclient import TestClient

from app.generator import generate_profiles
from app.main import app
from app.schemas import ProfileFilter
from app.comparison import compare_populations
from app.filtering import apply_filters, validate_filters
from app.segmentation import SEGMENT_DEFINITIONS, classify_profile, summarize_segments

client = TestClient(app)
SEG_IDS = {d["segment_id"] for d in SEGMENT_DEFINITIONS}


def test_every_profile_classified_deterministically():
    pros = generate_profiles(200, 6001)
    first = [classify_profile(p)["segment_id"] for p in pros]
    second = [classify_profile(p)["segment_id"] for p in generate_profiles(200, 6001)]
    assert first == second
    assert all(s in SEG_IDS for s in first)
    assert len(set(first)) >= 3, "segments should show variation, not collapse to one"


def test_segment_counts_and_percentages():
    pros = generate_profiles(300, 6002)
    summary = summarize_segments(pros)
    assert summary["total_profiles"] == 300
    assert sum(s["profile_count"] for s in summary["segments"]) == 300
    assert abs(sum(s["percentage"] for s in summary["segments"]) - 100.0) < 0.05
    for seg in summary["segments"]:
        assert {"segment_id", "segment_name", "description", "profile_count",
                "percentage", "defining_characteristics"} <= set(seg)


def test_segment_assignment_is_scoring_not_random():
    pros = generate_profiles(400, 6003)
    researchers = [p for p in pros
                   if classify_profile(p)["segment_id"] == "deliberate_researcher"]
    assert researchers
    # Deliberate researchers should skew toward High research behaviour.
    high = sum(1 for p in researchers if p["research_before_purchase"] == "High")
    assert high / len(researchers) > 0.4


def test_filter_single_and_multiple():
    pros = generate_profiles(400, 6004)
    by_age = apply_filters(pros, ProfileFilter(age_min=25, age_max=35))
    assert by_age and all(25 <= p["age"] <= 35 for p in by_age)
    combo = apply_filters(pros, ProfileFilter(age_min=25, age_max=35, country="India",
                                              price_sensitivity="Highly price sensitive"))
    assert all(25 <= p["age"] <= 35 and p["country"] == "India" for p in combo)
    assert len(combo) <= len(by_age)


def test_filter_behavioural_and_segment():
    pros = generate_profiles(400, 6005)
    seg = classify_profile(pros[0])["segment_id"]
    matched = apply_filters(pros, ProfileFilter(behavioural_segment=seg))
    assert matched and all(classify_profile(p)["segment_id"] == seg for p in matched)
    brand = apply_filters(pros, ProfileFilter(brand_loyalty="High"))
    assert brand and all(p["brand_loyalty"] == "High" for p in brand)


def test_filter_empty_and_invalid():
    pros = generate_profiles(200, 6006)
    empty = apply_filters(pros, ProfileFilter(age_min=70, age_max=78,
                                              career_level="Early"))
    assert empty == [] or all(p["career_level"] == "Early" for p in empty)
    impossible = apply_filters(pros, ProfileFilter(age_min=70, age_max=71,
                                                   employment_status="School student"))
    assert impossible == []
    for bad in ({"gender": "X"}, {"behavioural_segment": "nope"},
                {"research_intensity": "Extreme"}, {"country": "Atlantis"}):
        try:
            validate_filters(ProfileFilter(**bad), supported_countries=("India",))
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_combined_product_filter_example():
    pros = generate_profiles(600, 6007, country="India")
    seg = "deliberate_researcher"
    matched = apply_filters(pros, ProfileFilter(age_min=25, age_max=35, country="India",
                                                price_sensitivity="Highly price sensitive",
                                                behavioural_segment=seg))
    for p in matched:
        assert 25 <= p["age"] <= 35 and p["country"] == "India"
        assert p["price_sensitivity"] == "Highly price sensitive"
        assert classify_profile(p)["segment_id"] == seg


def test_compare_two_populations():
    a = generate_profiles(200, 6008, country="India")
    b = generate_profiles(300, 6009, country="Saudi Arabia")
    result = compare_populations({"India": a, "Saudi Arabia": b})
    assert result["populations"] == {"India": {"n": 200}, "Saudi Arabia": {"n": 300}}
    for dim in result["demographics"] + result["behavioural"]:
        for label in ("India", "Saudi Arabia"):
            pop = dim["populations"][label]
            assert sum(pop["counts"].values()) == pop["n"]
            assert abs(sum(pop["percentages"].values()) - 100.0) < 0.05
    seg = result["segments"]
    assert set(seg["categories"]) == SEG_IDS
    for label in ("India", "Saudi Arabia"):
        assert sum(seg["populations"][label]["counts"].values()) == seg["populations"][label]["n"]


def test_compare_three_populations_different_sizes():
    pops = {c: generate_profiles(n, 6010, country=c)
            for c, n in (("India", 120), ("Japan", 80), ("Brazil", 200))}
    result = compare_populations(pops)
    assert set(result["populations"]) == {"India", "Japan", "Brazil"}
    assert result["segments"]["populations"]["Japan"]["n"] == 80


def test_analytics_endpoints():
    r = client.post("/segments", json={"generation": {"count": 30, "seed": 61}})
    assert r.status_code == 200
    body = r.json()
    assert body["total_profiles"] == 30
    assert all("behavioural_segment" in p for p in body["profiles"])

    r = client.post("/filter", json={"generation": {"count": 100, "seed": 62},
                                     "filters": {"age_min": 25, "age_max": 35}})
    assert r.status_code == 200
    assert r.json()["matched_count"] <= 100

    r = client.post("/filter", json={"generation": {"count": 50, "seed": 62},
                                     "filters": {"gender": "X"}})
    assert r.status_code == 422

    r = client.post("/compare", json={"populations": [
        {"label": "A", "generation": {"count": 40, "seed": 63, "country": "India"}},
        {"label": "B", "generation": {"count": 40, "seed": 63, "country": "Japan"}}]})
    assert r.status_code == 200
    assert set(r.json()["populations"]) == {"A", "B"}

    r = client.post("/compare", json={"populations": [
        {"label": "A", "generation": {"count": 10, "seed": 1}}]})
    assert r.status_code == 422

    r = client.get("/segments/definitions")
    assert r.status_code == 200 and len(r.json()["segments"]) == 5


def test_compare_requires_exactly_two_distinct_countries():
    two = {"populations": [
        {"label": "A", "generation": {"count": 20, "seed": 71, "country": "Saudi Arabia"}},
        {"label": "B", "generation": {"count": 20, "seed": 71, "country": "United States"}}]}
    r = client.post("/compare", json=two)
    assert r.status_code == 200
    assert set(r.json()["populations"]) == {"A", "B"}
    # 0 populations.
    assert client.post("/compare", json={"populations": []}).status_code == 422
    # 1 population.
    assert client.post("/compare", json={"populations": two["populations"][:1]}).status_code == 422
    # 3 populations.
    three = {"populations": two["populations"] + [
        {"label": "C", "generation": {"count": 20, "seed": 71, "country": "Japan"}}]}
    assert client.post("/compare", json=three).status_code == 422
    # Duplicate countries.
    dup = {"populations": [
        {"label": "A", "generation": {"count": 20, "seed": 71, "country": "India"}},
        {"label": "B", "generation": {"count": 20, "seed": 72, "country": "IN"}}]}
    assert client.post("/compare", json=dup).status_code == 422
    # Missing country (global side).
    nogeo = {"populations": [
        {"label": "A", "generation": {"count": 20, "seed": 71, "country": "India"}},
        {"label": "B", "generation": {"count": 20, "seed": 71}}]}
    assert client.post("/compare", json=nogeo).status_code == 422
    # Unknown country.
    bad = {"populations": [
        {"label": "A", "generation": {"count": 20, "seed": 71, "country": "India"}},
        {"label": "B", "generation": {"count": 20, "seed": 71, "country": "Atlantis"}}]}
    assert client.post("/compare", json=bad).status_code == 422
