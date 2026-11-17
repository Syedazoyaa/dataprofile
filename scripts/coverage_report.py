"""Generate the human-readable coverage report from the reference snapshot.

Reads data/reference/coverage_matrix.json and writes reports/coverage_report.md
with per-indicator evidence coverage across all 193 supported countries.

Run: python scripts/coverage_report.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "data" / "reference" / "coverage_matrix.json"
OUT = ROOT / "reports" / "coverage_report.md"


def main() -> None:
    data = json.loads(SNAP.read_text(encoding="utf-8"))
    summary = data["summary"]
    countries = data["countries"]
    cov = data["coverage"]

    lines = [
        "# Raven reference-data coverage report",
        "",
        f"Countries: {len(countries)} (all supported). Snapshot retrieved 2026-11-17 from the World Bank WDI API.",
        "",
        "Statuses: **verified** = direct country observation; **estimated** = documented model on verified inputs;",
        "**reference_only** = context, never a generation prior; **missing** = no defensible value (documented fallback applies).",
        "",
        "## Indicator coverage",
        "",
        "| Indicator | verified | estimated | reference_only | missing | oldest year | newest year |",
        "|---|---|---|---|---|---|---|",
    ]
    for ind, s in sorted(summary.items(), key=lambda kv: -kv[1]["verified"]):
        lines.append(
            f"| {ind} | {s['verified']} | {s['estimated']} | {s['reference_only']} "
            f"| {s['missing']} | {s['oldest_reference_year']} | {s['newest_reference_year']} |"
        )
    lines += ["", "## Per-country evidence counts (top/bottom)", ""]
    counts = []
    for code, c in cov.items():
        st = Counter(v.get("status", "missing") for v in c.values())
        counts.append((code, st.get("verified", 0), st.get("reference_only", 0), st.get("missing", 0)))
    counts.sort(key=lambda t: (-t[1], t[0]))
    lines += ["| Code | verified | reference_only | missing |", "|---|---|---|---|"]
    for code, v, r, m in counts[:10]:
        lines.append(f"| {code} | {v} | {r} | {m} |")
    lines.append("| ... | | | |")
    for code, v, r, m in counts[-5:]:
        lines.append(f"| {code} | {v} | {r} | {m} |")
    total_verified = sum(c[1] for c in counts)
    lines += [
        "",
        f"Total verified country-indicator observations: **{total_verified}** across "
        f"{len(counts)} countries and {len(summary)} tracked indicators.",
        "",
        "Vatican City (VAT) has no World Bank data (not a member): all its indicators are",
        "explicitly `missing` and every generator accessor falls back to the documented legacy model.",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines); {total_verified} verified observations")


if __name__ == "__main__":
    main()
