"""Tests for the evidence-backed reference data layer (Raven).

Covers: snapshot schema/provenance, all-country coverage with explicit
evidence statuses, fallback policy (missing evidence never presented as
verified), derived-prior models, and generator integration invariants.
"""
import math

import pytest

from app import reference_data as rd
from app.geography import COUNTRIES, get_context
from app.generator import generate_profiles
from app.utils import profile_rng

ALL_COUNTRIES = sorted(COUNTRIES.keys())


def test_snapshot_loads_and_has_provenance():
    meta = rd.snapshot_meta()
    assert meta["loaded"], "reference snapshot missing — run scripts/normalize_reference_data.py"
    assert meta["schema_version"] == "2.0"
    assert meta["retrieved_at"] == "2026-11-17"
    assert meta["record_count"] >= 3000
    assert meta["country_count"] >= 192  # all countries with WDI evidence (VAT has none)


def test_snapshot_records_carry_full_provenance():
    snap = rd.load_snapshot()
    required = {
        "country_code", "country_iso3", "indicator_id", "wdi_indicator", "value",
        "unit", "reference_year", "source_organization", "source_dataset",
        "source_url", "licence", "retrieved_at", "evidence_status",
        "approved_for_generation",
    }
    for rec in snap["records"]:
        missing = required - rec.keys()
        assert not missing, f"record missing provenance fields: {missing}"
        assert rec["evidence_status"] in {"verified", "estimated", "reference_only", "missing"}
        assert rec["source_url"].startswith("https://api.worldbank.org/")
        assert "CC BY 4.0" in rec["licence"]


def test_evidence_statuses_are_explicit_for_every_country_indicator():
    cov = rd.load_snapshot()["indicator_summary"]
    for ind, s in cov.items():
        total = s["verified"] + s["estimated"] + s["reference_only"] + s["missing"]
        assert total == 193, f"{ind} coverage does not sum to 193 countries: {s}"


def test_priority_indicators_cover_at_least_177_countries():
    cov = rd.coverage_report()
    for ind in (
        "female_population_share", "age_0_14_share", "age_15_64_share", "age_65plus_share",
        "urban_population_share", "internet_use_share", "mobile_subscriptions_per100",
    ):
        assert cov[ind]["verified"] >= 190, f"{ind} unexpectedly sparse: {cov[ind]}"
    for ind in ("unemployment_rate", "labour_force_participation", "income_inequality_gini",
                "employment_agri_share", "employment_industry_share", "employment_services_share"):
        assert cov[ind]["verified"] >= 160, f"{ind} unexpectedly sparse: {cov[ind]}"


def test_reference_only_indicators_are_never_approved():
    snap = rd.load_snapshot()
    for rec in snap["records"]:
        if rec["indicator_id"] in {
            "fixed_broadband_per100", "gdp_per_capita_usd_nominal", "adult_literacy_rate",
            "population_total",
        }:
            assert rec["approved_for_generation"] is False, rec
            assert rec["evidence_status"] in {"reference_only", "verified"}


def test_fallback_returns_default_untouched_and_flagged():
    # Vatican City (VA) has no WDI evidence: every accessor must fall back.
    assert rd.reference_prior("VA", "internet_use_share", 0.42) == 0.42
    assert rd.elderly_share("VA") is None
    assert rd.elderly_adult_share("VA") is None
    assert rd.income_noise_sigma("VA") == 0.28
    assert rd.employment_gap_probability("VA") == 0.04
    assert rd.education_postgrad_scale("VA") == 1.0
    gw = rd.gender_weights("VA")
    assert (gw["Female"], gw["Male"], gw["Non-binary"]) == (0.48, 0.48, 0.04)
    assert gw["evidence_status"] == "legacy_default"
    # Unknown indicator / unknown country behave the same way.
    assert rd.reference_prior("US", "nonexistent_indicator", 7) == 7
    assert rd.reference_prior("XX", "urban_population_share", 3) == 3


def test_reference_only_never_used_as_prior():
    # adult literacy is reference_only: even where a value exists it must not
    # be returned by reference_prior with approved_only=True (the default).
    rec = rd.country_record("IN", "adult_literacy_rate")
    assert rec is not None and rec["evidence_status"] == "reference_only"
    assert rd.reference_prior("IN", "adult_literacy_rate", 0.5) == 0.5
    # explicit opt-in can read it for context
    assert rd.reference_prior("IN", "adult_literacy_rate", 0.5, approved_only=False) == rec["value"]


def test_reference_prior_values_are_in_expected_ranges():
    # proportion-unit indicators (snapshot stores 0-1)
    for code, ind in (("US", "urban_population_share"), ("IN", "internet_use_share")):
        v = rd.reference_prior(code, ind, None)
        assert v is not None and 0.0 <= v <= 1.0, (code, ind, v)
    # percent-unit indicators stay on their native scale
    v = rd.reference_prior("JP", "age_65plus_share", None)
    assert v is not None and 0 <= v <= 60, v
    v = rd.reference_prior("NG", "age_0_14_share", None)
    assert v is not None and 0 <= v <= 60, v
    # gini stays 0-100 scale
    g = rd.reference_prior("ZA", "income_inequality_gini", None)
    assert g is not None and 20 <= g <= 70
    # unemployment is a percent of labour force
    u = rd.reference_prior("ES", "unemployment_rate", None)
    assert u is not None and 0 <= u <= 35


def test_gender_weights_derive_from_female_share():
    gw_us = rd.gender_weights("US")
    female_us = rd.reference_prior("US", "female_population_share", None)
    assert female_us is not None  # percent of total population
    female_prop = female_us / 100.0
    total = gw_us["Female"] + gw_us["Male"] + gw_us["Non-binary"]
    assert abs(total - 1.0) < 1e-6
    assert gw_us["Non-binary"] <= 0.04 + 1e-9
    assert gw_us["evidence_status"] == "estimated"
    # Male share tracks (1 - female) proportionally
    assert abs(gw_us["Male"] - (1 - female_prop) * 0.96) < 0.01
    # High-female-share country skews female; low skews male
    ru = rd.gender_weights("RU")
    ind = rd.gender_weights("IN")
    assert ru["Female"] > ru["Male"]
    assert ind["Male"] > ind["Female"]


def test_elderly_adult_share_renormalisation():
    s65 = rd.elderly_share("JP")
    s1564 = rd.reference_prior("JP", "age_15_64_share", None) / 100.0
    adult = rd.elderly_adult_share("JP")
    assert s65 is not None and s1564 is not None and adult is not None
    expected = s65 / (s1564 + s65)
    assert abs(adult - expected) < 1e-9
    assert 0.0 < adult < 1.0
    # Japan is much older than Nigeria
    assert adult > rd.elderly_adult_share("NG") * 3


def test_income_noise_sigma_from_gini():
    gini_bra = rd.reference_prior("BR", "income_inequality_gini", None)
    sigma_bra = rd.income_noise_sigma("BR")
    sigma_swe = rd.income_noise_sigma("SE")
    # documented damped model: 0.28 + (sqrt(2)*Phi^-1((G+1)/2) - 0.55)*0.35
    expected = 0.28 + (math.sqrt(2.0) * _phi_inv((gini_bra / 100 + 1) / 2) - 0.55) * 0.35
    assert abs(sigma_bra - expected) < 1e-3
    # clamped bounds
    assert 0.18 <= sigma_bra <= 0.62 and 0.18 <= sigma_swe <= 0.62
    # unequal countries spread incomes more than equal ones
    gini_swe = rd.reference_prior("SE", "income_inequality_gini", None)
    if gini_swe < gini_bra:
        assert sigma_swe < sigma_bra


def _phi_inv(p):
    import statistics
    return statistics.NormalDist().inv_cdf(p)


def test_employment_gap_probability_tracks_unemployment():
    u_es = rd.reference_prior("ES", "unemployment_rate", None)
    p_es = rd.employment_gap_probability("ES")
    assert abs(p_es - min(0.38, max(0.03, u_es / 100 * 1.9))) < 1e-6
    # Niger (~0.4% unemployment) hits the low clamp; Spain sits far above legacy 4%
    assert rd.employment_gap_probability("NE") == 0.03
    assert p_es > 0.10
    assert rd.employment_gap_probability("VA") == 0.04


def test_industry_sector_weights_sum_and_map():
    w = rd.industry_sector_weights("MW", ("Services", "Technology", "Trade", "Manufacturing", "Agriculture"))
    assert w is not None
    # every weight positive, and Agriculture carries the dominant measured share
    assert all(x > 0 for x in w)
    assert w[-1] > w[0]
    ind = rd._indexes()[1]["MW"]["industry_prior"]
    assert abs(ind["agriculture_share"] + ind["industry_share"] + ind["services_share"] - 1.0) < 0.01
    # no evidence -> None (legacy path preserved)
    assert rd.industry_sector_weights("VA", ("Services",)) is None


def test_every_country_context_carries_reference_backed_fields():
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        ctx = get_context(profile_rng(1, 1), country_mode="specific", country=name)
        assert 0.0 <= ctx.urban_share <= 1.0, name
        assert 0.0 <= ctx.digital_access <= 1.0, name
        if code != "VA":
            assert ctx.elderly_share is not None and 0.0 < ctx.elderly_share < 1.0, name
            assert ctx.income_noise_sigma is not None, name
            # urban share equals the verified WDI value, not the registry guess
            ref = rd.reference_prior(code, "urban_population_share", None)
            assert ref is not None and abs(ctx.urban_share - ref) < 1e-9, name


def test_metro_cities_are_always_urban():
    ctx = get_context(profile_rng(2, 1), country_mode="specific", country="United States")
    # Sampled US cities are documented metros: unconditionally Urban
    assert ctx.city in {"Los Angeles", "New York City", "Austin"} and ctx.urban_rural == "Urban"
    # A low-urban-share country can still draw Rural away from metros
    ctx_in = get_context(profile_rng(3, 1), country_mode="specific", country="India")
    assert ctx_in.urban_rural in {"Urban", "Rural"}


def test_country_specific_priors_change_generation():
    # Age structure: Japanese profiles skew older than Nigerian ones.
    jp = generate_profiles(400, 1234, country="Japan")
    ng = generate_profiles(400, 1234, country="Nigeria")
    jp_senior = sum(p["age"] >= 65 for p in jp) / len(jp)
    ng_senior = sum(p["age"] >= 65 for p in ng) / len(ng)
    jp_share = rd.elderly_adult_share("JP")
    ng_share = rd.elderly_adult_share("NG")
    assert jp_senior > 0.5 * jp_share, (jp_senior, jp_share)
    assert jp_senior > ng_senior * 2, (jp_senior, ng_senior)
    # Gender: Russia female-majority vs India male-majority (weights ~51.5% / ~46.5%)
    ru = generate_profiles(800, 1234, country="Russia")
    ind = generate_profiles(800, 1234, country="India")
    ru_f = sum(p["gender"] == "Female" for p in ru) / len(ru)
    ind_f = sum(p["gender"] == "Female" for p in ind) / len(ind)
    assert ru_f > 0.49, ru_f
    assert ind_f < 0.49, ind_f
    assert ru_f > ind_f
    # Non-binary never exceeds its documented cap in large samples
    big = generate_profiles(600, 4321, country="United States")
    assert all(p["gender"] in {"Female", "Male", "Non-binary"} for p in big)


def test_determinism_with_reference_priors():
    a = generate_profiles(3, 77, country="Brazil")
    b = generate_profiles(3, 77, country="Brazil")
    assert a == b


def test_derived_priors_present_for_all_evidence_countries():
    derived = rd.load_snapshot()["derived_priors"]
    # 192 countries have WDI evidence; all of them carry gender + age + spread priors
    codes = {COUNTRIES[name]["code"] for name in ALL_COUNTRIES}
    with_evidence = codes - {"VA"}
    missing_gw = [c for c in with_evidence if "gender_weights" not in derived.get(c, {})]
    assert not missing_gw, f"gender prior missing for: {missing_gw[:5]}"
    missing_age = [c for c in with_evidence if "age_prior" not in derived.get(c, {})]
    assert not missing_age, f"age prior missing for: {missing_age[:5]}"
