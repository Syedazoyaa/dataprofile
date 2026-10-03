"""Country registry, coverage levels and country-conditioned generation tests."""
import pytest
from fastapi.testclient import TestClient

from app.generator import generate_profiles
from app.geography import (
    COUNTRIES,
    DEEP_COVERAGE,
    country_registry,
    coverage_for,
    resolve_country_name,
    supported_countries,
)
from app.main import app
from app.rules import assess_profile
from app.schemas import ProfileFilter
from app.filtering import apply_filters

client = TestClient(app)


def test_registry_completeness_and_iso_codes():
    assert len(COUNTRIES) == 193
    assert len(supported_countries()) == 193
    registry = country_registry()
    assert len(registry) == 193
    for entry in registry:
        assert {"name", "alpha2", "alpha3", "numeric", "continent", "subregion",
                "nationality", "currency", "languages", "coverage"} <= set(entry)
        assert len(entry["alpha2"]) == 2 and len(entry["alpha3"]) == 3
        assert entry["languages"], f"{entry['name']} must list at least one language"
    assert len({e["alpha2"] for e in registry}) == 193
    assert len({e["alpha3"] for e in registry}) == 193


def test_resolve_country_name_accepts_codes():
    assert resolve_country_name("Saudi Arabia") == "Saudi Arabia"
    assert resolve_country_name("SA") == "Saudi Arabia"
    assert resolve_country_name("sau") == "Saudi Arabia"
    assert resolve_country_name("IN") == "India"
    with pytest.raises(ValueError):
        resolve_country_name("Atlantis")


def test_coverage_levels_are_explicit():
    assert DEEP_COVERAGE == {"India", "United States", "United Kingdom", "Japan",
                             "Saudi Arabia", "Brazil", "Nigeria"}
    assert coverage_for("India") == "deep"
    assert coverage_for("SA") == "deep"
    assert coverage_for("Germany") == "standard"
    assert coverage_for("Qatar") == "standard"
    registry = {e["name"]: e["coverage"] for e in country_registry()}
    assert sum(1 for c in registry.values() if c == "deep") == 7
    assert sum(1 for c in registry.values() if c == "standard") == 186


def test_single_country_generation_is_conditioned():
    pros = generate_profiles(120, 7001, country="Saudi Arabia")
    assert {p["country"] for p in pros} == {"Saudi Arabia"}
    assert {p["currency"] for p in pros} == {"SAR"}
    assert {p["country_code"] for p in pros} == {"SA"}
    for p in pros:
        assert p["primary_language"] in ("Arabic", "English")
        assert p["city"] in ("Riyadh", "Jeddah", "Dammam")
        assert assess_profile(p)["valid"]
    # Probabilistic, not deterministic stereotypes.
    assert len({p["primary_language"] for p in pros}) == 2
    assert len({p["city"] for p in pros}) >= 2


def test_multi_country_generation_mixes_conditioned_profiles():
    pros = generate_profiles(300, 7002, country_mode="multiple",
                             countries=["India", "Saudi Arabia"])
    by_country = {}
    for p in pros:
        by_country.setdefault(p["country"], []).append(p)
    assert set(by_country) == {"India", "Saudi Arabia"}
    for p in by_country["India"]:
        assert p["currency"] == "INR" and p["primary_language"] in COUNTRIES["India"]["languages"]
    for p in by_country["Saudi Arabia"]:
        assert p["currency"] == "SAR" and p["primary_language"] in ("Arabic", "English")
    assert all(assess_profile(p)["valid"] for p in pros)


def test_multi_country_codes_and_determinism():
    first = generate_profiles(100, 7003, country_mode="multiple", countries=["IN", "SA", "AE"])
    second = generate_profiles(100, 7003, country_mode="multiple",
                               countries=["India", "Saudi Arabia", "United Arab Emirates"])
    assert [p["country"] for p in first] == [p["country"] for p in second]
    assert {p["country"] for p in first} <= {"India", "Saudi Arabia", "United Arab Emirates"}
    with pytest.raises(ValueError):
        generate_profiles(5, 7003, country_mode="multiple", countries=["Atlantis"])


def test_existing_india_behaviour_preserved():
    pros = generate_profiles(100, 7004)
    assert {p["country"] for p in pros} == {"India"}
    assert {p["currency"] for p in pros} == {"INR"}
    # Backward compatibility: old positional signature still works.
    legacy = generate_profiles(5, 7004, "Japan")
    assert {p["country"] for p in legacy} == {"Japan"}


def test_country_filter_single_and_multi_or():
    pros = generate_profiles(200, 7005, country_mode="multiple",
                             countries=["India", "Saudi Arabia", "Japan"])
    single = apply_filters(pros, ProfileFilter(country="India"))
    assert single and all(p["country"] == "India" for p in single)
    multi = apply_filters(pros, ProfileFilter(country=["IN", "Saudi Arabia"]))
    assert multi and {p["country"] for p in multi} <= {"India", "Saudi Arabia"}
    assert len(multi) >= len(single)
    assert all(p["country"] in ("India", "Saudi Arabia") for p in multi)


def test_countries_endpoint_and_generation_api():
    r = client.get("/countries")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 193 and len(body["countries"]) == 193

    r = client.post("/generate", json={"count": 10, "seed": 11, "country": "Saudi Arabia"})
    assert r.status_code == 200
    assert {p["country"] for p in r.json()["profiles"]} == {"Saudi Arabia"}

    r = client.post("/generate", json={"count": 40, "seed": 12,
                                       "countries": ["India", "Saudi Arabia"]})
    assert r.status_code == 200
    assert {p["country"] for p in r.json()["profiles"]} <= {"India", "Saudi Arabia"}

    # No country selected uses the neutral global mode, never India by default.
    r = client.post("/generate", json={"count": 50, "seed": 13})
    assert r.status_code == 200
    assert len({p["country"] for p in r.json()["profiles"]}) > 1

    r = client.post("/generate", json={"count": 3, "seed": 13, "countries": ["Atlantis"]})
    assert r.status_code == 422
    r = client.post("/generate", json={"count": 3, "seed": 13, "countries": []})
    assert r.status_code == 422
