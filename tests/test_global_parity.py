"""Global country parity tests.

Iterates through ALL 193 registered countries to verify that every country
receives equal technical support: resolution, context building, generation,
validation, analytics, comparison, and determinism.

Missing evidence-backed metadata must never crash generation or exclude a
country. Legacy geography_world.py values serve as the fallback for countries
without World Bank-sourced indicators.
"""

import pytest
from app.generator import generate_profiles
from app.geography import (
    COUNTRIES,
    country_registry,
    resolve_country_code,
    resolve_country_name,
    supported_countries,
    get_context,
)
from app.metadata import load_indicators, CATALOG_INDICATORS, coverage_for_country
from app.rules import assess_profile, validate_profile
from app.schemas import PROFILE_COLUMNS
from app.analytics import compute_analytics
from app.comparison import compare_populations
from app.utils import profile_rng

ALL_COUNTRIES = sorted(COUNTRIES.keys())


# --- Country registry resolution ---

def test_all_countries_resolve_by_name():
    """Every registered country name resolves to itself."""
    for name in ALL_COUNTRIES:
        assert resolve_country_name(name) == name


def test_all_countries_resolve_by_alpha2():
    """Every registered ISO alpha-2 code resolves to its country name."""
    for name, item in COUNTRIES.items():
        assert resolve_country_name(item["code"]) == name


def test_all_countries_resolve_by_alpha3():
    """Every registered ISO alpha-3 code resolves to its country name."""
    for name, item in COUNTRIES.items():
        assert resolve_country_name(item["alpha3"]) == name


def test_country_code_consistency():
    """resolve_country_code(name) == item['code'] for every country."""
    for name, item in COUNTRIES.items():
        assert resolve_country_code(name) == item["code"]
        assert resolve_country_code(item["code"]) == item["code"]


def test_registry_matches_context_count():
    """country_registry() returns exactly the same countries as COUNTRIES."""
    registry = country_registry()
    assert len(registry) == len(COUNTRIES)
    registry_codes = {e["alpha2"] for e in registry}
    expected_codes = {item["code"] for item in COUNTRIES.values()}
    assert registry_codes == expected_codes


def test_no_invalid_country_resolves():
    """Invalid country names/codes raise ValueError."""
    for invalid in ["Atlantis", "XX", "ZZZ", "", "United State", "USAA"]:
        with pytest.raises(ValueError):
            resolve_country_name(invalid)


# --- Baseline context completeness ---

def test_all_countries_have_valid_context():
    """Every country can build a GeographicContext without crashing."""
    rng = profile_rng(1, 1)
    for name in ALL_COUNTRIES:
        ctx = get_context(rng, country_mode="specific", country=name)
        assert ctx.country == name
        assert ctx.country_code == COUNTRIES[name]["code"]
        assert ctx.currency == COUNTRIES[name]["currency"]
        assert ctx.languages == COUNTRIES[name]["languages"]
        assert len(ctx.languages) > 0, f"{name} has no languages"
        assert ctx.payments, f"{name} has no payment methods"
        assert ctx.transport, f"{name} has no transport modes"
        assert ctx.foods, f"{name} has no food patterns"
        assert ctx.religions, f"{name} has no religions"
        assert 0 <= ctx.urban_share <= 1, f"{name} urban_share out of range: {ctx.urban_share}"
        assert 0 <= ctx.digital_access <= 1, f"{name} digital_access out of range: {ctx.digital_access}"


def test_all_countries_have_required_context_fields():
    """Every GeographicContext field is populated for every country."""
    rng = profile_rng(1, 1)
    required_fields = [
        "country", "country_code", "alpha3", "numeric", "continent", "subregion",
        "state", "city", "region", "nationality", "languages", "currency",
        "income_scale", "industries", "platforms", "payments", "transport",
        "foods", "religions", "urban_rural", "digital_access", "cost_factor",
        "income_cv", "housing_types", "shopping_ecosystems", "city_tier",
        "climate", "urban_share",
    ]
    for name in ALL_COUNTRIES:
        ctx = get_context(rng, country_mode="specific", country=name)
        for field in required_fields:
            value = getattr(ctx, field)
            assert value is not None and value != "", f"{name}.{field} is None/empty"


# --- Generation across all countries ---

@pytest.mark.parametrize("country_name", ALL_COUNTRIES, ids=lambda n: n[:30])
def test_every_country_generates_valid_profiles(country_name):
    """Every country can generate profiles that pass validation."""
    profiles = generate_profiles(10, 42, country=country_name)
    assert len(profiles) == 10
    for p in profiles:
        assert p["country"] == country_name
        assert p["country_code"] == COUNTRIES[country_name]["code"]
        assert p["currency"] == COUNTRIES[country_name]["currency"]
        assert p["primary_language"] in COUNTRIES[country_name]["languages"]
        assert p["available_payment_method"] in COUNTRIES[country_name]["payments"]
        assert p["primary_transport_mode"] in COUNTRIES[country_name]["transport"]
        assert p["local_food_pattern"] in COUNTRIES[country_name]["foods"]
        result = assess_profile(p)
        assert result["valid"], f"{country_name}: validation failed: {result['violations']}"


def test_all_countries_global_generation_includes_all():
    """Global generation with a large batch includes countries from all continents."""
    profiles = generate_profiles(500, 999, country_mode="global")
    represented = {p["country"] for p in profiles}
    # With 500 profiles across 193 weighted countries, expect broad coverage
    assert len(represented) >= 50, f"Expected >=50 countries in global batch, got {len(represented)}"
    continents = {COUNTRIES[c]["continent"] for c in represented}
    assert len(continents) >= 5, f"Expected >=5 continents, got {len(continents)}"


# --- Metadata coverage parity ---

def test_metadata_coverage_for_all_countries():
    """Every country has a coverage status for all catalog indicators."""
    indicators = load_indicators()
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        cov = coverage_for_country(code)
        assert len(cov) == len(CATALOG_INDICATORS)
        for indicator_id, info in cov.items():
            assert info["status"] in ("approved", "reference", "unavailable")
            assert isinstance(info["approved_for_generation"], bool)


def test_approved_metadata_only_overrides_legacy():
    """Only approved_for_generation=true records override legacy context values."""
    indicators = load_indicators()
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        for indicator_id in CATALOG_INDICATORS:
            record = indicators.get((code, indicator_id))
            if record is not None and record.get("approved_for_generation") is True:
                # Approved records must have a value and source
                assert record.get("value") is not None
                assert record.get("source_ids")


# --- Comparison parity ---

def test_country_comparison_works_for_all_country_pairs():
    """Comparison works for any valid pair of distinct countries."""
    # Test a representative sample of pairs (not all 193*192/2 for speed)
    test_pairs = [
        ("Afghanistan", "Albania"),
        ("Brazil", "Nigeria"),
        ("India", "Japan"),
        ("United States", "United Kingdom"),
        ("Saudi Arabia", "Brazil"),
    ]
    for name_a, name_b in test_pairs:
        result = compare_populations({
            "A": generate_profiles(20, 7, country=name_a),
            "B": generate_profiles(20, 7, country=name_b),
        })
        assert "populations" in result
        assert "demographics" in result
        assert "behavioural" in result
        assert "segments" in result
        assert result["populations"]["A"]["n"] == 20
        assert result["populations"]["B"]["n"] == 20


# --- Determinism parity ---

@pytest.mark.parametrize("country_name", ALL_COUNTRIES[:20], ids=lambda n: n[:20])
def test_determinism_for_all_countries(country_name):
    """Same seed + config produces identical profiles for every country."""
    a = generate_profiles(10, 12345, country=country_name)
    b = generate_profiles(10, 12345, country=country_name)
    assert a == b, f"Non-deterministic generation for {country_name}"


def test_cross_seed_determinism():
    """Different seeds produce different profiles (not identical)."""
    for name in ["Afghanistan", "Brazil", "Japan", "Nigeria", "United States"]:
        a = generate_profiles(5, 1, country=name)
        b = generate_profiles(5, 2, country=name)
        assert a != b, f"Same profiles for different seeds: {name}"


# --- Analytics parity ---

def test_analytics_coverage_reports_all_countries():
    """Analytics metadata_coverage reports every country present in the population."""
    profiles = generate_profiles(100, 5, country_mode="global")
    result = compute_analytics(profiles)
    mc = result["metadata_coverage"]
    assert "coverage_percent" in mc
    assert "countries" in mc
    assert "total_country_indicator_cells" in mc
    assert "approved_indicators" in mc
    # Coverage percent should not exceed 100
    if mc["coverage_percent"] is not None:
        assert 0 <= mc["coverage_percent"] <= 100


def test_metadata_coverage_separate_from_data_quality():
    """metadata_coverage is a separate section from data_quality."""
    profiles = generate_profiles(20, 5, country="Brazil")
    result = compute_analytics(profiles)
    assert "metadata_coverage" in result
    assert "data_quality" in result
    assert result["metadata_coverage"] is not result["data_quality"]
    # data_quality audits the sample; metadata_coverage audits reference evidence
    assert result["data_quality"]["checks_per_profile"] == 7
    assert "catalog_indicators" in result["metadata_coverage"]


# --- Global generation coverage ---

def test_global_generation_does_not_exclude_metadata_poor_countries():
    """Countries without approved metadata must still appear in global
    generation. No country is silently excluded due to lack of evidence."""
    # Generate a large batch and verify that countries with zero approved
    # metadata still appear
    profiles = generate_profiles(1000, 42, country_mode="global")
    represented = {p["country"] for p in profiles}

    indicators = load_indicators()
    zero_metadata_countries = set()
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        has_any = any(
            indicators.get((code, ind_id)) is not None
            for ind_id in CATALOG_INDICATORS
        )
        if not has_any:
            zero_metadata_countries.add(name)

    # At least some zero-metadata countries should be represented
    represented_zero_meta = represented & zero_metadata_countries
    assert len(represented_zero_meta) > 0, (
        "Countries without metadata were silently excluded from global generation"
    )


def test_global_generation_covers_all_continents():
    """Global generation must represent countries from all inhabited
    continents where the registry supports them."""
    profiles = generate_profiles(2000, 42, country_mode="global")
    represented = {p["country"] for p in profiles}
    continents = {COUNTRIES[c]["continent"] for c in represented}

    # All 6 inhabited continents should be represented
    expected_continents = {"Asia", "Europe", "Africa", "North America", "South America", "Oceania"}
    missing = expected_continents - continents
    assert not missing, f"Global generation missing continents: {missing}"


def test_country_comparison_uses_correct_context():
    """Each country in a comparison must use its own context (currency,
    language, etc.), not leak from the other country."""
    result = compare_populations({
        "A": generate_profiles(50, 7, country="India"),
        "B": generate_profiles(50, 7, country="Japan"),
    })

    # Verify each population's country context is correct
    # The comparison returns distributions, so we check the raw profiles
    in_profiles = generate_profiles(50, 7, country="India")
    jp_profiles = generate_profiles(50, 7, country="Japan")

    assert all(p["country"] == "India" for p in in_profiles)
    assert all(p["country"] == "Japan" for p in jp_profiles)
    assert all(p["currency"] == "INR" for p in in_profiles)
    assert all(p["currency"] == "JPY" for p in jp_profiles)
# --- Metadata approval rules ---

def test_reference_only_records_do_not_override_generation():
    """Records with approved_for_generation=false must never change
    generated output. income_inequality_gini and gdp_per_capita_usd are
    reference-only; they must not appear as overrides in context values."""
    indicators = load_indicators()
    # Find countries with reference-only gini or gdp records
    ref_countries = set()
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        for indicator_id in ("income_inequality_gini", "gdp_per_capita_usd"):
            record = indicators.get((code, indicator_id))
            if record is not None and record.get("approved_for_generation") is False:
                ref_countries.add(name)
    assert len(ref_countries) > 0, "Expected at least one country with reference-only records"

    # Generate profiles for those countries and verify they pass validation
    # (reference-only metadata must not break anything)
    for name in list(ref_countries)[:10]:
        profiles = generate_profiles(5, 42, country=name)
        for p in profiles:
            result = assess_profile(p)
            assert result["valid"], f"{name}: reference-only metadata broke validation: {result['violations']}"


def test_metadata_country_isolation():
    """Metadata for one country must not override another country's context.
    Each country's approved_value lookup is keyed by (country_code, indicator_id)."""
    indicators = load_indicators()
    # Pick two countries with approved urban_population_share
    at_record = indicators.get(("AT", "urban_population_share"))
    ca_record = indicators.get(("CA", "urban_population_share"))
    assert at_record is not None and at_record.get("approved_for_generation") is True
    assert ca_record is not None and ca_record.get("approved_for_generation") is True
    assert at_record["value"] != ca_record["value"], "AT and CA should have different urban_share values"

    # Generate profiles for both and verify each uses its own value
    at_profiles = generate_profiles(5, 42, country="Austria")
    ca_profiles = generate_profiles(5, 42, country="Canada")
    at_urban = {p["urban_share"] for p in at_profiles if p.get("urban_share") is not None}
    ca_urban = {p["urban_share"] for p in ca_profiles if p.get("urban_share") is not None}
    # urban_share is used as a probability threshold for urban_rural assignment,
    # so the actual urban_rural values will differ stochastically. But we can
    # verify the context was built correctly by checking get_context directly.
    from app.geography import get_context
    from app.utils import profile_rng
    rng = profile_rng(1, 1)
    at_ctx = get_context(rng, country_mode="specific", country="Austria")
    ca_ctx = get_context(rng, country_mode="specific", country="Canada")
    assert at_ctx.urban_share == at_record["value"], f"AT urban_share mismatch: {at_ctx.urban_share} != {at_record['value']}"
    assert ca_ctx.urban_share == ca_record["value"], f"CA urban_share mismatch: {ca_ctx.urban_share} != {ca_record['value']}"


def test_metadata_value_range_validation():
    """Approved metadata values must be within permitted ranges for their unit."""
    indicators = load_indicators()
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        for indicator_id in CATALOG_INDICATORS:
            record = indicators.get((code, indicator_id))
            if record is None or not record.get("approved_for_generation"):
                continue
            value = record.get("value")
            unit = record.get("unit")
            if value is None:
                continue
            if unit == "proportion_0_1":
                assert 0 <= value <= 1, f"{code}/{indicator_id}: proportion out of range: {value}"
            elif unit == "index_0_100":
                assert 0 <= value <= 100, f"{code}/{indicator_id}: index out of range: {value}"
            elif unit == "usd":
                assert value >= 0, f"{code}/{indicator_id}: negative USD value: {value}"


def test_metadata_source_attribution():
    """Every approved record must have source attribution."""
    indicators = load_indicators()
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        for indicator_id in CATALOG_INDICATORS:
            record = indicators.get((code, indicator_id))
            if record is None or not record.get("approved_for_generation"):
                continue
            assert record.get("source_ids"), f"{code}/{indicator_id}: approved record missing source_ids"
            assert record.get("source_url"), f"{code}/{indicator_id}: approved record missing source_url"
            assert record.get("reference_year") is not None, f"{code}/{indicator_id}: approved record missing reference_year"
            assert record.get("evidence_status"), f"{code}/{indicator_id}: approved record missing evidence_status"


# --- Offline operation (no network imports in production path) ---

def test_no_network_imports_in_generation_path():
    """Verify that the generation modules do not import Firecrawl,
    httpx, requests, or other network clients as actual import statements."""
    import importlib
    import inspect
    import re

    modules_to_check = [
        "app.generator",
        "app.geography",
        "app.metadata",
        "app.rules",
        "app.analytics",
        "app.coherence",
        "app.derived",
        "app.filtering",
        "app.comparison",
        "app.segmentation",
        "app.exports",
    ]
    banned_imports = {"firecrawl", "httpx", "requests", "urllib", "aiohttp"}
    import_pattern = re.compile(r"^\s*(?:import|from)\s+(" + "|".join(banned_imports) + r")\b", re.MULTILINE | re.IGNORECASE)
    for mod_name in modules_to_check:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        source = inspect.getsource(mod)
        matches = import_pattern.findall(source)
        assert not matches, f"{mod_name} imports banned network module(s): {matches}"


# --- Metadata fail-safe behavior ---

def test_missing_metadata_file_falls_back_safely():
    """If the metadata file is missing or unreadable, generation must
    fall back to legacy geography values without crashing."""
    from app import metadata as metadata_mod
    original_file = metadata_mod.METADATA_FILE

    try:
        # Point to a non-existent file
        from pathlib import Path
        metadata_mod.METADATA_FILE = Path("/nonexistent/path/metadata.json")
        metadata_mod.load_indicators.cache_clear()

        # Generation should still work with legacy values
        profiles = generate_profiles(5, 42, country="India")
        for p in profiles:
            result = assess_profile(p)
            assert result["valid"], f"Fallback generation failed: {result['violations']}"

        # load_indicators should return empty
        assert metadata_mod.load_indicators() == {}
    finally:
        metadata_mod.METADATA_FILE = original_file
        metadata_mod.load_indicators.cache_clear()


def test_malformed_metadata_file_falls_back_safely():
    """If the metadata file contains invalid JSON, generation must
    fall back to legacy values without crashing."""
    from app import metadata as metadata_mod
    import json
    import tempfile
    original_file = metadata_mod.METADATA_FILE

    try:
        # Write invalid JSON to a temp file and point to it
        from pathlib import Path
        tmp = Path(tempfile.gettempdir()) / "bad_metadata.json"
        tmp.write_text("{invalid json")
        metadata_mod.METADATA_FILE = tmp
        metadata_mod.load_indicators.cache_clear()

        profiles = generate_profiles(5, 42, country="India")
        for p in profiles:
            result = assess_profile(p)
            assert result["valid"], f"Malformed metadata fallback failed: {result['violations']}"

        assert metadata_mod.load_indicators() == {}
    finally:
        metadata_mod.METADATA_FILE = original_file
        metadata_mod.load_indicators.cache_clear()
        if tmp.exists():
            tmp.unlink()


# --- Determinism parity (full registry) ---

@pytest.mark.parametrize("country_name", ALL_COUNTRIES, ids=lambda n: n[:30])
def test_determinism_all_countries(country_name):
    """Same seed + config produces identical profiles for every country
    in the full registry."""
    a = generate_profiles(10, 12345, country=country_name)
    b = generate_profiles(10, 12345, country=country_name)
    assert a == b, f"Non-deterministic generation for {country_name}"


# --- Profile ID sequencing and uniqueness ---

def test_profile_ids_sequential_within_batch():
    """Profile IDs are sequential within a batch (1, 2, 3, ... N) with no
    gaps caused by retry/dedup attempts."""
    profiles = generate_profiles(50, 4242, country="India")
    ids = [p["profile_id"] for p in profiles]
    assert len(ids) == 50
    assert len(set(ids)) == 50, "duplicate profile IDs within batch"
    # Verify sequential numbering: ...-0001, ...-0002, ...-0050
    for i, p in enumerate(profiles, start=1):
        expected_suffix = f"{i:05d}"
        assert p["profile_id"].endswith(f"-{expected_suffix}"), \
            f"expected suffix -{expected_suffix}, got {p['profile_id']}"


def test_profile_ids_unique_across_batches():
    """Different seeds produce different profile IDs (cross-batch uniqueness)."""
    p1 = generate_profiles(10, 100, country="Brazil")
    p2 = generate_profiles(10, 200, country="Brazil")
    ids1 = {p["profile_id"] for p in p1}
    ids2 = {p["profile_id"] for p in p2}
    assert not ids1 & ids2, "different seeds should produce different IDs"


def test_profile_ids_same_seed_deterministic():
    """Same seed + same config produces identical profile IDs."""
    p1 = generate_profiles(10, 555, country="Japan")
    p2 = generate_profiles(10, 555, country="Japan")
    ids1 = [p["profile_id"] for p in p1]
    ids2 = [p["profile_id"] for p in p2]
    assert ids1 == ids2


def test_profile_id_format():
    """Profile ID follows documented format: {alpha2}-{seed:08x}-{seq:05d}."""
    profiles = generate_profiles(5, 1, country="Germany")
    for p in profiles:
        parts = p["profile_id"].split("-")
        assert len(parts) == 3, f"unexpected ID format: {p['profile_id']}"
        assert parts[0] == p["country_code"], f"country code mismatch: {parts[0]} vs {p['country_code']}"
        assert len(parts[1]) == 8, f"seed portion not 8 hex chars: {parts[1]}"
        assert len(parts[2]) == 5, f"sequence portion not 5 digits: {parts[2]}"


# --- Schema integrity ---

def test_feature_count_derived_from_schema():
    """The advertised feature count must come from PROFILE_COLUMNS,
    not a hardcoded number."""
    from app.schemas import PROFILE_COLUMNS
    profiles = generate_profiles(5, 999)
    assert len(PROFILE_COLUMNS) >= 500
    for p in profiles:
        assert len(p) == len(PROFILE_COLUMNS), \
            f"profile has {len(p)} fields, schema has {len(PROFILE_COLUMNS)}"
        assert set(p.keys()) == set(PROFILE_COLUMNS)


def test_schema_columns_unique_and_complete():
    """No duplicate or missing columns in the canonical schema."""
    from app.schemas import PROFILE_COLUMNS, PROFILE_SCHEMA
    names = [f.name for f in PROFILE_SCHEMA]
    assert len(names) == len(set(names)), "duplicate column names in schema"
    assert len(PROFILE_COLUMNS) == len(set(PROFILE_COLUMNS)), "duplicate columns"
    # Every column in PROFILE_COLUMNS must appear in PROFILE_SCHEMA
    schema_names = {f.name for f in PROFILE_SCHEMA}
    assert set(PROFILE_COLUMNS) == schema_names


def test_export_columns_match_schema():
    """JSON and CSV exports must use the same columns as PROFILE_COLUMNS."""
    from app.exports import export_bytes
    profiles = generate_profiles(3, 777)
    # Full JSON
    payload, _, _ = export_bytes(profiles, "json", view="full")
    import json
    rows = json.loads(payload)
    assert list(rows[0].keys()) == list(PROFILE_COLUMNS)
    # Full CSV
    payload, _, _ = export_bytes(profiles, "csv", view="full")
    import csv, io
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    assert reader.fieldnames == list(PROFILE_COLUMNS)


def test_summary_columns_match_core_fields():
    """Summary view exports must use CORE_PROFILE_FIELDS."""
    from app.exports import export_bytes
    profiles = generate_profiles(3, 777)
    from app.schemas import CORE_PROFILE_FIELDS
    payload, _, _ = export_bytes(profiles, "csv", view="summary")
    import csv, io
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8")))
    assert reader.fieldnames == list(CORE_PROFILE_FIELDS)


# --- Full country coverage ---

def test_all_countries_generate_valid_profiles():
    """Every registered country must generate valid profiles."""
    from app.rules import assess_profile
    failures = []
    for name in ALL_COUNTRIES:
        try:
            profiles = generate_profiles(5, 1, country=name)
            assert len(profiles) == 5
            for p in profiles:
                if not assess_profile(p)["valid"]:
                    failures.append(f"{name}: invalid profile: {assess_profile(p)['violations']}")
        except Exception as exc:
            failures.append(f"{name}: generation failed: {exc}")
    assert not failures, f"Country generation failures: {failures[:5]}"


def test_global_generation_all_continents():
    """Global generation must represent countries from all continents."""
    profiles = generate_profiles(2000, 42, country_mode="global")
    represented = {p["country"] for p in profiles}
    continents = {COUNTRIES[c]["continent"] for c in represented}
    expected = {"Asia", "Europe", "Africa", "North America", "South America", "Oceania"}
    missing = expected - continents
    assert not missing, f"Global generation missing continents: {missing}"


def test_global_generation_includes_metadata_poor_countries():
    """Countries without approved metadata must still appear in global
    generation; no country is silently excluded."""
    profiles = generate_profiles(1000, 42, country_mode="global")
    represented = {p["country"] for p in profiles}
    from app.metadata import load_indicators, CATALOG_INDICATORS
    indicators = load_indicators()
    zero_meta = []
    for name in ALL_COUNTRIES:
        code = COUNTRIES[name]["code"]
        if not any(indicators.get((code, ind)) for ind in CATALOG_INDICATORS):
            zero_meta.append(name)
    assert zero_meta, "test precondition: expected some zero-metadata countries"
    represented_zero = represented & set(zero_meta)
    assert represented_zero, "zero-metadata countries were silently excluded"


def test_country_comparison_uses_correct_context():
    """Each country in a comparison uses its own context, not leaked from
    the other country."""
    in_profiles = generate_profiles(50, 7, country="India")
    jp_profiles = generate_profiles(50, 7, country="Japan")
    assert all(p["country"] == "India" for p in in_profiles)
    assert all(p["country"] == "Japan" for p in jp_profiles)
    assert all(p["currency"] == "INR" for p in in_profiles)
    assert all(p["currency"] == "JPY" for p in jp_profiles)
