"""Data-driven global geography for Raven.

All country knowledge lives in structured metadata (geography_world.py),
generation logic remains reusable and free of if/else per country.

- 193 countries with ISO 3166-1 alpha-2/alpha-3/numeric, continent, subregion,
  nationality, currency, languages, cities/regions, payments, transport, etc.
- Fallback hierarchy: country → subregion → global generic
- Geography creates context (language, currency, payment, transport, housing,
  food, media, digital, urban) not personality.

Detailed overrides for the original 6 countries preserve exact legacy behavior.
"""

from dataclasses import dataclass
from typing import Tuple
from .geography_world import COUNTRIES_WORLD
from .utils import choose

# Re-export world as COUNTRIES for backward compatibility
COUNTRIES = COUNTRIES_WORLD

# For weighted global selection, use original weights where defined, else 3
# Keep original 6 weights (18,14,5,7,4,8,10) and 3 for others.

# Coverage tiers are intentionally NOT exposed: every supported country is a
# first-class product citizen. Per-country registry values (places, languages,
# income scales, selection weights) exist internally where justified, but no
# visible core/fallback/deep/standard distinction is presented to frontend
# users. The only documented geographic limitation is that city-language
# affinity tuning currently covers a small set of known metros; everywhere
# else a generic dominant-language weighting applies.

@dataclass(frozen=True)
class GeographicContext:
    country: str
    country_code: str  # alpha-2
    alpha3: str
    numeric: str
    continent: str
    subregion: str
    state: str
    city: str
    region: str  # macro region / subregion label for cultural_context
    nationality: str
    languages: Tuple[str, ...]
    currency: str
    income_scale: int
    industries: Tuple[str, ...]
    platforms: Tuple[str, ...]
    payments: Tuple[str, ...]
    transport: Tuple[str, ...]
    foods: Tuple[str, ...]
    religions: Tuple[str, ...]
    urban_rural: str
    digital_access: float
    cost_factor: float
    income_cv: float
    housing_types: Tuple[str, ...]
    shopping_ecosystems: Tuple[str, ...]
    city_tier: str
    climate: str
    urban_share: float

def supported_countries() -> Tuple[str, ...]:
    return tuple(sorted(COUNTRIES.keys()))

def supported_languages() -> set[str]:
    return {lang for item in COUNTRIES.values() for lang in item["languages"]}

def supported_currencies() -> set[str]:
    return {item["currency"] for item in COUNTRIES.values()}

def supported_continents() -> Tuple[str, ...]:
    return tuple(sorted({item["continent"] for item in COUNTRIES.values()}))

def supported_subregions() -> Tuple[str, ...]:
    return tuple(sorted({item["subregion"] for item in COUNTRIES.values()}))

def _fallback_item(country: str) -> dict:
    # Direct hit
    if country in COUNTRIES:
        return COUNTRIES[country]
    # Fallback by subregion/region not needed as we have all countries, but keep for robustness
    # Search by code
    for v in COUNTRIES.values():
        if v["code"] == country or v["alpha3"] == country:
            return v
    raise ValueError(f"Unsupported country: {country}")

def resolve_country_name(value: str) -> str:
    """Canonical country name for a name, alpha-2 or alpha-3 code (case-insensitive).

    Single shared helper for generation, filtering, analytics and validation
    so country lists are never duplicated across files.
    """
    if not isinstance(value, str):
        raise ValueError(f"Unsupported country: {value!r}")
    text = value.strip()
    if text in COUNTRIES:
        return text
    lowered = text.lower()
    for name, item in COUNTRIES.items():
        if (name.lower() == lowered or item["code"].lower() == lowered
                or item["alpha3"].lower() == lowered):
            return name
    raise ValueError(f"Unsupported country: {value!r}")

def country_summary(country: str) -> dict:
    """Frontend-ready registry record for one country (dropdowns, analytics)."""
    name = resolve_country_name(country)
    item = COUNTRIES[name]
    return {
        "name": name,
        "alpha2": item["code"],
        "alpha3": item["alpha3"],
        "numeric": item["numeric"],
        "continent": item["continent"],
        "subregion": item["subregion"],
        "nationality": item["nationality"],
        "currency": item["currency"],
        "languages": list(item["languages"]),
    }

def country_registry() -> list[dict]:
    """Full canonical registry (sorted by name) for dropdowns and validation."""
    return [country_summary(name) for name in sorted(COUNTRIES.keys())]

def get_context(rng, country_mode: str = "global", country: str | None = None, region: str | None = None, continent: str | None = None, countries: list[str] | None = None) -> GeographicContext:
    # Resolve country
    chosen = country
    if country_mode == "multiple":
        # Explicit multi-country selection: per-profile pick weighted by
        # registry weights, so larger populations stay proportionally mixed.
        if not countries:
            raise ValueError("countries must be a non-empty list for multiple-country generation")
        canonical = []
        for entry in countries:
            name = resolve_country_name(entry)
            if name not in canonical:
                canonical.append(name)
        weights = [COUNTRIES[n]["weight"] for n in canonical]
        chosen = choose(rng, canonical, weights)
    elif country_mode == "global" or country_mode == "random":
        # weighted random across all countries
        names = list(COUNTRIES.keys())
        weights = [COUNTRIES[n]["weight"] for n in names]
        chosen = choose(rng, names, weights)
    elif country_mode == "continent":
        # continent param can be in region or continent arg
        target_cont = continent or region or country
        candidates = [n for n, v in COUNTRIES.items() if v["continent"].lower() == target_cont.lower()]
        if not candidates:
            # try subregion
            candidates = [n for n, v in COUNTRIES.items() if v["subregion"].lower() == target_cont.lower()]
        if not candidates:
            raise ValueError(f"Unsupported continent/region: {target_cont}")
        weights = [COUNTRIES[n]["weight"] for n in candidates]
        chosen = choose(rng, candidates, weights)
    elif country_mode == "region" or country_mode == "subregion":
        target_reg = region or country
        candidates = [n for n, v in COUNTRIES.items() if v["subregion"].lower() == target_reg.lower() or v["continent"].lower() == target_reg.lower()]
        if not candidates:
            raise ValueError(f"Unsupported region: {target_reg}")
        weights = [COUNTRIES[n]["weight"] for n in candidates]
        chosen = choose(rng, candidates, weights)
    else:  # specific
        chosen = resolve_country_name(chosen)

    item = _fallback_item(chosen)
    # Places: filter by region if provided and mode is specific with region
    places = item["places"]
    if region and country_mode == "specific":
        # region here means admin region filter (e.g., "Telangana")
        filtered = [p for p in places if p[0].lower() == region.lower()]
        if filtered:
            places = filtered
        # else keep all (fallback)
    # Choose state/city/region
    # places is tuple of (admin, city, macro_region)
    state, city, geo_region = choose(rng, list(places))
    # Urban/rural weighted by urban_share
    urban_rural = "Urban" if rng.random() < item["urban_share"] else "Rural"
    # City tier: Metro if major city of original 6 or capital-like, else Tier 1/2
    metro_cities = {"Hyderabad","Bengaluru","Mumbai","Los Angeles","New York City","London","Tokyo","Riyadh","Sao Paulo","Lagos","Berlin","Paris","Toronto","Sydney","Moscow","Beijing","Mumbai","Delhi","Shanghai","Mexico City","Cairo","Nairobi","Johannesburg","Bangkok","Seoul","Jakarta","Istanbul","Dubai"}
    if city in metro_cities or "City 1" not in city:  # original detailed cities are meaningful
        # For templated "X City 1" treat as Tier 1
        if "City 1" in city:
            city_tier = "Tier 1"
        elif city in {"Hyderabad","Bengaluru","Mumbai","Los Angeles","New York City","London","Tokyo","Riyadh","Sao Paulo","Lagos"}:
            city_tier = "Metro"
        else:
            city_tier = "Metro" if rng.random() < 0.35 else ("Tier 1" if rng.random() < 0.6 else "Tier 2")
    else:
        city_tier = "Tier 1" if rng.random() < 0.6 else "Tier 2"

    return GeographicContext(
        country=chosen,
        country_code=item["code"],
        alpha3=item["alpha3"],
        numeric=item["numeric"],
        continent=item["continent"],
        subregion=item["subregion"],
        state=state,
        city=city,
        region=geo_region,
        nationality=item["nationality"],
        languages=item["languages"],
        currency=item["currency"],
        income_scale=item["income"],
        industries=item["industries"],
        platforms=item["platforms"],
        payments=item["payments"],
        transport=item["transport"],
        foods=item["foods"],
        religions=item["religions"],
        urban_rural=urban_rural,
        digital_access=item["digital"],
        cost_factor=item["cost"],
        income_cv=item["income_cv"],
        housing_types=item["housing"],
        shopping_ecosystems=item["shopping"],
        city_tier=city_tier,
        climate=item["climate"],
        urban_share=item["urban_share"],
    )
