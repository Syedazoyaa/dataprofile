"""Evidence-backed country indicator metadata for Raven.

Loads the committed `data/metadata/country_indicator_records.json` snapshot
(validated against the starter-kit schema) and exposes approved reference
values to the generator. Legacy `geography_world.py` values remain the
default; only records with `approved_for_generation=true` override a legacy
context value.

Runtime properties:
- No Firecrawl or network access at generation/startup; only a committed JSON
  snapshot is read.
- Fail-safe: a missing or invalid metadata file yields an empty mapping so the
  service degrades to legacy geography values instead of crashing.
- Package-relative path: independent of the caller's working directory.
- Loaded once and cached (lru_cache) so per-profile generation is O(1).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

METADATA_FILE = Path(__file__).resolve().parent.parent / "data" / "metadata" / "country_indicator_records.json"


@lru_cache(maxsize=1)
def load_indicators() -> dict[tuple[str, str], dict[str, Any]]:
    """Return {(country_code, indicator_id): record} for all committed records.

    Fail-safe: a missing or invalid metadata file yields an empty mapping so
    the service degrades to legacy geography values instead of crashing.
    """
    try:
        text = METADATA_FILE.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    records = payload.get("records", []) if isinstance(payload, dict) else []
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        code = record.get("country_code")
        indicator = record.get("indicator_id")
        if isinstance(code, str) and isinstance(indicator, str):
            index[(code.upper(), indicator)] = record
    return index


def get_indicator(country_code: str, indicator_id: str) -> dict[str, Any] | None:
    """Return the committed record for a country + indicator, or None."""
    return load_indicators().get((str(country_code).upper(), str(indicator_id)))


def approved_value(country_code: str, indicator_id: str, default: Any = None) -> Any:
    """Return the sourced value if an approved record exists, else default.

    Only records with `approved_for_generation=true` are consumed; unapproved
    records remain reference-only and never change generated output.
    """
    record = get_indicator(country_code, indicator_id)
    if record is not None and record.get("approved_for_generation") is True:
        return record.get("value")
    return default


# Prioritized indicator catalog (mirrors the starter-kit indicator_catalog.json
# indicator ids). Used to compute metadata coverage independent of the
# generated-sample statistics.
CATALOG_INDICATORS = (
    "population_age_distribution",
    "urban_population_share",
    "internet_use_share",
    "income_distribution",
    "income_inequality_gini",
    "gdp_per_capita_usd",
    "education_distribution",
    "household_structure_distribution",
    "financial_inclusion_and_digital_payments",
    "transport_mode_distribution",
    "consumer_channel_usage",
    "media_platform_usage",
)

STATUS_APPROVED = "approved"
STATUS_REFERENCE = "reference"
STATUS_UNAVAILABLE = "unavailable"


def coverage_for_country(country_code: str) -> dict[str, dict[str, Any]]:
    """Coverage status for every catalog indicator for one country.

    Returns {indicator_id: {status, evidence_status, approved_for_generation,
    reference_year, value, unit}} where status is one of
    STATUS_APPROVED / STATUS_REFERENCE / STATUS_UNAVAILABLE.
    """
    code = str(country_code).upper()
    out: dict[str, dict[str, Any]] = {}
    for indicator_id in CATALOG_INDICATORS:
        record = get_indicator(code, indicator_id)
        if record is None:
            out[indicator_id] = {
                "status": STATUS_UNAVAILABLE,
                "evidence_status": None,
                "approved_for_generation": False,
                "reference_year": None,
                "value": None,
                "unit": None,
            }
        else:
            out[indicator_id] = {
                "status": STATUS_APPROVED if record.get("approved_for_generation") is True else STATUS_REFERENCE,
                "evidence_status": record.get("evidence_status"),
                "approved_for_generation": bool(record.get("approved_for_generation")),
                "reference_year": record.get("reference_year"),
                "value": record.get("value"),
                "unit": record.get("unit"),
            }
    return out
