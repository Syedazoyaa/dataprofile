"""Regression tests for schema, calendar, tenure and export correctness."""

from datetime import date
import csv
import io

from app.config import get_settings
from app.exports import export_bytes
from app.generator import age_on, generate_profiles
from app.rules import assess_profile
from app.schemas import PROFILE_COLUMNS, PROFILE_SCHEMA


def test_every_generated_value_matches_the_canonical_schema_type():
    profile = generate_profiles(1, 8101)[0]
    assert tuple(profile) == PROFILE_COLUMNS
    for field in PROFILE_SCHEMA:
        value = profile[field.name]
        if field.value_type == "integer":
            assert isinstance(value, int) and not isinstance(value, bool), field.name
        elif field.value_type == "number":
            assert isinstance(value, (int, float)) and not isinstance(value, bool), field.name
        elif field.value_type == "array":
            assert isinstance(value, list), field.name
        elif field.value_type == "boolean":
            assert isinstance(value, bool), field.name
        elif field.value_type == "date":
            assert isinstance(value, str), field.name
            date.fromisoformat(value)
        else:
            assert isinstance(value, str), field.name


def test_calendar_aware_dob_matches_age_and_is_reproducible(monkeypatch):
    monkeypatch.setenv("GENERATION_REFERENCE_DATE", "2024-02-29")
    get_settings.cache_clear()
    try:
        first = generate_profiles(200, 8102)
        second = generate_profiles(200, 8102)
        assert first == second
        for profile in first:
            dob = date.fromisoformat(profile["date_of_birth"])
            reference = date.fromisoformat(profile["generation_reference_date"])
            assert reference == date(2024, 2, 29)
            assert age_on(dob, reference) == profile["age"]
    finally:
        get_settings.cache_clear()


def test_tenure_is_derived_from_living_arrangement_and_checked():
    profiles = generate_profiles(500, 8103)
    expected = {"Owned home": "Owner", "Rented home": "Renter",
                "Shared housing": "Renter", "Family home": "Not owner"}
    assert all(p["home_ownership"] == expected[p["living_arrangement"]] for p in profiles)
    invalid = dict(profiles[0])
    invalid["home_ownership"] = "Renter" if invalid["home_ownership"] != "Renter" else "Owner"
    assert not assess_profile(invalid)["valid"]


def test_research_distribution_retains_low_values_and_csv_round_trips_special_text():
    profiles = generate_profiles(1000, 8104)
    assert any(profile["research_intensity"] == "Low" for profile in profiles)
    exported_profile = dict(profiles[0])
    exported_profile["profile_summary"] = 'Unicode Ω, "quoted"\nand multiline'
    payload, media_type, _ = export_bytes([exported_profile], "csv")
    assert media_type == "text/csv"
    row = next(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
    assert row["profile_summary"] == exported_profile["profile_summary"]
