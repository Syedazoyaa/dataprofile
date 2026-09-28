"""Interpretable behavioural segmentation for Raven's synthetic population.

These segments describe clusters of the *generated synthetic population* only;
they are not empirical claims about real-world customers. Assignment is a
deterministic scoring system over existing behavioural attributes (no random
draws, no ML dependencies), isolated here so a statistical clustering
approach can replace it later without touching the generator.
"""

from statistics import median

LEVEL_RANK = {"Low": 1, "Moderate": 2, "High": 3}
PRICE_RANK = {
    "Price insensitive": 1,
    "Slightly price aware": 2,
    "Price conscious": 3,
    "Price sensitive": 4,
    "Highly price sensitive": 5,
}
INTENT_RANK = {"Very unlikely": 1, "Unlikely": 2, "Considering": 3, "Likely": 4, "Very likely": 5}

SEGMENT_DEFINITIONS = (
    {
        "segment_id": "deliberate_researcher",
        "segment_name": "Deliberate Researcher",
        "description": "Researches extensively, compares options carefully and decides slowly.",
        "defining_characteristics": [
            "research_before_purchase is High",
            "comparison_behavior is High",
            "analytical_orientation is High",
            "decision_speed is Low",
            "impulse_buying is Low",
        ],
    },
    {
        "segment_id": "price_conscious_evaluator",
        "segment_name": "Price-Conscious Evaluator",
        "description": "Weighs price and discounts heavily and compares before committing.",
        "defining_characteristics": [
            "price_sensitivity is Price sensitive or Highly price sensitive",
            "discount_sensitivity is High",
            "premium_preference is Low",
            "comparison_behavior is High",
        ],
    },
    {
        "segment_id": "brand_loyal_buyer",
        "segment_name": "Brand-Loyal Buyer",
        "description": "Trusts familiar brands, repeats purchases and relies on recommendations.",
        "defining_characteristics": [
            "brand_loyalty is High",
            "brand_trust is High",
            "recommendation_dependence is High",
            "impulse_buying is Low or Moderate",
        ],
    },
    {
        "segment_id": "impulse_oriented_buyer",
        "segment_name": "Impulse-Oriented Buyer",
        "description": "Decides fast with minimal research and higher spontaneous buying.",
        "defining_characteristics": [
            "impulse_buying is High",
            "decision_speed is High",
            "planning_behavior is Low",
            "research_before_purchase is Low",
        ],
    },
    {
        "segment_id": "balanced_mixed",
        "segment_name": "Balanced/Mixed Behaviour",
        "description": "No single dominant tendency; behaviour sits near the middle across dimensions.",
        "defining_characteristics": [
            "key behaviours are mostly Moderate",
            "no extreme price, brand or impulse tendency",
        ],
    },
)

# Fixed tie-break order: most distinctive segments first, balanced last.
SEGMENT_ORDER = [d["segment_id"] for d in SEGMENT_DEFINITIONS]


def _level(value, mapping=LEVEL_RANK, default=2):
    return mapping.get(value, default)


def _norm(rank, low, high):
    if high <= low:
        return 0.5
    return (rank - low) / (high - low)


def aggregate_purchase_intent(profile):
    """Median purchase-intent label across commerce topics (derived proxy)."""
    ranks = [INTENT_RANK[v] for k, v in profile.items()
             if k.endswith("_purchase_intent_score") and v in INTENT_RANK]
    if not ranks:
        return "Considering"
    med = median(sorted(ranks))
    for label, rank in INTENT_RANK.items():
        if rank == round(med):
            return label
    return "Considering"


def segment_scores(profile):
    """Deterministic 0-1 fit score per segment for one profile."""
    research = _norm(_level(profile.get("research_before_purchase")), 1, 3)
    comparison = _norm(_level(profile.get("comparison_behavior")), 1, 3)
    analytical = _norm(_level(profile.get("analytical_orientation")), 1, 3)
    info = _norm(_level(profile.get("information_seeking")), 1, 3)
    planning = _norm(_level(profile.get("planning_behavior")), 1, 3)
    decision_fast = _norm(_level(profile.get("decision_speed")), 1, 3)
    decision_slow = 1.0 - decision_fast
    impulse = _norm(_level(profile.get("impulse_buying")), 1, 3)
    impulse_low = 1.0 - impulse
    brand = _norm(_level(profile.get("brand_loyalty")), 1, 3)
    trust = _norm(_level(profile.get("brand_trust")), 1, 3)
    recommend = _norm(_level(profile.get("recommendation_dependence")), 1, 3)
    price = _norm(PRICE_RANK.get(profile.get("price_sensitivity"), 3), 1, 5)
    price_low = 1.0 - price
    discount = _norm(_level(profile.get("discount_sensitivity")), 1, 3)
    premium = _norm(_level(profile.get("premium_preference")), 1, 3)
    premium_low = 1.0 - premium

    deliberate = (research * 0.24 + comparison * 0.20 + analytical * 0.16
                  + info * 0.12 + decision_slow * 0.14 + impulse_low * 0.08
                  + planning * 0.06)
    price_eval = (price * 0.30 + discount * 0.24 + premium_low * 0.16
                  + comparison * 0.16 + impulse_low * 0.08 + research * 0.06)
    brand_loyal = (brand * 0.30 + trust * 0.22 + recommend * 0.18
                   + impulse_low * 0.12 + price_low * 0.10 + planning * 0.08)
    impulse_buy = (impulse * 0.30 + decision_fast * 0.24 + (1.0 - planning) * 0.18
                   + (1.0 - research) * 0.14 + (1.0 - comparison) * 0.08
                   + (1.0 - discount) * 0.06)
    # Balanced: high when key behaviours sit near the middle.
    mids = [profile.get("research_before_purchase"), profile.get("comparison_behavior"),
            profile.get("brand_loyalty"), profile.get("impulse_buying"),
            profile.get("decision_speed"), profile.get("planning_behavior")]
    balanced = sum(1.0 if v == "Moderate" else 0.45 if v is not None else 0.0 for v in mids) / len(mids)
    balanced = balanced * 0.96  # keep achievable without dominating extremes

    return {
        "deliberate_researcher": round(deliberate, 4),
        "price_conscious_evaluator": round(price_eval, 4),
        "brand_loyal_buyer": round(brand_loyal, 4),
        "impulse_oriented_buyer": round(impulse_buy, 4),
        "balanced_mixed": round(balanced, 4),
    }


def classify_profile(profile):
    """Assign a profile to exactly one segment (deterministic, never random)."""
    scores = segment_scores(profile)
    best_id = max(SEGMENT_ORDER, key=lambda sid: (scores[sid], -SEGMENT_ORDER.index(sid)))
    definition = next(d for d in SEGMENT_DEFINITIONS if d["segment_id"] == best_id)
    return {
        "segment_id": definition["segment_id"],
        "segment_name": definition["segment_name"],
        "score": scores[best_id],
        "scores": scores,
    }


def summarize_segments(profiles):
    """Population-level segment distribution with counts and percentages."""
    total = len(profiles)
    counts = {d["segment_id"]: 0 for d in SEGMENT_DEFINITIONS}
    for profile in profiles:
        counts[classify_profile(profile)["segment_id"]] += 1
    segments = []
    for definition in SEGMENT_DEFINITIONS:
        count = counts[definition["segment_id"]]
        segments.append({
            **definition,
            "profile_count": count,
            "percentage": round(count / total * 100, 2) if total else 0.0,
        })
    return {"total_profiles": total, "segments": segments}
