"""Reproducible acquisition of the World Bank WDI reference data (Raven).

Fetches every indicator used by the reference snapshot from the World Bank
API (CC BY 4.0) and writes the raw CSVs consumed by
``scripts/normalize_reference_data.py`` into ``data/raw/``.

Run where outbound HTTPS is available (this repo's original acquisition ran
through an allow-listed fetch harness because the local shell had no network):

    python scripts/acquire_reference_data.py            # all indicators
    python scripts/acquire_reference_data.py IT.NET.USER.ZS   # one indicator

Output formats (both are parsed by the normalizer):
  - compact   '# indicator: name (WDI_ID, ...)' header + 'CC|value|year' rows
  - labelled  'CC|WDI_ID|value|year' rows

Notes
-----
- ``mrnev=1`` asks for the most recent non-empty value (needed for sparse
  series such as IT.NET.USER.ZS); ``mrv=1`` gives latest-year-only rows.
- The API intermittently returns 502; this script retries with a cache-busting
  ``attempt`` parameter (the same trick used during the original retrieval).
- Aggregates (AFE, AFW, WLD, CHI, XKX, OSS, PST, ...) are filtered out by
  joining against the 193-country registry in ``app/geography_world.py``.
- Indicators that failed repeatedly during the original pass (EG.ELC.ACC.ZS,
  SE.SEC.ENRR, SL.GDP.PCAP.EM.KD) and datasets that were time-boxed out
  (UN DESA household/marital data, Findex, Barro-Lee attainment, religion and
  language shares) are retried here and otherwise remain explicit `missing`
  entries in the coverage matrix with their planned sources.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.geography_world import COUNTRIES_WORLD  # noqa: E402

RAW = ROOT / "data" / "raw"
RETRIEVED = time.strftime("%Y-%m-%d")

# indicator_id -> (friendly_name, unit_note, compact_output_file)
INDICATORS = {
    "SP.POP.TOTL":        ("population_total", "persons", "wdi_SP.POP.TOTL.csv"),
    "SP.POP.TOTL.FE.ZS":  ("female_population_share", "% of total", "wdi_batch1.csv"),
    "SP.POP.0014.TO.ZS":  ("age_0_14_share", "% of total", "wdi_batch1.csv"),
    "SP.POP.1564.TO.ZS":  ("age_15_64_share", "% of total", "wdi_batch2.csv"),
    "SP.POP.65UP.TO.ZS":  ("age_65plus_share", "% of total", "wdi_batch1.csv"),
    "SP.URB.TOTL.IN.ZS":  ("urban_population_share", "% of total", "wdi_batch1.csv"),
    "IT.NET.USER.ZS":     ("internet_use_share", "% of population", "wdi_batch2.csv"),
    "IT.CEL.SETS.P2":     ("mobile_subscriptions_per100", "per 100 people", "wdi_batch2.csv"),
    "IT.NET.BBND.P2":     ("fixed_broadband_per100", "per 100 people", "wdi_batch3.csv"),
    "NY.GDP.PCAP.CD":     ("gdp_per_capita_usd_nominal", "current US$", "wdi_batch3.csv"),
    "NY.GDP.PCAP.PP.CD":  ("gdp_per_capita_ppp_intld", "current international $", "wdi_batch3.csv"),
    "SI.POV.GINI":        ("income_inequality_gini", "0-100", "wdi_batch4.csv"),
    "SL.UEM.TOTL.ZS":     ("unemployment_rate", "% of labour force", "wdi_batch4.csv"),
    "SL.TLF.CACT.ZS":     ("labour_force_participation", "% of pop 15+", "wdi_batch4.csv"),
    "SL.AGR.EMPL.ZS":     ("employment_agri_share", "% of employment", "wdi_batch4.csv"),
    "SL.IND.EMPL.ZS":     ("employment_industry_share", "% of employment", "wdi_batch4.csv"),
    "SL.SRV.EMPL.ZS":     ("employment_services_share", "% of employment", "wdi_batch4.csv"),
    "SE.ADT.LITR.ZS":     ("adult_literacy_rate", "% of adults 15+", "wdi_batch4.csv"),
    "SE.TER.ENRR":        ("tertiary_enrollment_gross", "% of cohort", "wdi_batch4.csv"),
    # Failed in the original pass; retried here before being marked missing.
    "EG.ELC.ACC.ZS":      ("electricity_access", "% of population", "wdi_batch5.csv"),
    "SE.SEC.ENRR":        ("secondary_education_enrollment", "% of cohort", "wdi_batch5.csv"),
    "SL.GDP.PCAP.EM.KD":  ("gdp_per_worker", "constant 2021 US$", "wdi_batch5.csv"),
}

# Datasets time-boxed out of the original acquisition (explicit `missing` in
# the snapshot; planned sources documented in source_catalogue.json).
PLANNED = {
    "education_attainment_distribution": "Barro-Lee v3.0 (barrolee.com) or WCDE v9",
    "household_size_and_composition": "UN DESA Household Size & Composition 2022",
    "marital_status_distribution": "UN DESA World Marriage Data",
    "religion_affiliation_distribution": "Pew Research Center Global Religious Landscape",
    "language_distribution": "National census language tables",
    "housing_tenure_distribution": "National housing censuses; UN-Habitat",
    "transport_mode_distribution": "National travel surveys",
    "payment_method_adoption": "Global Findex Database (World Bank) CSV",
    "consumer_channel_usage": "UNCTAD e-commerce estimates",
    "media_platform_usage": "Provider supported-country documentation",
}

API = "https://api.worldbank.org/v2/country/all/indicator/{ind}?format=json&per_page=20000&mrnev=1"


def registry_codes() -> set[str]:
    return {v["alpha3"] for v in COUNTRIES_WORLD.values()}


def fetch(indicator: str, attempts: int = 4) -> list[dict]:
    url = API.format(ind=indicator)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(f"{url}&attempt={attempt}", headers={"User-Agent": "dataprofile-raven/2.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return payload[1] or []
        except Exception as exc:  # noqa: BLE001 - API is flaky; retry
            last_error = exc
            time.sleep(2 * attempt)
    raise RuntimeError(f"World Bank API failed for {indicator}: {last_error}")


def main() -> None:
    wanted = set(sys.argv[1:]) or set(INDICATORS)
    keep = registry_codes()
    RAW.mkdir(parents=True, exist_ok=True)

    by_file: dict[str, list[str]] = {}
    for ind, (name, unit, fname) in INDICATORS.items():
        if ind not in wanted:
            continue
        rows = fetch(ind)
        lines = [
            f"# World Bank WDI API, mrnev=1, retrieved {RETRIEVED}",
            f"# indicator: {name} ({ind}, {unit})",
        ]
        n = 0
        for row in rows:
            iso3 = row.get("countryiso3code", "")
            if iso3 not in keep or row.get("value") is None:
                continue
            year = row.get("date", "")
            value = row["value"]
            lines.append(f"{iso3}|{value}|{year}")
            n += 1
        by_file.setdefault(fname, []).extend(lines)
        print(f"{ind:18s} -> {fname}: {n} countries")

    for fname, lines in by_file.items():
        path = RAW / fname
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if existing and fname in {"wdi_batch1.csv", "wdi_batch2.csv", "wdi_batch3.csv", "wdi_batch4.csv"}:
            # append updated sections for refresh runs
            path.write_text(existing.rstrip("\n") + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
        else:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {path}")

    print("\nTime-boxed-out datasets (explicit `missing`, planned sources):")
    for name, src in PLANNED.items():
        print(f"  {name:38s} {src}")
    print("\nNext step: python scripts/normalize_reference_data.py")


if __name__ == "__main__":
    main()
