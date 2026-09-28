"""Population comparison over arbitrary synthetic populations.

Compares two or more labelled populations across existing Raven dimensions.
All inputs are generated synthetic populations; outputs are structured JSON
suitable for frontend visualisation. Percentages normalise for different
population sizes; raw counts are included alongside.
"""

from collections import Counter

from .segmentation import SEGMENT_DEFINITIONS, aggregate_purchase_intent, classify_profile

AGE_BINS = (
    ("16-24", 16, 24),
    ("25-34", 25, 34),
    ("35-49", 35, 49),
    ("50-64", 50, 64),
    ("65+", 65, 78),
)

DEMOGRAPHIC_DIMENSIONS = (
    "age_distribution",
    "gender_distribution",
    "education",
    "employment",
    "career_level",
    "income_band",
)

BEHAVIOURAL_DIMENSIONS = (
    "research_intensity",
    "comparison_behaviour",
    "purchase_intent",
    "price_sensitivity",
    "brand_loyalty",
    "decision_speed",
    "planning_behaviour",
    "impulse_buying",
)


def _age_bin(age):
    for label, low, high in AGE_BINS:
        if low <= age <= high:
            return label
    return "65+"


def _dimension_values(profile, dimension):
    if dimension == "age_distribution":
        return _age_bin(profile.get("age", 0))
    if dimension == "gender_distribution":
        return profile.get("gender")
    if dimension == "education":
        return profile.get("education_level")
    if dimension == "employment":
        return profile.get("employment_status")
    if dimension == "career_level":
        return profile.get("career_level")
    if dimension == "income_band":
        return profile.get("income_band")
    if dimension == "research_intensity":
        return profile.get("research_before_purchase")
    if dimension == "comparison_behaviour":
        return profile.get("comparison_behavior")
    if dimension == "purchase_intent":
        return aggregate_purchase_intent(profile)
    if dimension == "price_sensitivity":
        return profile.get("price_sensitivity")
    if dimension == "brand_loyalty":
        return profile.get("brand_loyalty")
    if dimension == "decision_speed":
        return profile.get("decision_speed")
    if dimension == "planning_behaviour":
        return profile.get("planning_behavior")
    if dimension == "impulse_buying":
        return profile.get("impulse_buying")
    return None


def _distribution(populations: dict[str, list[dict]], dimension: str) -> dict:
    categories: set = set()
    counts: dict[str, Counter] = {}
    for label, profiles in populations.items():
        counter = Counter(_dimension_values(p, dimension) for p in profiles)
        counts[label] = counter
        categories.update(counter.keys())
    ordered = sorted(c for c in categories if c is not None)
    result = {"dimension": dimension, "categories": ordered, "populations": {}}
    for label, profiles in populations.items():
        total = len(profiles)
        counter = counts[label]
        result["populations"][label] = {
            "n": total,
            "counts": {c: counter.get(c, 0) for c in ordered},
            "percentages": {c: round(counter.get(c, 0) / total * 100, 2) if total else 0.0
                            for c in ordered},
        }
    return result


def compare_populations(populations: dict[str, list[dict]]) -> dict:
    """Compare labelled populations; supports two or more of any size."""
    if len(populations) < 2:
        raise ValueError("at least two populations are required for comparison")
    demographics = [_distribution(populations, d) for d in DEMOGRAPHIC_DIMENSIONS]
    behavioural = [_distribution(populations, d) for d in BEHAVIOURAL_DIMENSIONS]
    segment_pops = {label: [classify_profile(p)["segment_id"] for p in profiles]
                    for label, profiles in populations.items()}
    categories = [d["segment_id"] for d in SEGMENT_DEFINITIONS]
    segment_dist: dict = {"dimension": "behavioural_segments",
                          "categories": categories, "populations": {}}
    for label, ids in segment_pops.items():
        total = len(ids)
        counter = Counter(ids)
        segment_dist["populations"][label] = {
            "n": total,
            "counts": {c: counter.get(c, 0) for c in categories},
            "percentages": {c: round(counter.get(c, 0) / total * 100, 2) if total else 0.0
                            for c in categories},
        }
    return {
        "populations": {label: {"n": len(profiles)} for label, profiles in populations.items()},
        "demographics": demographics,
        "behavioural": behavioural,
        "segments": segment_dist,
        "note": ("Distributions describe model-generated synthetic populations, "
                 "not empirical claims about real populations."),
    }
