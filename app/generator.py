import json
from datetime import date, timedelta
from pathlib import Path

from .personas import PERSONAS, OTT_BY_LANGUAGE
from .rules import validate_profile
from .schemas import DOMAIN_TOPICS, MEASURES, PROFILE_COLUMNS, PROFILE_SCHEMA_VERSION
from .utils import choose, level, profile_rng

LOCATIONS = json.loads((Path(__file__).parent.parent / "data" / "india_locations.json").read_text(encoding="utf-8"))
AGE_BANDS = ((16, 17, 3), (18, 22, 13), (23, 29, 20), (30, 39, 24), (40, 49, 18), (50, 59, 12), (60, 69, 7), (70, 78, 3))
LANGUAGES = {place["language"] for place in LOCATIONS} | {"Hindi", "English"}
CITY_STATES = {"Hyderabad": "Telangana", "Bengaluru": "Karnataka", "Mumbai": "Maharashtra", "Delhi": "Delhi", "Chennai": "Tamil Nadu", "Pune": "Maharashtra", "Kolkata": "West Bengal", "Kochi": "Kerala", "Ahmedabad": "Gujarat", "Jaipur": "Rajasthan"}


def _clip(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def _score(rng, base: float, noise: float = .12) -> float:
    return _clip(rng.gauss(base, noise))


def _stage(age: int) -> str:
    if age < 18: return "Teenager"
    if age < 23: return "University Student"
    if age < 30: return "Early Career"
    if age < 40: return "Established Professional"
    if age < 52: return "Mid-Career"
    if age < 64: return "Senior Professional"
    return "Retired"


def _age(rng, age_range) -> int:
    if age_range:
        return rng.randint(*age_range)
    band = choose(rng, list(AGE_BANDS), [band[2] for band in AGE_BANDS])
    return rng.randint(band[0], band[1])


def _category(value: float) -> str:
    return level(value)


def _five_level(value: float, measure: str) -> str:
    """Translate internal continuous propensity into user-facing categories."""
    labels = {
        "interest_score": ("Not interested", "Slightly interested", "Moderately interested", "Interested", "Highly interested"),
        "usage_frequency_score": ("Never", "Rarely", "Occasionally", "Frequently", "Very frequently"),
        "purchase_intent_score": ("Very unlikely", "Unlikely", "Considering", "Likely", "Very likely"),
        "research_intensity_score": ("Minimal research", "Light research", "Moderate research", "Detailed research", "Extensive research"),
    }
    return labels[measure][min(4, int(_clip(value) * 5))]


def _trait_label(name: str, value: float) -> str:
    descriptions = {
        "technology_affinity": ("Technology cautious", "Technology practical", "Technology comfortable", "Technology enthusiastic", "Technology leading"),
        "price_sensitivity": ("Price insensitive", "Slightly price aware", "Price conscious", "Price sensitive", "Highly price sensitive"),
        "health_orientation": ("Health disengaged", "Health aware", "Health balanced", "Health focused", "Highly health focused"),
    }
    return descriptions.get(name, ("Very low", "Low", "Moderate", "High", "Very high"))[min(4, int(_clip(value) * 5))]


def _domain_base(domain: str, traits: dict[str, float], income_factor: float, age: int, children: int) -> float:
    mapping = {
        "commerce": .35 * traits["digital_adoption"] + .25 * income_factor + .2 * traits["novelty_seeking"] + .2 * traits["luxury_orientation"],
        "technology": .6 * traits["technology_affinity"] + .3 * traits["digital_adoption"] + .1 * traits["openness"],
        "media": .4 * traits["digital_adoption"] + .3 * traits["social_orientation"] + .3 * traits["cultural_openness"],
        "food": .4 * traits["openness"] + .25 * income_factor + .2 * traits["social_orientation"] + .15 * traits["health_orientation"],
        "travel": .35 * income_factor + .3 * traits["novelty_seeking"] + .2 * traits["cultural_openness"] + .15 * traits["risk_tolerance"],
        "fashion": .35 * traits["luxury_orientation"] + .25 * income_factor + .25 * traits["social_orientation"] + .15 * traits["openness"],
        "mobility": .45 * income_factor + .25 * traits["environmental_awareness"] + .2 * traits["technology_affinity"] + .1 * (1 - children / 4),
        "wellness": .65 * traits["health_orientation"] + .2 * traits["planning_orientation"] + .15 * traits["conscientiousness"],
        "home": .45 * income_factor + .25 * traits["planning_orientation"] + .2 * traits["environmental_awareness"] + .1 * min(children / 2, 1),
        "hobbies": .35 * traits["openness"] + .3 * traits["social_orientation"] + .2 * traits["novelty_seeking"] + .15 * traits["health_orientation"],
        "finance": .35 * income_factor + .3 * traits["planning_orientation"] + .2 * traits["conscientiousness"] + .15 * traits["digital_adoption"],
    }
    return _clip(mapping[domain] - max(0, age - 64) * .004)


def generate_profile(seed: int, index: int, country: str = "India", age_range=None, preferred_language=None, persona=None) -> dict:
    if country != "India": raise ValueError("Only India is currently supported")
    if preferred_language and preferred_language not in LANGUAGES: raise ValueError("Unsupported preferred_language")
    if persona and persona not in PERSONAS: raise ValueError("Unsupported persona")
    rng = profile_rng(seed, index)
    age = _age(rng, age_range); stage = _stage(age); place = choose(rng, LOCATIONS)
    language = preferred_language or place["language"]
    traits = {key: _score(rng, .5, .19) for key in ("openness", "conscientiousness", "extraversion", "agreeableness", "risk_tolerance", "novelty_seeking", "social_orientation", "health_orientation", "luxury_orientation", "planning_orientation", "cultural_openness", "environmental_awareness", "technology_affinity", "price_sensitivity")}
    traits["digital_adoption"] = _score(rng, .65 * traits["technology_affinity"] + .2 * traits["openness"] + .15 * (1 - max(age - 25, 0) / 70))
    if stage == "Teenager":
        education, employment, career, experience = "School education", "School student", "None", 0
    elif stage == "University Student":
        education, employment, career, experience = "Undergraduate", "Student", "None", 0
    elif stage == "Retired":
        education, employment, career, experience = choose(rng, ["School education", "Undergraduate", "Postgraduate"], [25, 45, 30]), "Retired", "Former professional", max(0, age - 22 - rng.randint(0, 5))
    else:
        education = choose(rng, ["School education", "Undergraduate", "Postgraduate", "Professional diploma"], [12, 48, 23, 17])
        experience = max(0, min(age - 16, age - (22 if education in {"Undergraduate", "Postgraduate"} else 18) - rng.randint(0, 3)))
        career = "Early" if experience < 5 else choose(rng, ["Mid-level", "Senior", "Leadership"], [50, 38, 12 + (10 if experience > 16 else 0)])
        employment = choose(rng, ["Employed full-time", "Self-employed", "Employed part-time"], [75, 15, 10])
    marital = "Single" if age < 21 else choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [max(12, 65 - age), 20, max(10, age - 10), 3 if age > 35 else 0])
    children = 0 if age < 20 or marital not in {"Married", "Separated/Widowed"} else choose(rng, [0, 1, 2, 3], [30, 43, 23, 4])
    industry = choose(rng, place["industries"])
    income_base = {"None": 0, "Early": 420000, "Mid-level": 800000, "Senior": 1350000, "Leadership": 2300000, "Former professional": 600000}.get(career, 300000)
    annual_income = 0 if employment in {"School student", "Student"} else int(max(120000, income_base * (0.75 + .5 * traits["luxury_orientation"]) * (1 + min(experience, 25) / 100)))
    monthly_income = annual_income // 12
    household_income = annual_income + (int(annual_income * rng.uniform(.25, .9)) if marital == "Married" else 0)
    expense_ratio = min(.92, .38 + children * .06 + .18 * traits["luxury_orientation"] - .16 * traits["planning_orientation"])
    expenses = int(monthly_income * expense_ratio); savings = monthly_income - expenses
    income_factor = _clip(annual_income / 2600000)
    persona_value = persona or choose(rng, list(PERSONAS), [1 + (2 * traits["technology_affinity"] if name == "Sci-Fi Enthusiast" else 0) + (2 * traits["cultural_openness"] if name == "International Cinema Explorer" else 0) + (children if name == "Family Entertainment Viewer" else 0) for name in PERSONAS])
    occupation = employment if employment in {"School student", "Student", "Retired"} else f"{career} {industry} professional"
    degree_years = {"School education": 10, "Undergraduate": 15, "Postgraduate": 17, "Professional diploma": 13}[education]
    profile = {
        "profile_id": f"IN-{seed:08x}-{index:05d}", "profile_schema_version": PROFILE_SCHEMA_VERSION, "age": age, "age_band": next(f"{a}-{b}" for a,b,_ in AGE_BANDS if a <= age <= b), "date_of_birth": str(date(2026, 8, 20) - timedelta(days=age * 365 + rng.randint(0, 364))), "gender": choose(rng, ["Female", "Male", "Non-binary"], [48, 48, 4]), "country": "India", "state": CITY_STATES[place["city"]], "city": place["city"], "region": place["regions"][0], "urban_rural": "Urban", "nationality": "Indian", "primary_language": language, "preferred_language": language if traits["cultural_openness"] < .65 else choose(rng, [language, "English"]), "population_segment": "Working professional" if employment.startswith("Employed") else stage, "life_stage": stage,
        "marital_status": marital, "relationship_status": "Married" if marital == "Married" else marital, "number_of_children": children, "dependents_count": children + (1 if age > 45 and rng.random() < .2 else 0), "household_size": max(1, 1 + (1 if marital == "Married" else 0) + children + (1 if age < 30 and rng.random() < .35 else 0)), "family_type": "Nuclear" if marital == "Married" else "Single-person" if age > 27 else "With parents", "living_arrangement": "Owned home" if age > 35 and income_factor > .35 else "Rented home" if age > 23 else "Family home", "parents_in_household": age < 30 and rng.random() < .65, "siblings_count": choose(rng, [0,1,2,3], [18,48,26,8]),
        "education_level": education, "highest_degree": education, "field_of_study": choose(rng, ["Engineering", "Business", "Arts and humanities", "Science", "Commerce", "Healthcare"]), "institution_type": choose(rng, ["Public", "Private", "Professional institute"]), "graduation_status": "In progress" if employment == "Student" else "Completed", "years_of_education": degree_years, "academic_orientation": _category((traits["openness"] + traits["conscientiousness"]) / 2), "education_quality": _category(.4 + income_factor * .35 + traits["conscientiousness"] * .25),
        "employment_status": employment, "occupation": occupation, "industry": industry, "job_function": industry, "career_level": career, "years_of_experience": experience, "employer_type": "Large enterprise" if career in {"Senior", "Leadership"} else choose(rng, ["Startup", "Mid-size company", "Large enterprise", "Public sector"]), "work_mode": "Remote/hybrid" if traits["digital_adoption"] > .55 and industry in {"Technology", "Consulting", "Media"} else "On-site", "weekly_work_hours": 0 if employment in {"School student", "Student", "Retired"} else rng.randint(38, 55), "leadership_status": "People manager" if career == "Leadership" else "Individual contributor", "job_stability": _category((min(experience, 15) / 15 + traits["conscientiousness"]) / 2), "career_growth_orientation": _category((traits["novelty_seeking"] + traits["planning_orientation"]) / 2),
        "annual_income": annual_income, "monthly_income": monthly_income, "income_band": "Limited" if annual_income < 300000 else "Modest" if annual_income < 700000 else "Comfortable" if annual_income < 1400000 else "Affluent", "household_income": household_income, "monthly_expenses": expenses, "monthly_savings": savings, "savings_rate": round(savings / monthly_income, 3) if monthly_income else 0, "financial_stability": _category((traits["planning_orientation"] + min(savings / max(monthly_income,1) * 2, 1)) / 2), "spending_power": _category(income_factor), "price_sensitivity": traits["price_sensitivity"], "financial_risk_tolerance": _category(traits["risk_tolerance"]), "investment_interest": _category((income_factor + traits["risk_tolerance"]) / 2), "credit_behavior": _category((income_factor + traits["conscientiousness"]) / 2),
        "shopping_frequency": _category((income_factor + traits["digital_adoption"]) / 2), "online_shopping_frequency": _category(traits["digital_adoption"]), "offline_shopping_frequency": _category(traits["social_orientation"]), "preferred_marketplace": "Value marketplace" if traits["price_sensitivity"] > .6 else "Brand marketplace", "preferred_category": "Home and family" if children else "Electronics" if traits["technology_affinity"] > .6 else "Fashion", "average_order_value": int(600 + income_factor * 4800 + traits["luxury_orientation"] * 2200), "discount_sensitivity": _category(traits["price_sensitivity"]), "brand_loyalty": _category((traits["conscientiousness"] + traits["price_sensitivity"]) / 2), "impulse_buying": _category(1 - traits["planning_orientation"]), "research_before_purchase": _category((traits["openness"] + traits["planning_orientation"]) / 2), "premium_preference": _category((income_factor + traits["luxury_orientation"]) / 2), "cart_abandonment_tendency": _category(traits["price_sensitivity"]),
        "technology_affinity": traits["technology_affinity"], "digital_adoption": traits["digital_adoption"], "daily_screen_time_hours": round(1.5 + traits["digital_adoption"] * 6 - max(age-50,0)*.03, 1), "device_preference": "Smartphone-first" if traits["technology_affinity"] < .6 else "Multi-device", "ai_interest": _category((traits["technology_affinity"] + traits["openness"]) / 2), "social_media_activity": _category((traits["social_orientation"] + traits["digital_adoption"]) / 2), "instagram_usage": _category((traits["social_orientation"] + (1 if age < 40 else .35)) / 2), "youtube_usage": _category(traits["digital_adoption"]), "facebook_usage": _category(.65 if age > 40 else .35), "linkedin_usage": _category(.75 if employment.startswith("Employed") else .25), "messaging_frequency": _category(traits["social_orientation"]), "content_creation": _category((traits["openness"] + traits["social_orientation"]) / 2), "influencer_following": _category(traits["novelty_seeking"]),
        "entertainment_persona": persona_value, "preferred_ott_platform": choose(rng, OTT_BY_LANGUAGE.get(language, OTT_BY_LANGUAGE["English"])), "preferred_movie_genres": PERSONAS[persona_value][:2], "streaming_hours_weekly": round(2 + traits["digital_adoption"] * 14, 1), "gaming_frequency": _category(traits["technology_affinity"] * (1.1 if age < 40 else .7)), "music_frequency": _category((traits["openness"] + traits["digital_adoption"]) / 2), "preferred_music_genre": choose(rng, ["Film music", "Pop", "Indie", "Regional", "Classical"]), "regional_music_preference": _category(.5 + (.2 if language != "English" else 0)), "international_music_preference": _category(traits["cultural_openness"]),
        "dining_frequency": _category((income_factor + traits["social_orientation"]) / 2), "vegetarian_preference": choose(rng, ["Vegetarian", "Non-vegetarian", "Flexible"], [28, 48, 24]), "food_experimentation": _category(traits["openness"]), "travel_frequency": _category(_domain_base("travel", traits, income_factor, age, children)), "preferred_destination_type": "Family and relaxation" if children else "Culture and cities" if traits["cultural_openness"] > .6 else "Nature and short breaks", "travel_budget": _category(income_factor), "planning_behavior": _category(traits["planning_orientation"]), "booking_behavior": "Digital self-service" if traits["digital_adoption"] > .5 else "Assisted booking", "adventure_interest": _category((traits["risk_tolerance"] + traits["novelty_seeking"]) / 2), "home_ownership": "Owner" if age > 35 and income_factor > .4 else "Renter", "housing_type": "Apartment" if place["city"] in {"Mumbai", "Bengaluru", "Delhi", "Chennai"} else "Independent home", "neighborhood_type": "Urban residential", 
        **{key: _trait_label(key, value) for key, value in traits.items()}, "decision_speed": _category(traits["risk_tolerance"]), "comparison_behavior": _category(traits["planning_orientation"]), "analytical_orientation": _category((traits["openness"] + traits["planning_orientation"]) / 2), "recommendation_dependence": _category(traits["social_orientation"]), "brand_trust": _category(traits["conscientiousness"]), "information_seeking": _category(traits["openness"]), "digital_payment_preference": _category(traits["digital_adoption"]), "card_usage": _category((income_factor + traits["digital_adoption"]) / 2), "wallet_usage": _category(traits["digital_adoption"]), "cash_usage": _category(1-traits["digital_adoption"]), "recurring_payment_behavior": _category((traits["digital_adoption"] + traits["conscientiousness"]) / 2), "pet_ownership": "Yes" if rng.random() < .22 else "No", "hobby_count": max(1, round(1 + (traits["openness"] + traits["social_orientation"]) * 3)), "reading_frequency": _category(traits["openness"]), "sports_interest": _category((traits["health_orientation"] + traits["social_orientation"]) / 2), "photography_interest": _category((traits["openness"] + traits["cultural_openness"]) / 2), "creative_interest": _category(traits["openness"]), "volunteering_interest": _category(traits["agreeableness"]),
    }
    for domain, topics in DOMAIN_TOPICS.items():
        base = _domain_base(domain, traits, income_factor, age, children)
        for topic in topics:
            topic_adjustment = .12 if any(word in topic for word in ("international", "artificial", "luxury", "electric", "premium")) and traits["openness"] > .55 else 0
            for measure in MEASURES:
                measure_adjustment = {"interest_score": .04, "usage_frequency_score": 0, "purchase_intent_score": income_factor * .08, "research_intensity_score": traits["planning_orientation"] * .08}[measure]
                profile[f"{domain}_{topic}_{measure}"] = _five_level(_score(rng, base + topic_adjustment + measure_adjustment), measure)
    missing = set(PROFILE_COLUMNS) - profile.keys()
    if missing: raise RuntimeError(f"Generator missed schema columns: {sorted(missing)}")
    validate_profile(profile)
    return profile


def generate_profiles(count: int, seed: int, country="India", age_range=None, preferred_language=None, persona=None, workers=1) -> list[dict]:
    return [generate_profile(seed, index + 1, country, age_range, preferred_language, persona) for index in range(count)]
