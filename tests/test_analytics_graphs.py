"""Analytics service tests: structure, values, currency honesty, quality, edge cases."""
from fastapi.testclient import TestClient

from app.analytics import compute_analytics, spearman
from app.generator import generate_profiles
from app.main import app
from app.schemas import ProfileFilter
from app.filtering import apply_filters
from app.comparison import compare_populations

client = TestClient(app)


def _labels(dist):
    return [entry["label"] for entry in dist]


def test_overview_metrics_are_real():
    pros = generate_profiles(200, 8001, country="India")
    overview = compute_analytics(pros)["overview"]
    assert overview["total_profiles"] == 200
    assert overview["min_age"] >= 16 and overview["max_age"] <= 78
    assert overview["min_age"] <= overview["median_age"] <= overview["max_age"]
    assert abs(overview["average_age"] - sum(p["age"] for p in pros) / 200) < 0.01
    assert overview["income_currency"] == "INR"
    assert overview["median_income"] == __import__("statistics").median(
        sorted(p["annual_income"] for p in pros))
    assert overview["country_count"] == 1 and overview["city_count"] == 3
    assert 0 < overview["employment_rate"] <= 1
    assert overview["dominant_segment"] and overview["dominant_education"]


def test_distribution_structure_and_totals():
    analytics = compute_analytics(generate_profiles(150, 8002))
    for dist in (analytics["demographics"]["gender_distribution"],
                 analytics["demographics"]["education_distribution"],
                 analytics["demographics"]["employment_distribution"],
                 analytics["demographics"]["career_level_distribution"],
                 analytics["financial"]["income_bands"]):
        assert all({"label", "count"} <= set(e) for e in dist)
        assert sum(e["count"] for e in dist) == 150
    assert _labels(analytics["demographics"]["age_distribution"]) == ["16-24", "25-34", "35-49", "50-64", "65+"]
    assert sum(e["count"] for e in analytics["demographics"]["age_distribution"]) == 150
    assert sum(e["count"] for e in analytics["demographics"]["experience_distribution"]) == 150


def test_multi_currency_income_never_pooled():
    pros = (generate_profiles(80, 8003, country="India")
            + generate_profiles(80, 8004, country="United States"))
    financial = compute_analytics(pros)["financial"]
    assert set(financial["income_by_currency"]) == {"INR", "USD"}
    assert financial["income_by_currency"]["INR"]["n"] == 80
    # income_vs_expenses is anchored to one currency, explicitly labelled.
    assert financial["income_vs_expenses"]["currency"] in ("INR", "USD")
    assert "never pooled across currencies" in financial["note"]
    assert sum(e["count"] for e in financial["income_bands"]) == 160


def test_behavioural_and_segment_analytics_reuse_segmentation():
    from app.segmentation import summarize_segments
    pros = generate_profiles(200, 8005)
    analytics = compute_analytics(pros)
    assert set(analytics["behavioural"]) >= {"research_before_purchase",
                                             "price_sensitivity", "purchase_intent",
                                             "brand_loyalty", "decision_speed"}
    assert analytics["behavioural"]["purchase_intent"]
    assert analytics["segments"] == summarize_segments(pros)
    assert sum(s["profile_count"] for s in analytics["segments"]["segments"]) == 200


def test_relationships_have_methodology_and_no_causality():
    analytics = compute_analytics(generate_profiles(300, 8006))
    rel = analytics["relationships"]
    for name in ("age_vs_income", "experience_vs_income", "research_vs_purchase_intent",
                 "price_vs_purchase_intent", "brand_vs_purchase_intent",
                 "comparison_vs_decision_speed"):
        entry = rel[name]
        assert entry["method"] == "spearman"
        assert entry["sample_size"] > 0
        assert all({"x", "y"} <= set(pt) for pt in entry["points"])
        assert len(entry["points"]) <= 500
        if entry["correlation"] is not None:
            assert -1.0 <= entry["correlation"] <= 1.0
    assert rel["age_vs_income"]["correlation"] is not None
    assert rel["age_vs_income"]["correlation"] > 0  # experience/income grows with age by design
    assert rel["education_vs_research"] and rel["career_vs_purchase_intent"]
    assert "not causal" in analytics["note"]


def test_expense_ratio_bins_cover_all_eligible():
    base = {"profile_id": "t", "age": 30, "gender": "Female", "country": "India",
            "city": "Mumbai", "education_level": "Undergraduate",
            "employment_status": "Employed full-time", "career_level": "Mid-level",
            "annual_income": 120000, "monthly_income": 10000, "monthly_savings": 1000,
            "primary_language": "Hindi", "preferred_language": "Hindi",
            "life_stage": "Established Professional", "income_band": "Modest",
            "currency": "INR", "research_before_purchase": "Moderate",
            "comparison_behavior": "Moderate", "price_sensitivity": "Price conscious",
            "brand_loyalty": "Moderate", "decision_speed": "Moderate",
            "planning_behavior": "Moderate", "impulse_buying": "Moderate",
            "discount_sensitivity": "Moderate", "information_seeking": "Moderate",
            "financial_risk_tolerance": "Moderate", "years_of_experience": 5}
    pros = []
    for i, expenses in enumerate([2000, 5000, 7000, 9000, 9500]):
        p = dict(base)
        p["profile_id"] = "t-%d" % i
        p["monthly_expenses"] = expenses
        p["monthly_savings"] = 10000 - expenses
        pros.append(p)
    dist = compute_analytics(pros)["financial"]["expense_to_income_ratio"]
    assert {e["label"]: e["count"] for e in dist} == {
        "<40%": 1, "40-60%": 1, "60-80%": 1, ">80%": 2}
    assert sum(e["count"] for e in dist) == 5


def test_spearman_math():
    assert spearman([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0
    assert spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0
    assert spearman([1, 1, 1], [1, 2, 3]) is None
    assert spearman([1, 2], [1, 2]) is None


def test_data_quality_transparent_score():
    pros = generate_profiles(200, 8007, country="India")
    quality = compute_analytics(pros)["data_quality"]
    assert quality["total_profiles"] == 200
    assert quality["duplicate_ids"] == 0
    assert quality["invalid_categories"] == {}
    assert quality["inconsistencies"]["gender_language_mapping"] == 0
    assert quality["checks_per_profile"] == 7
    expected = round(100 * (1 - quality["failed_checks"] / (200 * 7)), 2)
    assert quality["data_quality_score"] == expected
    assert "not accuracy" in quality["formula"]
    assert set(quality["segment_coverage"]) == {"deliberate_researcher", "price_conscious_evaluator",
                                                "brand_loyal_buyer", "impulse_oriented_buyer",
                                                "balanced_mixed"}
    assert quality["country_coverage"][0] == {"label": "India", "count": 200}


def test_filtered_and_country_specific_analytics():
    pros = generate_profiles(400, 8008, country_mode="multiple",
                             countries=["India", "Saudi Arabia"])
    filtered = apply_filters(pros, ProfileFilter(country="Saudi Arabia", age_min=25, age_max=40))
    analytics = compute_analytics(filtered)
    assert analytics["overview"]["total_profiles"] == len(filtered)
    assert analytics["overview"]["country_count"] == 1
    assert analytics["geography"]["country_distribution"] == [
        {"label": "Saudi Arabia", "count": len(filtered)}]
    assert all(25 <= p["age"] <= 40 for p in filtered)


def test_empty_and_missing_field_handling():
    empty = compute_analytics([])
    assert empty["overview"]["total_profiles"] == 0
    assert empty["overview"]["median_age"] is None
    assert empty["segments"]["total_profiles"] == 0
    assert empty["data_quality"]["data_quality_score"] is None
    assert empty["relationships"]["age_vs_income"]["correlation"] is None
    partial = [{"profile_id": "x-1", "age": 30, "country": "India"}]
    partial_result = compute_analytics(partial)
    assert partial_result["overview"]["total_profiles"] == 1
    assert partial_result["data_quality"]["missing_values"]


def test_analytics_endpoint_structure_and_compare_still_work():
    r = client.post("/analytics", json={"generation": {"count": 120, "seed": 21,
                                                       "country": "Saudi Arabia"}})
    assert r.status_code == 200
    body = r.json()
    assert body["total_generated"] == 120
    assert body["filters_applied"] == {}
    assert body["overview"]["country_count"] == 1
    assert body["overview"]["income_currency"] == "SAR"
    assert body["data_quality"]["data_quality_score"] is not None

    r = client.post("/analytics", json={
        "generation": {"count": 200, "seed": 22, "countries": ["India", "Saudi Arabia"]},
        "filters": {"age_min": 25, "age_max": 40, "country": ["SA"]}})
    assert r.status_code == 200
    assert r.json()["filters_applied"] == {"age_min": 25, "age_max": 40, "country": ["SA"]}
    assert r.json()["overview"]["country_count"] == 1

    r = client.post("/analytics", json={"generation": {"count": 5, "seed": 1},
                                        "filters": {"gender": "X"}})
    assert r.status_code == 422

    r = client.post("/compare", json={"populations": [
        {"label": "India", "generation": {"count": 60, "seed": 23, "country": "India"}},
        {"label": "Saudi Arabia", "generation": {"count": 60, "seed": 23,
                                                "country": "Saudi Arabia"}}]})
    assert r.status_code == 200
    assert set(r.json()["segments"]["categories"]) == {
        "deliberate_researcher", "price_conscious_evaluator", "brand_loyal_buyer",
        "impulse_oriented_buyer", "balanced_mixed"}
    assert compare_populations  # comparison service reused, not duplicated
