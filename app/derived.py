"""Deterministic derived profile attributes.

High-level human-readable classifications built from already-generated traits
and observables (never independent random draws, except seeded spread noise).
Every function is deterministic for a given profile: same seed + config +
index always yields the same derived values.

Covers: profile_summary, social_disposition (Introvert/Ambivert/Extrovert),
review_influence (distinct from recommendation_dependence), interactive /
social-shopping / advertisement engagement, and the 7-attribute social media
personality (distinct from raw following/activity observables).
"""

_LEVEL_RANK = {"Low": 1, "Moderate": 2, "High": 3}
_FREQ_RANK = {"Never": 1, "Rarely": 2, "Occasionally": 3, "Frequently": 4, "Very frequently": 5}


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _rank_level(value, mapping=_LEVEL_RANK) -> int:
    return mapping.get(value, 2)


def social_disposition(extraversion: float, social_orientation: float) -> str:
    """Introvert / Ambivert / Extrovert from raw latent scores (deterministic, no RNG)."""
    score = _clip(0.55 * extraversion + 0.45 * social_orientation)
    if score < 0.42:
        return "Introvert"
    if score < 0.60:
        return "Ambivert"
    return "Extrovert"


def _level(rng, base: float, noise: float = 0.10) -> str:
    """Seeded Low/Moderate/High level with natural spread around a trait base."""
    value = _clip(rng.gauss(base, noise))
    if value >= 0.60:
        return "High"
    if value <= 0.40:
        return "Low"
    return "Moderate"


def review_influence(rng, traits: dict) -> str:
    """Weight given to product reviews (information-driven; distinct from
    recommendation_dependence, which is socially-driven)."""
    base = _clip(0.55 * traits["openness"] + 0.30 * traits["conscientiousness"]
                 + 0.15 * traits["planning_orientation"])
    return _level(rng, base)


def interactive_content_engagement(rng, traits: dict) -> str:
    """Survey / quiz / interactive content engagement."""
    base = _clip(0.45 * traits["digital_adoption"] + 0.30 * traits["novelty_seeking"]
                 + 0.25 * traits["extraversion"])
    return _level(rng, base)


def social_shopping_tendency(rng, traits: dict, profile: dict) -> str:
    """Propensity to purchase via social platforms."""
    online = _rank_level(profile.get("online_shopping_frequency")) / 3.0
    base = _clip(0.40 * traits["social_orientation"] + 0.30 * traits["digital_adoption"]
                 + 0.30 * online)
    return _level(rng, base)


def advertisement_responsiveness(rng, traits: dict, age: int) -> str:
    """Responsiveness to advertising (novelty/social-driven, age-tilted)."""
    base = _clip(0.40 * traits["novelty_seeking"] + 0.30 * traits["social_orientation"]
                 + 0.20 * traits["openness"] + (0.05 if age < 35 else -0.05))
    return _level(rng, base)


def social_consumer_tendency(rng, traits: dict) -> str:
    """Content Consumer: propensity to consume (vs create) social content."""
    base = _clip(0.50 * traits["social_orientation"] + 0.35 * traits["digital_adoption"]
                 + 0.15 * (1 - traits["openness"]))
    return _level(rng, base)


def social_creator_tendency(rng, traits: dict, profile: dict) -> str:
    """Content Creator tendency. Derived from observed content_creation plus
    novelty drive, so it tracks but never equals the raw observable."""
    observed = _rank_level(profile.get("content_creation")) / 3.0
    base = _clip(0.55 * observed + 0.30 * traits["novelty_seeking"]
                 + 0.15 * traits["extraversion"])
    return _level(rng, base)


def social_engagement_level(rng, traits: dict, profile: dict) -> str:
    """Engagement depth (distinct from raw social_media_activity volume)."""
    activity = _rank_level(profile.get("social_media_activity")) / 3.0
    messaging = _FREQ_RANK.get(profile.get("messaging_frequency"), 3) / 5.0
    base = _clip(0.45 * activity + 0.35 * messaging + 0.20 * traits["extraversion"])
    return _level(rng, base)


def trend_sensitivity(rng, traits: dict, age: int) -> str:
    """Trend Sensitivity: novelty + cultural openness, tilted younger."""
    base = _clip(0.45 * traits["novelty_seeking"] + 0.35 * traits["cultural_openness"]
                 + 0.10 * traits["digital_adoption"] + (0.06 if age < 32 else -0.04))
    return _level(rng, base)


def influencer_influence(rng, traits: dict, profile: dict) -> str:
    """Being influenced by influencers. Combines recommendation dependence with
    actual following behaviour, so it differs from influencer_following alone."""
    following = _FREQ_RANK.get(profile.get("influencer_following"), 3) / 5.0
    rec_dep = _rank_level(profile.get("recommendation_dependence")) / 3.0
    base = _clip(0.50 * rec_dep + 0.35 * following + 0.15 * traits["agreeableness"])
    return _level(rng, base)


def brand_interaction_tendency(rng, traits: dict, profile: dict) -> str:
    """Brand Interaction on social platforms (loyalty × social activity)."""
    loyalty = _rank_level(profile.get("brand_loyalty")) / 3.0
    activity = _rank_level(profile.get("social_media_activity")) / 3.0
    base = _clip(0.50 * loyalty + 0.35 * activity + 0.15 * traits["extraversion"])
    return _level(rng, base)


def profile_summary(profile: dict) -> str:
    """Concise human-readable summary derived from generated attributes (no RNG)."""
    parts = []
    digital = profile.get("digital_adoption", "Moderate")
    parts.append({"Very high": "Digitally highly active",
                  "High": "Digitally active",
                  "Moderate": "Moderately digital",
                  "Low": "Occasionally online",
                  "Very low": "Rarely online"}.get(digital, "Moderately digital"))
    research = profile.get("research_before_purchase", "Moderate")
    parts.append({"High": "research-oriented", "Moderate": "balanced researcher",
                  "Low": "quick-deciding"}.get(research, "balanced researcher"))
    employment = profile.get("employment_status", "")
    if employment.startswith("Employed"):
        parts.append(f"{str(profile.get('career_level', '')).lower()} professional".strip())
    elif employment in ("Student", "School student"):
        parts.append("student")
    elif employment == "Retired":
        parts.append("retired professional")
    elif employment == "Self-employed":
        parts.append("self-employed professional")
    price = profile.get("price_sensitivity", "Price conscious")
    parts.append(f"with {str(price).lower()}")
    shopping = profile.get("online_shopping_frequency", "Moderate")
    parts.append({"High": "strong online shopping preference",
                  "Moderate": "mixed online/offline shopping",
                  "Low": "offline-first shopping"}.get(shopping, "mixed online/offline shopping"))
    interests = []
    if _rank_level(profile.get("technology_smartphone_usage_frequency_score",
                               "Occasionally"), _FREQ_RANK) >= 4:
        interests.append("technology")
    if profile.get("travel_frequency") == "High":
        interests.append("travel")
    if _rank_level(profile.get("music_frequency", "Moderate")) >= 3:
        interests.append("music")
    if _rank_level(profile.get("reading_frequency", "Moderate")) >= 3:
        interests.append("reading")
    if _rank_level(profile.get("sports_interest", "Moderate")) >= 3:
        interests.append("sports")
    if interests:
        parts.append("and strong interest in " + ", ".join(interests[:3]))
    summary = ", ".join(parts) + "."
    return summary[0].upper() + summary[1:]


def derive_extras(rng, traits: dict, profile: dict, age: int) -> dict:
    """All derived experience-layer attributes for one profile (seeded RNG)."""
    extras = {
        "social_disposition": social_disposition(traits["extraversion"],
                                                 traits["social_orientation"]),
        "review_influence": review_influence(rng, traits),
        "interactive_content_engagement": interactive_content_engagement(rng, traits),
        "advertisement_responsiveness": advertisement_responsiveness(rng, traits, age),
        "social_consumer_tendency": social_consumer_tendency(rng, traits),
        "social_creator_tendency": social_creator_tendency(rng, traits, profile),
        "social_engagement_level": social_engagement_level(rng, traits, profile),
        "trend_sensitivity": trend_sensitivity(rng, traits, age),
        "influencer_influence": influencer_influence(rng, traits, profile),
        "brand_interaction_tendency": brand_interaction_tendency(rng, traits, profile),
        "social_shopping_tendency": social_shopping_tendency(rng, traits, profile),
    }
    # Summary is derived last so it can reflect the full profile (deterministic).
    extras["profile_summary"] = profile_summary({**profile, **extras})
    return extras
