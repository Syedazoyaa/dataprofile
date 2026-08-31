"""Data-driven geographic context for Raven.

These are deliberately modeled defaults for behavioral simulation, NOT empirical
claims.  Distributions are assumptions with probabilistic variation; future
calibration can replace them with sourced public statistics without changing
generators.  Geography describes environment (currency, language, labor market,
commerce/payment, transport/food/digital ecosystems, cultural context) and must
NOT define personality — the same latent human archetype remains comparable
across countries with only local expression changing.

Empirical vs modeled:
- empirical/reference intent: currency codes, official languages, well-known
  platform/transport/payment names are grounded in public knowledge but not
  statistically calibrated.
- modeled assumption: income_scale, digital_access, weights, probabilities,
  cost indices, housing/urban shares are synthetic defaults.
- fallback: generic shared vocabularies for foods/religions when local detail
  is unavailable.

Add a country by adding one context record + places; generators stay generic.
"""

from dataclasses import dataclass
from .utils import choose

@dataclass(frozen=True)
class GeographicContext:
    country: str; country_code: str; state: str; city: str; region: str
    nationality: str; languages: tuple[str, ...]; currency: str
    income_scale: int; industries: tuple[str, ...]; platforms: tuple[str, ...]
    payments: tuple[str, ...]; transport: tuple[str, ...]; foods: tuple[str, ...]
    religions: tuple[str, ...]; urban_rural: str; digital_access: float
    # Extended environmental dimensions (all modeled defaults)
    cost_factor: float
    income_cv: float
    housing_types: tuple[str, ...]
    shopping_ecosystems: tuple[str, ...]
    city_tier: str
    climate: str
    urban_share: float

# income = modeled median-like scale (annual, local currency) used as context anchor
# digital = modeled digital access index 0-1
# cost = modeled cost-of-living factor relative to baseline (1.0)
COUNTRIES = {
  "India": {"weight": 18, "code":"IN", "nationality":"Indian", "currency":"INR", "income":900000, "income_cv":0.52, "cost":0.38, "languages":("Hindi","English","Telugu","Tamil","Bengali"), "industries":("Technology","Finance","Manufacturing","Healthcare","Media"), "platforms":("JioHotstar","Amazon Prime Video","Netflix","YouTube"), "payments":("UPI","Digital wallet","Card","Cash"), "transport":("Metro","Two-wheeler","Ride-hailing","Rail"), "foods":("Regional Indian","Vegetarian","Street food","Global cuisine"), "religions":("Hindu","Muslim","Christian","Sikh","No religious affiliation"), "digital":.68, "housing":("Apartment","Independent house","Shared housing","Gated community"), "shopping":("E-commerce marketplace","Modern retail","Traditional market","Kirana/digital hybrid"), "climate":"Tropical/Mixed", "urban_share":0.35, "places":(("Telangana","Hyderabad","South Asia"),("Karnataka","Bengaluru","South Asia"),("Maharashtra","Mumbai","South Asia"))},
  "United States": {"weight": 14, "code":"US", "nationality":"American", "currency":"USD", "income":68000, "income_cv":0.45, "cost":1.0, "languages":("English","Spanish"), "industries":("Technology","Healthcare","Finance","Retail","Education"), "platforms":("Netflix","Hulu","Max","YouTube"), "payments":("Card","Digital wallet","Bank transfer","Cash"), "transport":("Car","Ride-hailing","Public transit","Domestic flight"), "foods":("American","Latin American","Asian","Plant-forward"), "religions":("Christian","Jewish","Muslim","No religious affiliation"), "digital":.88, "housing":("Single-family home","Apartment","Suburban house","Condo"), "shopping":("E-commerce marketplace","Big-box retail","Mall","Online DTC"), "climate":"Temperate/Continental", "urban_share":0.83, "places":(("California","Los Angeles","North America"),("New York","New York City","North America"),("Texas","Austin","North America"))},
  "United Kingdom": {"weight": 5, "code":"GB", "nationality":"British", "currency":"GBP", "income":42000, "income_cv":0.42, "cost":0.95, "languages":("English",), "industries":("Finance","Technology","Healthcare","Education","Creative services"), "platforms":("Netflix","BBC iPlayer","Disney+","YouTube"), "payments":("Card","Bank transfer","Digital wallet","Cash"), "transport":("Rail","Public transit","Car","Ride-hailing"), "foods":("British","South Asian","European","Plant-forward"), "religions":("Christian","Muslim","Hindu","No religious affiliation"), "digital":.9, "housing":("Terraced house","Apartment","Semi-detached","Council housing"), "shopping":("High street","E-commerce","Supermarket","Online marketplace"), "climate":"Temperate maritime", "urban_share":0.84, "places":(("England","London","Europe"),("Scotland","Glasgow","Europe"),("England","Manchester","Europe"))},
  "Japan": {"weight": 7, "code":"JP", "nationality":"Japanese", "currency":"JPY", "income":5200000, "income_cv":0.40, "cost":1.05, "languages":("Japanese","English"), "industries":("Technology","Manufacturing","Automotive","Finance","Retail"), "platforms":("Netflix","Amazon Prime Video","U-NEXT","YouTube"), "payments":("Cash","Card","Mobile payment","Bank transfer"), "transport":("Rail","Public transit","Walking","Car"), "foods":("Japanese","Seafood","Regional cuisine","Western"), "religions":("Shinto","Buddhist","Christian","No religious affiliation"), "digital":.86, "housing":("Apartment","Compact house","Condo","Company housing"), "shopping":("Convenience store","Department store","E-commerce","Specialty retail"), "climate":"Temperate/Seasonal", "urban_share":0.92, "places":(("Tokyo","Tokyo","East Asia"),("Osaka","Osaka","East Asia"),("Aichi","Nagoya","East Asia"))},
  "Saudi Arabia": {"weight": 4, "code":"SA", "nationality":"Saudi", "currency":"SAR", "income":115000, "income_cv":0.48, "cost":0.88, "languages":("Arabic","English"), "industries":("Energy","Government","Finance","Construction","Technology"), "platforms":("Shahid","Netflix","YouTube","Amazon Prime Video"), "payments":("Card","Mobile payment","Bank transfer","Cash"), "transport":("Car","Ride-hailing","Metro","Domestic flight"), "foods":("Arabian","Middle Eastern","Halal international","Global cuisine"), "religions":("Muslim","Christian","No religious affiliation"), "digital":.91, "housing":("Villa","Apartment","Compound","Traditional house"), "shopping":("Mall","E-commerce","Souk/traditional","Hypermarket"), "climate":"Arid/Desert", "urban_share":0.85, "places":(("Riyadh Province","Riyadh","Middle East"),("Makkah Province","Jeddah","Middle East"),("Eastern Province","Dammam","Middle East"))},
  "Brazil": {"weight": 8, "code":"BR", "nationality":"Brazilian", "currency":"BRL", "income":45000, "income_cv":0.55, "cost":0.55, "languages":("Portuguese","English"), "industries":("Agriculture","Services","Finance","Technology","Manufacturing"), "platforms":("Globoplay","Netflix","YouTube","Amazon Prime Video"), "payments":("PIX","Card","Cash","Digital wallet"), "transport":("Bus","Car","Ride-hailing","Metro"), "foods":("Brazilian","Regional cuisine","Barbecue","Plant-forward"), "religions":("Christian","Afro-Brazilian religions","No religious affiliation"), "digital":.75, "housing":("Apartment","House","Favela/Community housing","Gated community"), "shopping":("Street market","Mall","E-commerce","Supermarket"), "climate":"Tropical/Subtropical", "urban_share":0.87, "places":(("São Paulo","São Paulo","South America"),("Rio de Janeiro","Rio de Janeiro","South America"),("Bahia","Salvador","South America"))},
  "Nigeria": {"weight": 10, "code":"NG", "nationality":"Nigerian", "currency":"NGN", "income":4500000, "income_cv":0.58, "cost":0.32, "languages":("English","Yoruba","Igbo","Hausa"), "industries":("Services","Technology","Oil and gas","Trade","Agriculture"), "platforms":("Netflix","Showmax","YouTube","Amazon Prime Video"), "payments":("Bank transfer","Mobile money","Card","Cash"), "transport":("Bus","Ride-hailing","Car","Motorcycle taxi"), "foods":("Nigerian","West African","Regional cuisine","Global cuisine"), "religions":("Christian","Muslim","Traditional religions","No religious affiliation"), "digital":.58, "housing":("Compound","Apartment","Bungalow","Shared housing"), "shopping":("Open market","E-commerce","Supermarket","Informal trade"), "climate":"Tropical", "urban_share":0.52, "places":(("Lagos","Lagos","West Africa"),("Federal Capital Territory","Abuja","West Africa"),("Rivers","Port Harcourt","West Africa"))},
}

def supported_countries() -> tuple[str, ...]: return tuple(COUNTRIES)
def supported_languages() -> set[str]: return {language for item in COUNTRIES.values() for language in item["languages"]}

def get_context(rng, country_mode: str = "specific", country: str | None = "India", region: str | None = None) -> GeographicContext:
    if country_mode == "global": country = choose(rng, list(COUNTRIES), [item["weight"] for item in COUNTRIES.values()])
    if country_mode != "global" and country not in COUNTRIES: raise ValueError("Unsupported country")
    item = COUNTRIES[country]
    places = [place for place in item["places"] if not region or place[0] == region]
    if not places: raise ValueError("Unsupported region for country")
    state, city, geo_region = choose(rng, places)
    # City tier and urban/rural determined probabilistically from urban_share
    # Keep deterministic given rng:  Urban vs Rural weighted by urban_share
    urban_rural = "Urban" if rng.random() < item["urban_share"] else "Rural"
    # Tier: metro vs secondary
    city_tier = "Metro" if city in {"Hyderabad","Bengaluru","Mumbai","Los Angeles","New York City","London","Tokyo","Riyadh","São Paulo","Lagos"} else "Tier 1" if rng.random() < 0.6 else "Tier 2"
    return GeographicContext(country, item["code"], state, city, geo_region, item["nationality"], item["languages"], item["currency"], item["income"], item["industries"], item["platforms"], item["payments"], item["transport"], item["foods"], item["religions"], urban_rural, item["digital"], item["cost"], item["income_cv"], item["housing"], item["shopping"], city_tier, item["climate"], item["urban_share"])
