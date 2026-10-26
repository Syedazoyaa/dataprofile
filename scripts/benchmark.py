"""Reproducible local benchmark for Raven's CPU-bound in-memory paths.

Run from the repository root:
    python scripts/benchmark.py

It deliberately reports generation separately from analytics and exports. The
script does not call HTTP, write files, or make claims about network latency.
"""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median
import sys
import time
import tracemalloc

# Make the script runnable both as ``python scripts/benchmark.py`` and from
# test tooling that has not installed this repository as a package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analytics import compute_analytics
from app.exports import export_bytes
from app.generator import generate_profiles

BATCH_SIZES = (1, 10, 100, 500, 2000)
TRIALS = 3
SEED = 90210


def _seconds(operation):
    started = time.perf_counter()
    result = operation()
    return time.perf_counter() - started, result


def benchmark(batch_size: int) -> dict[str, float | int]:
    trials = []
    for trial in range(TRIALS):
        generation_seconds, profiles = _seconds(
            lambda: generate_profiles(batch_size, SEED + trial, country_mode="global")
        )
        analytics_seconds, _ = _seconds(lambda: compute_analytics(profiles))
        json_seconds, json_payload = _seconds(lambda: export_bytes(profiles, "json"))
        csv_seconds, csv_payload = _seconds(lambda: export_bytes(profiles, "csv"))
        trials.append({
            "generation_seconds": generation_seconds,
            "analytics_seconds": analytics_seconds,
            "json_export_seconds": json_seconds,
            "csv_export_seconds": csv_seconds,
            "json_bytes": len(json_payload[0]),
            "csv_bytes": len(csv_payload[0]),
        })
    result = {key: median(t[key] for t in trials) for key in trials[0]}
    # Memory is deliberately measured once outside the timing trials because
    # tracemalloc materially changes CPU timings for this allocation-heavy path.
    tracemalloc.start()
    memory_profiles = generate_profiles(batch_size, SEED, country_mode="global")
    compute_analytics(memory_profiles)
    export_bytes(memory_profiles, "json")
    export_bytes(memory_profiles, "csv")
    _, result["peak_bytes"] = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result["batch_size"] = batch_size
    result["profiles_per_second"] = round(batch_size / result["generation_seconds"], 2)
    result["milliseconds_per_profile"] = round(result["generation_seconds"] * 1000 / batch_size, 3)
    return result


def main() -> None:
    print(json.dumps({"method": "median of 3 fixed-seed in-process trials; peak memory measured separately with tracemalloc"}))
    for size in BATCH_SIZES:
        print(json.dumps(benchmark(size)), flush=True)


if __name__ == "__main__":
    main()
