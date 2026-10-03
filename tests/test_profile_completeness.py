"""Canonical attribute audit, summary/full views, downloads, and input validation."""
import io
import pandas as pd
from fastapi.testclient import TestClient

from app.generator import generate_profiles
from app.main import app
from app.rules import assess_profile
from app.schemas import CORE_PROFILE_FIELDS, PROFILE_COLUMNS, GenerateRequest

client = TestClient(app)

DERIVED_FIELDS = (
    "profile_summary", "social_disposition", "review_influence",
    "interactive_content_engagement", "social_shopping_tendency",
    "advertisement_responsiveness", "social_consumer_tendency",
    "social_creator_tendency", "social_engagement_level", "trend_sensitivity",
    "influencer_influence", "brand_interaction_tendency",
)


def test_canonical_attribute_audit_is_clean():
    print(f"\nTotal canonical attributes: {len(PROFILE_COLUMNS)}")
    assert len(PROFILE_COLUMNS) == len(set(PROFILE_COLUMNS)), "duplicate columns"
    assert not any(name.startswith(("feature_", "random_value_", "dummy_")) for name in PROFILE_COLUMNS)
    profiles = generate_profiles(5, 9001)
    generated = set(profiles[0])
    missing = set(PROFILE_COLUMNS) - generated
    unexpected = generated - set(PROFILE_COLUMNS)
    print(f"Generated attributes: {len(generated)}")
    print(f"Missing attributes: {sorted(missing)}")
    print(f"Unexpected attributes: {sorted(unexpected)}")
    assert missing == set() and unexpected == set()
    for field in DERIVED_FIELDS:
        assert field in PROFILE_COLUMNS
    assert len(CORE_PROFILE_FIELDS) == len(set(CORE_PROFILE_FIELDS))
    assert set(CORE_PROFILE_FIELDS) <= set(PROFILE_COLUMNS)


def test_derived_fields_are_coherent_not_independent():
    pros = generate_profiles(200, 9002)
    for p in pros:
        assert assess_profile(p)["valid"]
        assert isinstance(p["profile_summary"], str) and len(p["profile_summary"]) > 40
        assert p["social_disposition"] in ("Introvert", "Ambivert", "Extrovert")
        for key in DERIVED_FIELDS[2:]:
            assert p[key] in ("Low", "Moderate", "High"), key
    # Disposition tracks extraversion: high-extraversion population skews Extrovert.
    extro = [p for p in pros if p["extraversion"] in ("High", "Very high")]
    intro = [p for p in pros if p["extraversion"] in ("Very low", "Low")]
    assert extro and intro
    assert (sum(1 for p in extro if p["social_disposition"] == "Extrovert") / len(extro)
            > sum(1 for p in intro if p["social_disposition"] == "Extrovert") / len(intro))
    # Influencer influence is not a copy of following; review != recommendation.
    assert any(p["influencer_influence"] != _freq_to_level(p["influencer_following"]) for p in pros)
    assert not all(p["review_influence"] == p["recommendation_dependence"] for p in pros)


def _freq_to_level(value):
    return {"Never": "Low", "Rarely": "Low", "Occasionally": "Moderate",
            "Frequently": "High", "Very frequently": "High"}.get(value)


def test_summary_and_full_views():
    full = client.post("/generate", json={"count": 2, "seed": 11}).json()
    assert full["view"] == "full" and full["feature_count"] == len(PROFILE_COLUMNS)
    assert set(full["profiles"][0]) == set(PROFILE_COLUMNS)
    summary = client.post("/generate", json={"count": 2, "seed": 11, "view": "summary"}).json()
    assert summary["view"] == "summary"
    assert summary["canonical_feature_count"] == len(PROFILE_COLUMNS)
    assert set(summary["profiles"][0]) == set(CORE_PROFILE_FIELDS)
    assert summary["profiles"][0]["profile_summary"] == full["profiles"][0]["profile_summary"]


def test_individual_and_bulk_downloads():
    # Individual full JSON download.
    r = client.post("/generate", json={"count": 3, "seed": 21, "scope": "individual",
                                       "view": "full", "format": "json"})
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith('attachment; filename="raven_profile_')
    assert len(r.json()) == len(PROFILE_COLUMNS)
    # Individual summary CSV download (single row + header).
    r = client.post("/generate", json={"count": 3, "seed": 21, "scope": "individual",
                                       "view": "summary", "format": "csv"})
    assert r.status_code == 200
    assert "raven_profile_" in r.headers["content-disposition"]
    assert "raven_profiles_summary" not in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert len(lines) == 2 and lines[0].split(",")[0] == "personality_name"
    assert len(lines[0].split(",")) == len(CORE_PROFILE_FIELDS)
    # Bulk summary CSV download.
    r = client.post("/generate", json={"count": 4, "seed": 22, "view": "summary", "format": "csv"})
    assert r.status_code == 200
    assert 'filename="raven_profiles_summary.csv"' in r.headers["content-disposition"]
    df = pd.read_csv(io.StringIO(r.text))
    assert list(df.columns) == list(CORE_PROFILE_FIELDS) and len(df) == 4
    # Bulk full CSV download: one row per profile, one column per attribute.
    r = client.post("/generate", json={"count": 4, "seed": 22, "view": "full", "format": "csv"})
    assert r.status_code == 200
    assert f'filename="raven_profiles_full_{len(PROFILE_COLUMNS)}.csv"' in r.headers["content-disposition"]
    df = pd.read_csv(io.StringIO(r.text))
    assert list(df.columns) == list(PROFILE_COLUMNS) and len(df) == 4
    assert df["profile_id"].is_unique
    # Bulk full parquet download.
    r = client.post("/generate", json={"count": 3, "seed": 23, "format": "parquet"})
    assert r.status_code == 200
    pdf = pd.read_parquet(io.BytesIO(r.content))
    assert list(pdf.columns) == list(PROFILE_COLUMNS) and len(pdf) == 3


def test_no_movie_genre_input_required():
    fields = set(GenerateRequest.model_fields)
    assert not any("genre" in name or "movie" in name for name in fields)
    r = client.post("/generate", json={"count": 2, "seed": 31})
    assert r.status_code == 200
    for p in r.json()["profiles"]:
        assert p["preferred_movie_genres"]  # generated output, not an input
    r = client.post("/generate", json={"count": 1, "seed": 31, "movie_genre": "Action"})
    assert r.status_code == 200  # unknown extra field ignored, never required


def test_invalid_inputs_rejected():
    assert client.post("/generate", json={"count": 0}).status_code == 422
    assert client.post("/generate", json={"count": 2, "seed": 1, "country": "Atlantis"}).status_code == 422
    assert client.post("/generate", json={"count": 2, "seed": 1, "view": "tiny"}).status_code == 422
    assert client.post("/generate", json={"count": 2, "seed": 1, "scope": "solo"}).status_code == 422
    assert client.post("/generate", json={"count": 2, "seed": 1, "profile_index": 5}).status_code == 422
    assert client.post("/generate", json={"count": 2, "seed": 1, "format": "xml"}).status_code == 422
    assert client.post("/generate", json={"count": 2, "seed": 1, "age_range": [40, 20]}).status_code == 422


def test_single_multiple_country_global_and_comparison():
    one = client.post("/generate", json={"count": 1, "seed": 41}).json()
    assert one["count"] == 1 and len(one["profiles"][0]) == len(PROFILE_COLUMNS)
    multi = client.post("/generate", json={"count": 30, "seed": 42,
                                           "countries": ["India", "Japan"]}).json()
    assert {p["country"] for p in multi["profiles"]} <= {"India", "Japan"}
    glob = client.post("/generate", json={"count": 30, "seed": 43,
                                          "country_mode": "global"}).json()
    assert len({p["country"] for p in glob["profiles"]}) > 1
    comp = client.post("/compare", json={"populations": [
        {"label": "A", "generation": {"count": 20, "seed": 44, "country": "India"}},
        {"label": "B", "generation": {"count": 20, "seed": 44, "country": "Japan"}}]})
    assert comp.status_code == 200
