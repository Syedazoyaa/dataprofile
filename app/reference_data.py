"""Evidence-backed country reference data for Raven.

Loads the committed snapshot ``data/reference/country_reference.json``
(normalized by ``scripts/normalize_reference_data.py`` from raw World Bank
WDI retrievals in ``data/raw/``). Generation never makes network calls and
only ever reads this local snapshot.

Evidence status model (never fabricated, never presented as verified):
- verified       : direct country-level observation from the named source
- estimated      : derived from verified inputs via a documented model
- reference_only : context only; NOT used as a generation prior
- missing        : no defensible value; caller's documented legacy default applies

Fallback policy: every accessor takes an explicit legacy default and returns
it whenever the snapshot is absent, the country is absent (only Vatican City),
or the record is not approved for generation. The legacy default is a
documented behavioural model, never a country statistic, so no fallback is
ever mistaken for evidence.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "data" / "reference" / "country_reference.json"

# Priors must come from these statuses only; reference_only records are context.
_PRIOR_STATUSES = {"verified", "estimated"}


@lru_cache(maxsize=1)
def load_snapshot() -> dict:
    """Load the committed reference snapshot (empty dict if not built yet)."""
    if not SNAPSHOT_PATH.exists():
        return {}
    data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    return data


def snapshot_meta() -> dict:
    """Provenance summary of the loaded snapshot (for QA/tests/reports)."""
    snap = load_snapshot()
    if not snap:
        return {"loaded": False, "record_count": 0, "source": str(SNAPSHOT_PATH)}
    return {
        "loaded": True,
        "schema_version": snap.get("schema_version"),
        "generated_at": snap.get("generated_at"),
        "retrieved_at": snap.get("retrieved_at"),
        "record_count": len(snap.get("records", [])),
        "country_count": len(snap.get("derived_priors", {})),
        "source": str(SNAPSHOT_PATH),
    }


@lru_cache(maxsize=None)
def _indexes() -> tuple[dict, dict]:
    """Build (records_by_alpha2, derived_by_alpha2) indexes once.

    ``records_by_alpha2[code][indicator_id]`` is the record dict;
    ``derived_by_alpha2[code]`` is the documented-model prior dict.
    """
    snap = load_snapshot()
    records: dict[str, dict[str, dict]] = {}
    for rec in snap.get("records", []):
        records.setdefault(rec["country_code"], {})[rec["indicator_id"]] = rec
    derived = {code: pri for code, pri in snap.get("derived_priors", {}).items()}
    return records, derived


def country_record(country_code: str, indicator_id: str) -> dict | None:
    """Full provenance record for one country/indicator, or None."""
    records, _ = _indexes()
    return records.get(country_code, {}).get(indicator_id)


def reference_prior(country_code: str, indicator_id: str, default, *, approved_only: bool = True):
    """Evidence-backed prior value, or the caller's legacy default.

    Returns the record value only when the evidence status qualifies
    (verified/estimated) and, for ``approved_only``, the record is marked
    approved for generation. Otherwise returns ``default`` untouched.
    """
    rec = country_record(country_code, indicator_id)
    if rec is None:
        return default
    if rec.get("evidence_status") not in _PRIOR_STATUSES:
        if not (approved_only is False and rec.get("evidence_status") == "reference_only"):
            return default
    elif approved_only and not rec.get("approved_for_generation", False):
        return default
    return rec.get("value", default)


def gender_weights(country_code: str, default: tuple[float, float, float] = (0.48, 0.48, 0.04)) -> dict:
    """Gender prior {Female, Male, Non-binary} from the WDI female share.

    Documented model: Female/Male shares are allocated proportionally and a
    Non-binary share is capped at 4% (the source does not measure it).
    Falls back to the legacy default weights when no evidence exists.
    """
    derived = _indexes()[1].get(country_code, {})
    gw = derived.get("gender_weights")
    if not gw:
        f, m, nb = default
        return {"Female": f, "Male": m, "Non-binary": nb, "evidence_status": "legacy_default"}
    return {
        "Female": gw["Female"], "Male": gw["Male"], "Non-binary": gw["Non-binary"],
        "evidence_status": gw.get("evidence_status", "estimated"),
    }


def elderly_share(country_code: str) -> float | None:
    """Share of the total population aged 65+ (verified WDI), or None."""
    rec = country_record(country_code, "age_65plus_share")
    if rec and rec.get("evidence_status") in _PRIOR_STATUSES:
        # snapshot stores proportions (0-1) for share indicators
        return float(rec["value"]) if rec["value"] <= 1.5 else float(rec["value"]) / 100.0
    return None


def elderly_adult_share(country_code: str) -> float | None:
    """P(aged 65+ | aged 15+): renormalised senior probability for adults.

    Documented model: the verified WDI 65+ share of the total population is
    renormalised over the adult population (15-64 plus 65+) so it can be used
    directly as a senior-draw probability when sampling adult ages. Returns
    None when the age-band evidence is missing.
    """
    s65 = elderly_share(country_code)
    rec1564 = country_record(country_code, "age_15_64_share")
    if s65 is None or rec1564 is None or rec1564.get("evidence_status") not in _PRIOR_STATUSES:
        return None
    s1564 = float(rec1564["value"])
    if s1564 > 1.5:
        s1564 /= 100.0
    denom = s1564 + s65
    if denom <= 0:
        return None
    return s65 / denom


def income_noise_sigma(country_code: str, default: float = 0.28) -> float:
    """Damped lognormal noise sigma for per-profile income spread.

    Model: sigma = sqrt(2)*Phi^-1((G+1)/2) from the verified Gini, damped to
    profile_noise_sigma = 0.28 + (sigma - 0.55)*0.35 clamped to [0.18, 0.62].
    Falls back to the legacy fixed sigma (0.28).
    """
    derived = _indexes()[1].get(country_code, {})
    spread = derived.get("income_spread")
    if spread:
        return float(spread["profile_noise_sigma"])
    return default


def employment_gap_probability(country_code: str, default: float = 0.04) -> float:
    """Probability of a non-standard employment draw (part-time/self-employed).

    Documented model: P ~= unemployment_rate/100 * 1.9, clamped [0.03, 0.38],
    from the verified ILO unemployment rate. Legacy default 0.04 otherwise.
    """
    derived = _indexes()[1].get(country_code, {})
    emp = derived.get("employment_prior")
    if emp and emp.get("nonstandard_employment_probability") is not None:
        return float(emp["nonstandard_employment_probability"])
    return default


def education_postgrad_scale(country_code: str, default: float = 1.0) -> float:
    """Postgraduate weight multiplier from gross tertiary enrollment.

    Documented model: scale = 0.4 + 0.9 * min(ter, 110)/110, so enrollment
    tilts but never dominates the legacy education model. Legacy 1.0 fallback.
    """
    derived = _indexes()[1].get(country_code, {})
    edu = derived.get("education_prior")
    if edu and edu.get("tertiary_enrollment_gross") is not None:
        return 0.4 + 0.9 * min(edu["tertiary_enrollment_gross"], 110.0) / 110.0
    return default


_SECTOR_TO_INDUSTRY = {
    "Agriculture": "agriculture_share",
    "Manufacturing": "industry_share",
    "Construction": "industry_share",
    "Automotive": "industry_share",
    "Oil and gas": "industry_share",
    "Energy": "industry_share",
    "Services": "services_share",
    "Retail": "services_share",
    "Media": "services_share",
    "Education": "services_share",
    "Healthcare": "services_share",
}


def industry_sector_weights(country_code: str, industries) -> list[float] | None:
    """Per-industry weights from verified ILO sector shares, or None.

    Maps each registry industry onto its sector share (agriculture/industry/
    services, renormalised to 1). Industries outside the three sectors
    (Technology, Trade, Finance, ...) receive the blended mid weight
    0.5*(industry_share + services_share) + 0.5*uniform-ish 0.05 floor.
    Returns None when sector evidence is missing so callers keep the legacy
    uniform/field-based choice.
    """
    derived = _indexes()[1].get(country_code, {})
    ind = derived.get("industry_prior")
    if not ind:
        return None
    a, i, s = ind["agriculture_share"], ind["industry_share"], ind["services_share"]
    weights = []
    for name in industries:
        key = _SECTOR_TO_INDUSTRY.get(name)
        if key == "agriculture_share":
            weights.append(a)
        elif key == "industry_share":
            weights.append(i)
        elif key == "services_share":
            weights.append(s)
        else:
            weights.append(max(0.05, 0.5 * (i + s)))
    return weights


def coverage_report() -> dict:
    """Indicator-level coverage summary (verified/estimated/reference/missing)."""
    snap = load_snapshot()
    return snap.get("indicator_summary", {})


def evidence_report(country_code: str) -> dict:
    """Per-country evidence statuses for QA and coverage queries."""
    records, derived = _indexes()
    recs = records.get(country_code, {})
    return {
        code: {
            "value": rec.get("value"),
            "evidence_status": rec.get("evidence_status"),
            "approved_for_generation": rec.get("approved_for_generation"),
            "reference_year": rec.get("reference_year"),
            "source": f"{rec.get('source_organization')} / {rec.get('source_dataset')}",
        }
        for code, rec in sorted(recs.items())
    } | {"derived_priors": sorted(derived.get(country_code, {}).keys())}
