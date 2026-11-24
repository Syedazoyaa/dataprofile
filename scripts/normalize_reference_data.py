"""Normalize acquired raw reference data into the versioned reference snapshot.

Reads data/raw/*.csv (produced by scripts/acquire_reference_data.py) and writes:
- data/reference/country_reference.json  (per-country, per-indicator records with provenance)
- data/reference/coverage_matrix.json    (193 countries x all indicators, explicit status)
- data/reference/source_catalogue.json   (sources, licences, retrieval metadata)

Status model (explicit, never fabricated):
- verified       : direct observation for this country from the named source
- estimated      : derived from verified inputs via a documented model
- reference_only : useful context, not approved as a generation prior
- missing        : no defensible value acquired

Run:  python scripts/normalize_reference_data.py
"""
from __future__ import annotations

import json
import math
import re
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "reference"
OUT.mkdir(parents=True, exist_ok=True)

RETRIEVED = "2026-11-17"
WB_BASE = "https://api.worldbank.org/v2/country/all/indicator/{id}?format=json&per_page=400&mrnev=1"

# (file, wdi_id, indicator_id, unit, org, dataset, licence, approved, status, limitations)
SOURCES = [
    ("wdi_SP.POP.TOTL.csv", "SP.POP.TOTL", "population_total", "persons",
     "World Bank", "World Development Indicators", "CC BY 4.0", False, "verified",
     ["National total population; not an individual-level prior."]),
    ("wdi_batch1.csv", "SP.POP.TOTL.FE.ZS", "female_population_share", "percent",
     "World Bank", "World Development Indicators (UN WPP based)", "CC BY 4.0", True, "verified",
     ["Total-population female share; individuals may differ; used only as a probabilistic prior."]),
    ("wdi_batch1.csv", "SP.POP.0014.TO.ZS", "age_0_14_share", "percent",
     "World Bank", "World Development Indicators (UN WPP based)", "CC BY 4.0", True, "verified",
     ["Coarse 3-band age structure; adult age sampling is interpolated from bands (documented model)."]),
    ("wdi_batch2.csv", "SP.POP.1564.TO.ZS", "age_15_64_share", "percent",
     "World Bank", "World Development Indicators (UN WPP based)", "CC BY 4.0", True, "verified",
     ["Coarse 3-band age structure; adult age sampling is interpolated from bands (documented model)."]),
    ("wdi_batch1.csv", "SP.POP.65UP.TO.ZS", "age_65plus_share", "percent",
     "World Bank", "World Development Indicators (UN WPP based)", "CC BY 4.0", True, "verified",
     ["Coarse 3-band age structure; adult age sampling is interpolated from bands (documented model)."]),
    ("wdi_batch1.csv", "SP.URB.TOTL.IN.ZS", "urban_population_share", "proportion_0_1",
     "World Bank", "World Development Indicators", "CC BY 4.0", True, "verified",
     ["National urban boundary share, not an individual urban/rural assignment."]),
    ("wdi_batch2.csv", "IT.NET.USER.ZS", "internet_use_share", "proportion_0_1",
     "World Bank / ITU", "World Development Indicators (ITU)", "CC BY 4.0", True, "verified",
     ["Share of individuals using the internet; digital_access maps to this prior."]),
    ("wdi_batch2.csv", "IT.CEL.SETS.P2", "mobile_subscriptions_per100", "per_100_people",
     "World Bank / ITU", "World Development Indicators (ITU)", "CC BY 4.0", True, "verified",
     ["SIM subscriptions can exceed 100; used as device-access context, not ownership proof."]),
    ("wdi_batch3.csv", "IT.NET.BBND.P2", "fixed_broadband_per100", "per_100_people",
     "World Bank / ITU", "World Development Indicators (ITU)", "CC BY 4.0", False, "reference_only",
     ["Fixed subscriptions, not individual usage; reference context only."]),
    ("wdi_batch3.csv", "NY.GDP.PCAP.CD", "gdp_per_capita_usd_nominal", "current_usd",
     "World Bank", "World Development Indicators", "CC BY 4.0", False, "reference_only",
     ["GDP per capita is not personal income; never used as a salary."]),
    ("wdi_batch3.csv", "NY.GDP.PCAP.PP.CD", "gdp_per_capita_ppp_intld", "current_intl_usd",
     "World Bank", "World Development Indicators", "CC BY 4.0", False, "verified",
     ["GDP per capita is not personal income; used only to rank and sanity-check income scales."]),
    ("wdi_income_scale.csv", "NY.GNP.PCAP.CN", "gni_per_capita_lcu", "current_lcu",
     "World Bank", "World Development Indicators", "CC BY 4.0", False, "reference_only",
     ["Gross national income per capita in current local currency. It is a national-income "
      "anchor, not a wage or median-salary estimate; used to refresh the model's local income scale."]),
    ("wdi_batch4.csv", "SI.POV.GINI", "income_inequality_gini", "gini_0_100",
     "World Bank", "World Development Indicators (PIP)", "CC BY 4.0", True, "verified",
     ["Survey-based; reference years vary; converted to a damped lognormal spread (documented model)."]),
    ("wdi_batch4.csv", "SL.UEM.TOTL.ZS", "unemployment_rate", "percent_of_labour_force",
     "World Bank / ILO", "World Development Indicators (ILO modelled)", "CC BY 4.0", True, "verified",
     ["ILO modelled estimate; working-age adults only; used as a probabilistic prior."]),
    ("wdi_batch4.csv", "SL.TLF.CACT.ZS", "labour_force_participation", "percent_pop_15plus",
     "World Bank / ILO", "World Development Indicators (ILO modelled)", "CC BY 4.0", True, "verified",
     ["Population 15+, both sexes; individuals may differ."]),
    ("wdi_batch4.csv", "SL.AGR.EMPL.ZS", "employment_agri_share", "percent_of_employment",
     "World Bank / ILO", "World Development Indicators (ILO modelled)", "CC BY 4.0", True, "verified",
     ["Sector shares inform industry priors; not an individual assignment."]),
    ("wdi_batch4.csv", "SL.IND.EMPL.ZS", "employment_industry_share", "percent_of_employment",
     "World Bank / ILO", "World Development Indicators (ILO modelled)", "CC BY 4.0", True, "verified",
     ["Sector shares inform industry priors; not an individual assignment."]),
    ("wdi_batch4.csv", "SL.SRV.EMPL.ZS", "employment_services_share", "percent_of_employment",
     "World Bank / ILO", "World Development Indicators (ILO modelled)", "CC BY 4.0", True, "verified",
     ["Sector shares inform industry priors; not an individual assignment."]),
    ("wdi_batch4.csv", "SE.ADT.LITR.ZS", "adult_literacy_rate", "percent_adults_15plus",
     "World Bank / UNESCO", "World Development Indicators (UIS)", "CC BY 4.0", False, "reference_only",
     ["Reference years vary widely (some pre-2000); context only, never a generation prior."]),
    ("wdi_batch4.csv", "SE.TER.ENRR", "tertiary_enrollment_gross", "percent_of_cohort",
     "World Bank / UNESCO", "World Development Indicators (UIS)", "CC BY 4.0", True, "verified",
     ["Gross enrollment can exceed 100 (foreign students, repeats); used as a damped education tilt."]),
]

# Indicators assessed but not acquired in this pass (explicitly missing; see ledger)
MISSING_INDICATORS = {
    "education_attainment_distribution": {
        "status": "missing",
        "note": ("Barro-Lee / Wittgenstein Centre attainment files not acquired in this pass; "
                 "coarse education prior is derived from tertiary_enrollment_gross (estimated)."),
        "planned_source": "Barro-Lee v3.0 (barrolee.com) or WCDE v9; see scripts/acquire_reference_data.py",
    },
    "household_size_and_composition": {
        "status": "missing",
        "note": ("UN DESA Household Size & Composition database not acquired in this pass; "
                 "household generation remains the documented legacy model (legacy_unverified)."),
        "planned_source": "UN DESA Database on Household Size and Composition 2022",
    },
    "marital_status_distribution": {
        "status": "missing",
        "note": ("UN World Marriage Data not acquired in this pass; marital generation remains the "
                 "documented legacy model (legacy_unverified)."),
        "planned_source": "UN DESA World Marriage Data",
    },
    "religion_affiliation_distribution": {
        "status": "missing",
        "note": ("No defensible per-country religion distribution acquired in this pass; legacy registry "
                 "lists are the documented uncalibrated fallback and are NOT labelled country evidence."),
        "planned_source": "Pew Research Center Global Religious Landscape data files",
    },
    "language_distribution": {
        "status": "missing",
        "note": ("No defensible per-country language shares acquired in this pass; legacy registry language "
                 "lists are the documented fallback with dominant-first weighting (legacy_unverified)."),
        "planned_source": "National census language tables (varies by country)",
    },
    "housing_tenure_distribution": {
        "status": "missing",
        "note": "No global housing-tenure dataset acquired; legacy model retained.",
        "planned_source": "National housing censuses; UN-Habitat",
    },
    "transport_mode_distribution": {
        "status": "missing",
        "note": ("No global modal-share dataset acquired; transport options remain registry lists with "
                 "behavioural weighting (legacy_unverified)."),
        "planned_source": "National travel surveys; UITP/WHO road-safety context",
    },
    "payment_method_adoption": {
        "status": "missing",
        "note": ("World Bank Global Findex not acquired in this pass; payment priors are driven by verified "
                 "internet/mobile access plus behavioural model (documented fallback)."),
        "planned_source": "Global Findex Database (World Bank), CSV download",
    },
    "consumer_channel_usage": {
        "status": "missing",
        "note": "No defensible global e-commerce channel dataset acquired; legacy lists retained.",
        "planned_source": "UNCTAD e-commerce estimates; national statistics",
    },
    "media_platform_usage": {
        "status": "missing",
        "note": ("Platform availability is not census data; registry platform lists remain legacy_unverified "
                 "and availability claims are not made."),
        "planned_source": "Provider documentation (Netflix/Spotify etc. supported-country pages)",
    },
    "electricity_access": {
        "status": "missing",
        "note": "EG.ELC.ACC.ZS fetch failed (World Bank API 502) in this pass; see acquisition script.",
        "planned_source": "World Bank WDI EG.ELC.ACC.ZS",
    },
    "secondary_education_enrollment": {
        "status": "missing",
        "note": "SE.SEC.ENRR fetch failed in this pass; see acquisition script.",
        "planned_source": "World Bank WDI SE.SEC.ENRR",
    },
    "gdp_per_worker": {
        "status": "missing",
        "note": "SL.GDP.PCAP.EM.KD fetch failed in this pass; see acquisition script.",
        "planned_source": "World Bank WDI SL.GDP.PCAP.EM.KD",
    },
}


def load_tables() -> dict[str, dict[str, tuple[float, int]]]:
    """Scan every raw CSV and return {wdi_id: {alpha3: (value, year)}}.

    Handles both row layouts found in data/raw:
      - compact   'CC|value|year'  under a '# indicator: name (WDI_ID, ...)' header
      - labelled  'CC|WDI_ID_or_name|value|year'
    """
    tables: dict[str, dict[str, tuple[float, int]]] = {}
    for path in sorted(RAW.glob("*.csv")):
        current: str | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                m = re.search(r"#\s*indicator:.*\(([A-Z]{2,3}\.[A-Z0-9.]+)", line)
                if m:
                    current = m.group(1)
                continue
            parts = line.split("|")
            if len(parts) == 4 and len(parts[0]) == 3:
                iso3, label, value, year = parts
                # labelled rows carry either the WDI id or the friendly name
                label_key = label if re.fullmatch(r"[A-Z]{2,3}\.[A-Z0-9.]+", label) else current
                if label_key is None:
                    continue
                tables.setdefault(label_key, {})[iso3] = (float(value), int(year))
            elif len(parts) == 3 and len(parts[0]) == 3 and current:
                tables.setdefault(current, {})[parts[0]] = (float(parts[1]), int(parts[2]))
    return tables


def load_registry_codes() -> dict[str, str]:
    """alpha3 -> alpha2 from the canonical registry."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gw", ROOT / "app" / "geography_world.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {v["alpha3"]: v["code"] for v in mod.COUNTRIES_WORLD.values()}


def gini_to_sigma(gini: float) -> float:
    """Lognormal sigma whose Gini equals the input (G = 2*Phi(sigma/sqrt2) - 1)."""
    return math.sqrt(2.0) * statistics.NormalDist().inv_cdf((gini + 1.0) / 2.0)


def main() -> None:
    alpha2 = load_registry_codes()
    countries = sorted(alpha2)  # 193 alpha-3 codes

    # Load every indicator table once (single format-agnostic scan of data/raw)
    tables = load_tables()

    records: list[dict] = []
    coverage: dict[str, dict[str, dict]] = {}

    for iso3 in countries:
        code = alpha2[iso3]
        cov: dict[str, dict] = {}
        for (fname, wdi_id, ind_id, unit, org, dataset, licence, approved, status, limits) in SOURCES:
            hit = tables.get(wdi_id, {}).get(iso3)
            if hit is None:
                cov[ind_id] = {"status": "missing", "source": org, "dataset": dataset,
                               "note": f"{wdi_id} not observed for {iso3} in this retrieval"}
                continue
            value, year = hit
            # percent-based indicators whose unit is a proportion are stored
            # divided by 100 so downstream priors are always 0-1.
            if unit == "proportion_0_1" and value > 1.5:
                value = round(value / 100.0, 6)
            rec = {
                "country_code": code, "country_iso3": iso3, "indicator_id": ind_id,
                "wdi_indicator": wdi_id, "value_type": "number", "value": value,
                "unit": unit, "reference_year": year,
                "source_organization": org, "source_dataset": dataset,
                "source_url": WB_BASE.format(id=wdi_id), "licence": licence,
                "retrieved_at": RETRIEVED, "methodology_note":
                    f"{wdi_id} most-recent non-empty observation from the World Bank API.",
                "evidence_status": status, "quality_grade": "A",
                "limitations": limits, "approved_for_generation": bool(approved),
                "used_for": {
                    "female_population_share": "gender prior",
                    "age_0_14_share": "age prior (bands)",
                    "age_15_64_share": "age prior (bands)",
                    "age_65plus_share": "age prior (bands)",
                    "urban_population_share": "settlement prior",
                    "internet_use_share": "digital access prior",
                    "mobile_subscriptions_per100": "device context",
                    "income_inequality_gini": "income spread prior",
                    "unemployment_rate": "employment prior",
                    "labour_force_participation": "employment prior",
                    "employment_agri_share": "industry prior",
                    "employment_industry_share": "industry prior",
                    "employment_services_share": "industry prior",
                    "tertiary_enrollment_gross": "education prior (damped tilt)",
                }.get(ind_id, "reference context"),
            }
            records.append(rec)
            cov[ind_id] = {"status": status, "approved": bool(approved), "year": year,
                           "source": f"{org} / {dataset}"}
        for ind_id, info in MISSING_INDICATORS.items():
            cov[ind_id] = {"status": info["status"], "note": info["note"],
                           "planned_source": info["planned_source"]}
        coverage[code] = cov

    # Derived generation priors (documented models) -> separate derived section
    derived: dict[str, dict] = {}
    for iso3 in countries:
        code = alpha2[iso3]
        d: dict[str, dict] = {}
        female = tables["SP.POP.TOTL.FE.ZS"].get(iso3)
        if female:
            f = min(0.85, max(0.15, female[0] / 100.0))
            # Residual share (schema keeps a Non-binary category the source does
            # not measure) is allocated proportionally and capped.
            nb = 0.04
            f_adj = f * (1.0 - nb)
            m_adj = (1.0 - f) * (1.0 - nb)
            d["gender_weights"] = {
                "Female": round(f_adj, 4), "Male": round(m_adj, 4), "Non-binary": round(nb, 4),
                "model": "female share from WDI; Non-binary capped at 4% (source does not measure it)",
                "evidence_status": "estimated",
            }
        age0014 = tables["SP.POP.0014.TO.ZS"].get(iso3)
        age1564 = tables["SP.POP.1564.TO.ZS"].get(iso3)
        age65 = tables["SP.POP.65UP.TO.ZS"].get(iso3)
        if age65:
            d["age_prior"] = {
                "share_65plus_of_total": age65[0] / 100.0,
                "model": ("adult sampling: P(65+) within an age range is taken from the WDI 65+ share of the "
                          "total population, renormalised over the allowed range; ages below 65 uniform"),
                "evidence_status": "estimated",
                "limitations": ["Coarse 3-band source; no single-year age data acquired."],
            }
        gini = tables["SI.POV.GINI"].get(iso3)
        if gini:
            sigma = gini_to_sigma(gini[0] / 100.0)
            # Damped mapping: per-profile wage lognormal noise rises with
            # measured inequality but never doubles it.
            noise = min(0.62, max(0.18, 0.28 + (sigma - 0.55) * 0.35))
            d["income_spread"] = {
                "gini": gini[0], "gini_year": gini[1], "lognormal_sigma_gini": round(sigma, 3),
                "profile_noise_sigma": round(noise, 3),
                "model": "sigma = sqrt(2)*Phi^-1((G+1)/2); profile noise = 0.28 + (sigma-0.55)*0.35, clamped [0.18,0.62]",
                "evidence_status": "estimated",
            }
        unemp = tables["SL.UEM.TOTL.ZS"].get(iso3)
        lfpr = tables["SL.TLF.CACT.ZS"].get(iso3)
        if unemp:
            d["employment_prior"] = {
                "unemployment_rate": unemp[0], "unemployment_year": unemp[1],
                "labour_force_participation": lfpr[0] if lfpr else None,
                "nonstandard_employment_probability": round(
                    min(0.38, max(0.03, (unemp[0] / 100.0) * 1.9)), 4),
                "model": "P(non standard employment) ~ unemployment*1.9 clamped [0.03,0.38]; estimated",
                "evidence_status": "estimated",
            }
        agri = tables["SL.AGR.EMPL.ZS"].get(iso3)
        ind = tables["SL.IND.EMPL.ZS"].get(iso3)
        serv = tables["SL.SRV.EMPL.ZS"].get(iso3)
        if agri and ind and serv:
            a, i, s = agri[0], ind[0], serv[0]
            tot = max(a + i + s, 0.01)
            d["industry_prior"] = {
                "agriculture_share": round(a / tot, 4), "industry_share": round(i / tot, 4),
                "services_share": round(s / tot, 4), "year": max(agri[1], ind[1], serv[1]),
                "model": "ILO sector shares renormalised to 1; mapped onto registry industry lists",
                "evidence_status": "estimated",
            }
        ter = tables["SE.TER.ENRR"].get(iso3)
        if ter:
            d["education_prior"] = {
                "tertiary_enrollment_gross": ter[0], "year": ter[1],
                "model": "postgraduate weight scaled by (0.4 + 0.9*min(ter,110)/110), clamped; estimated",
                "evidence_status": "estimated",
            }
        if d:
            derived[code] = d

    # Coverage summary per indicator
    summary: dict[str, dict] = {}
    all_ind = [s[2] for s in SOURCES] + list(MISSING_INDICATORS)
    for ind_id in all_ind:
        counts = defaultdict(int)
        years = []
        for code, cov in coverage.items():
            st = cov.get(ind_id, {}).get("status", "missing")
            counts[st] += 1
            y = cov.get(ind_id, {}).get("year")
            if y:
                years.append(y)
        summary[ind_id] = {
            "verified": counts["verified"], "estimated": counts["estimated"],
            "reference_only": counts["reference_only"], "missing": counts["missing"],
            "total_countries": len(countries),
            "oldest_reference_year": min(years) if years else None,
            "newest_reference_year": max(years) if years else None,
        }

    OUT.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "schema_version": "2.0",
        "generated_at": date.today().isoformat(),
        "retrieved_at": RETRIEVED,
        "purpose": ("Versioned evidence-backed country reference data for Raven. Statuses are explicit; "
                    "missing evidence is never presented as verified; legacy geography_world.py values "
                    "remain documented fallbacks."),
        "records": records,
        "derived_priors": derived,
        "indicator_summary": summary,
    }
    (OUT / "country_reference.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    (OUT / "coverage_matrix.json").write_text(
        json.dumps({"countries": countries, "indicators": all_ind, "coverage": coverage,
                    "summary": summary}, ensure_ascii=False), encoding="utf-8")
    (OUT / "source_catalogue.json").write_text(json.dumps({
        "world_bank": {
            "organization": "World Bank", "dataset": "World Development Indicators",
            "url": "https://api.worldbank.org/v2/",
            "licence": "CC BY 4.0 (attribution required; redistribution permitted)",
            "retrieved_at": RETRIEVED,
            "indicators": [s[1] for s in SOURCES],
            "limitations": ["Modelled ILO/ITU/UIS estimates where the underlying survey is not national.",
                            "Vatican City (VAT) and PRK rows absent from some series."],
        },
        "not_acquired_this_pass": {k: v["planned_source"] for k, v in MISSING_INDICATORS.items()},
        "policy": ("Acquisition is reproducible via scripts/acquire_reference_data.py; generation never "
                   "makes network calls and reads only this committed snapshot."),
    }, ensure_ascii=False), encoding="utf-8")

    n_rec = len(records)
    print(f"records={n_rec} countries={len(countries)} indicators={len(all_ind)}")
    for ind_id, s in summary.items():
        print(f"{ind_id:38s} verified={s['verified']:3d} est={s['estimated']:3d} "
              f"ref={s['reference_only']:3d} missing={s['missing']:3d}")


if __name__ == "__main__":
    main()
