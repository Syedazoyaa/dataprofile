"""Reusable demographic/behavioural filtering over generated populations.

Filtering is always applied to an already-generated population, never during
generation, so dependency relationships are preserved. New filters are added
by extending FILTER_REGISTRY, not by changing endpoints.
"""

from .geography import resolve_country_name
from .schemas import ProfileFilter
from .segmentation import aggregate_purchase_intent, classify_profile

_LEVEL_VALUES = ("Low", "Moderate", "High")
_PRICE_VALUES = (
    "Price insensitive",
    "Slightly price aware",
    "Price conscious",
    "Price sensitive",
    "Highly price sensitive",
)
_INTENT_VALUES = ("Very unlikely", "Unlikely", "Considering", "Likely", "Very likely")
_GENDER_VALUES = ("Female", "Male", "Non-binary")
_EDUCATION_VALUES = ("School education", "Professional diploma", "Undergraduate", "Postgraduate")
_EMPLOYMENT_VALUES = (
    "Employed full-time", "Employed part-time", "Self-employed",
    "Student", "School student", "Retired",
)
_CAREER_VALUES = ("None", "Early", "Mid-level", "Senior", "Leadership", "Former professional")
_INCOME_VALUES = ("Limited", "Modest", "Comfortable", "Affluent")

# filter attr -> (profile key, allowed values, aggregate helper or None)
FILTER_REGISTRY = {
    "gender": ("gender", _GENDER_VALUES, None),
    "country": (None, None, None),  # validated against geography at request time
    "education": ("education_level", _EDUCATION_VALUES, None),
    "employment_status": ("employment_status", _EMPLOYMENT_VALUES, None),
    "career_level": ("career_level", _CAREER_VALUES, None),
    "income_band": ("income_band", _INCOME_VALUES, None),
    "research_intensity": ("research_before_purchase", _LEVEL_VALUES, None),
    "comparison_behaviour": ("comparison_behavior", _LEVEL_VALUES, None),
    "purchase_intent": (None, _INTENT_VALUES, aggregate_purchase_intent),
    "price_sensitivity": ("price_sensitivity", _PRICE_VALUES, None),
    "brand_loyalty": ("brand_loyalty", _LEVEL_VALUES, None),
    "decision_speed": ("decision_speed", _LEVEL_VALUES, None),
    "planning_behaviour": ("planning_behavior", _LEVEL_VALUES, None),
    "impulse_buying": ("impulse_buying", _LEVEL_VALUES, None),
    "behavioural_segment": (None, None, None),  # validated against segment ids
}

_SEGMENT_IDS = (
    "deliberate_researcher",
    "price_conscious_evaluator",
    "brand_loyal_buyer",
    "impulse_oriented_buyer",
    "balanced_mixed",
)


def _country_set(value) -> set[str]:
    """Normalise a country filter (name/code or list) to canonical names (OR semantics)."""
    entries = value if isinstance(value, list) else [value]
    return {resolve_country_name(entry) for entry in entries}


def validate_filters(filters: ProfileFilter, supported_countries=None):
    """Raise ValueError with a meaningful message for any invalid filter."""
    for name, (key, allowed, _helper) in FILTER_REGISTRY.items():
        value = getattr(filters, name, None)
        if value is None:
            continue
        if name == "country":
            try:
                names = _country_set(value)
            except ValueError:
                raise ValueError(f"Unsupported filter country: {value!r}") from None
            if supported_countries is not None:
                unknown = [n for n in names if n not in supported_countries]
                if unknown:
                    raise ValueError(f"Unsupported filter country: {sorted(unknown)!r}")
            continue
        if name == "behavioural_segment":
            if value not in _SEGMENT_IDS:
                raise ValueError(
                    f"Unsupported behavioural_segment: {value!r}. Valid: {sorted(_SEGMENT_IDS)}")
            continue
        if allowed is not None and value not in allowed:
            raise ValueError(f"Invalid value for {name}: {value!r}. Valid: {list(allowed)}")


def _matches(profile, filters: ProfileFilter) -> bool:
    if filters.age_min is not None and profile.get("age", 0) < filters.age_min:
        return False
    if filters.age_max is not None and profile.get("age", 0) > filters.age_max:
        return False
    for name, (key, _allowed, helper) in FILTER_REGISTRY.items():
        value = getattr(filters, name, None)
        if value is None:
            continue
        if name == "country":
            if profile.get("country") not in _country_set(value):
                return False
        elif name == "behavioural_segment":
            if classify_profile(profile)["segment_id"] != value:
                return False
        elif helper is not None:
            if helper(profile) != value:
                return False
        elif key is not None:
            if profile.get(key) != value:
                return False
    return True


def apply_filters(profiles: list[dict], filters: ProfileFilter) -> list[dict]:
    """Return the subset of profiles matching all provided filters (AND)."""
    return [p for p in profiles if _matches(p, filters)]


def active_filters(filters: ProfileFilter) -> dict:
    """Echo back only the filters that were actually applied."""
    result = {}
    for field in ("age_min", "age_max", *FILTER_REGISTRY):
        value = getattr(filters, field, None)
        if value is not None:
            result[field] = value
    return result
