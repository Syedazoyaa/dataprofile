"""Refresh country income anchors from World Bank GNI per capita (current LCU).

The generator models income ranges around each country's ``income`` field in
``app/geography_world.py``.  This script updates that field from the latest
available ``NY.GNP.PCAP.CN`` observations acquired by
``acquire_reference_data.py``.  GNI per capita is a consistent national-income
anchor in each country's own currency, not a median wage; the generator's
career, education, and inequality factors continue to determine the range.

Usage:
    python scripts/acquire_reference_data.py NY.GNP.PCAP.CN
    python scripts/refresh_income_scales.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "wdi_income_scale.csv"
REGISTRY = ROOT / "app" / "geography_world.py"
INDICATOR = "NY.GNP.PCAP.CN"


def _latest_gni_by_alpha3() -> dict[str, int]:
    if not RAW.exists():
        raise FileNotFoundError(
            f"{RAW} is missing. Run `python scripts/acquire_reference_data.py {INDICATOR}` first."
        )
    values: dict[str, int] = {}
    for line in RAW.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) != 3 or len(parts[0]) != 3:
            continue
        alpha3, value, _year = parts
        income = round(float(value))
        if income > 0:
            values[alpha3] = income
    if not values:
        raise ValueError(f"No {INDICATOR} observations found in {RAW}.")
    return values


def refresh(*, dry_run: bool = False) -> tuple[int, int]:
    values = _latest_gni_by_alpha3()
    text = REGISTRY.read_text(encoding="utf-8")
    registry_codes = set(re.findall(r"'alpha3': '([A-Z]{3})'", text))
    seen: set[str] = set()

    # Every registry record occupies one line.  Match the ISO-3 code and its
    # later income value together so only the intended anchor is changed.
    pattern = re.compile(r"('alpha3': '([A-Z]{3})'.*?'income': )(\d+)")

    def replace(match: re.Match[str]) -> str:
        prefix, alpha3, old = match.groups()
        new = values.get(alpha3)
        if new is None:
            return match.group(0)
        seen.add(alpha3)
        return f"{prefix}{new}"

    updated = pattern.sub(replace, text)
    changed = sum(1 for alpha3 in seen if re.search(
        rf"'alpha3': '{re.escape(alpha3)}'.*?'income': (\d+)", text
    ).group(1) != str(values[alpha3]))
    if not dry_run:
        REGISTRY.write_text(updated, encoding="utf-8", newline="\n")
    return changed, len(registry_codes - seen)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    changed, unavailable = refresh(dry_run=args.dry_run)
    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {changed} country income scales from {INDICATOR}.")
    print(f"Retained legacy values for {unavailable} countries without an observation.")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
