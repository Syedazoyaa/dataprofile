"""Request models and the single source of truth for profile columns."""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

PROFILE_SCHEMA_VERSION = "1.1"

PERSONALITY_ARCHETYPES = (
    "Analytical",
    "Adventurous",
    "Social",
    "Creative",
    "Disciplined",
    "Empathetic",
    "Independent",
    "Practical",
    "Ambitious",
    "Balanced",
)

@dataclass(frozen=True)
class FeatureSpec:
    name: str
    domain: str
    value_type: str
    dependency: str

# Semantic feature families. Each value describes a real preference or behavior;
# shared latent traits generate the related observable scores.
DOMAIN_TOPICS = {
    "commerce": ("electronics", "fashion", "groceries", "home_furnishing", "beauty", "travel_booking", "books", "fitness", "automotive", "baby_care", "pet_care", "luxury_goods", "food_delivery", "furniture", "telecom"),
    "technology": ("smartphone", "laptop", "smart_tv", "wearable", "gaming_console", "cloud_storage", "video_calling", "productivity_app", "online_learning", "artificial_intelligence", "cybersecurity", "smart_home"),
    "media": ("movies", "series", "short_video", "news", "podcasts", "sports_content", "documentaries", "music_streaming", "gaming_content", "regional_content", "international_content", "live_events"),
    "food": ("home_cooking", "restaurant_dining", "food_delivery", "street_food", "healthy_food", "fast_food", "regional_cuisine", "global_cuisine", "premium_dining", "desserts", "coffee", "meal_planning"),
    "travel": ("domestic_travel", "international_travel", "weekend_breaks", "family_travel", "business_travel", "adventure_travel", "cultural_travel", "nature_travel", "budget_travel", "luxury_travel"),
    "fashion": ("casual_wear", "formal_wear", "ethnic_wear", "footwear", "accessories", "grooming", "beauty_products", "sustainable_fashion"),
    "mobility": ("car", "two_wheeler", "electric_vehicle", "public_transport", "ride_hailing", "walking", "cycling", "intercity_transport"),
    "wellness": ("fitness", "running", "yoga", "gym", "outdoor_activity", "sleep_hygiene", "nutrition", "preventive_wellness", "mental_wellbeing_content", "health_tracking"),
    "home": ("home_ownership", "rental_living", "interior_design", "home_improvement", "home_appliances", "smart_home", "gardening", "household_services", "energy_saving", "neighborhood_engagement"),
    "hobbies": ("reading", "sports", "photography", "gaming", "creative_arts", "cooking", "volunteering", "learning", "collecting", "social_clubs"),
    "finance": ("saving", "investing", "insurance", "credit_card", "digital_wallet", "upi_payment", "subscription", "budgeting", "financial_learning", "charitable_giving"),
}
MEASURES = ("interest_score", "usage_frequency_score", "purchase_intent_score", "research_intensity_score")

CORE_FIELDS = (
    ("personality_name", "personality", "string", "derived archetype from latent traits (openness,conscientiousness,extraversion,agreeableness,risk,novelty,social,health,luxury,planning,cultural,environmental,tech,price)"),
    ("profile_id", "identity", "string", "seed + profile index"), ("profile_schema_version", "identity", "string", "schema version"), ("age", "demographics", "integer", "weighted age band"), ("age_band", "demographics", "category", "age"), ("date_of_birth", "demographics", "date", "age + seed"), ("gender", "demographics", "category", "weighted demographic distribution"), ("country", "location", "string", "request"), ("state", "location", "string", "city"), ("city", "location", "string", "location record"), ("region", "location", "string", "location record"), ("urban_rural", "location", "category", "city"), ("nationality", "demographics", "string", "country"), ("primary_language", "language", "category", "location/request"), ("preferred_language", "language", "category", "language + cultural openness"), ("population_segment", "demographics", "category", "age + income"), ("life_stage", "demographics", "category", "age + family"),
    ("marital_status", "family", "category", "age + life stage"), ("relationship_status", "family", "category", "marital status"), ("number_of_children", "family", "integer", "age + marital status"), ("dependents_count", "family", "integer", "children + life stage"), ("household_size", "family", "integer", "children + living arrangement"), ("family_type", "family", "category", "marital status + children"), ("living_arrangement", "family", "category", "age + income"), ("parents_in_household", "family", "boolean", "age + life stage"), ("siblings_count", "family", "integer", "demographic distribution"),
    ("education_level", "education", "category", "age + life stage"), ("highest_degree", "education", "category", "education level"), ("field_of_study", "education", "category", "education + technology affinity"), ("institution_type", "education", "category", "education + income"), ("graduation_status", "education", "category", "age + education"), ("years_of_education", "education", "integer", "education level"), ("academic_orientation", "education", "category", "openness + conscientiousness"), ("education_quality", "education", "category", "income + education"),
    ("employment_status", "career", "category", "life stage"), ("occupation", "career", "category", "career level + industry + job function"), ("industry", "career", "category", "location + education"), ("job_function", "career", "category", "industry + field of study"), ("professional_training", "career", "category", "education + industry + career pathway (plausibility marker, never a gate)"), ("career_level", "career", "category", "age + experience + education"), ("years_of_experience", "career", "integer", "age + education"), ("employer_type", "career", "category", "industry + career level"), ("work_mode", "career", "category", "industry + technology affinity"), ("weekly_work_hours", "career", "integer", "employment + career level"), ("leadership_status", "career", "category", "career level"), ("job_stability", "career", "category", "age + career level"), ("career_growth_orientation", "career", "category", "novelty + career stage"),
    ("annual_income", "finance", "integer", "career level + experience + education"), ("monthly_income", "finance", "integer", "annual income"), ("income_band", "finance", "category", "annual income"), ("household_income", "finance", "integer", "income + household structure"), ("financial_support_source", "finance", "category", "employment + income (support when personal income is zero)"), ("monthly_expenses", "finance", "integer", "income + household + support"), ("monthly_savings", "finance", "integer", "income - expenses (floored at zero when supported)"), ("savings_rate", "finance", "number", "savings / income"), ("financial_stability", "finance", "category", "savings + job stability"), ("spending_power", "finance", "category", "income + household"), ("price_sensitivity", "traits", "number", "latent trait"), ("financial_risk_tolerance", "finance", "category", "risk tolerance"), ("investment_interest", "finance", "category", "income + risk tolerance"), ("credit_behavior", "finance", "category", "income + conscientiousness"),
    ("shopping_frequency", "commerce", "category", "income + digital adoption"), ("online_shopping_frequency", "commerce", "category", "digital adoption"), ("offline_shopping_frequency", "commerce", "category", "social orientation"), ("preferred_marketplace", "commerce", "category", "price sensitivity + age"), ("preferred_category", "commerce", "category", "life stage + traits"), ("average_order_value", "commerce", "integer", "income + luxury orientation"), ("discount_sensitivity", "commerce", "category", "price sensitivity"), ("brand_loyalty", "commerce", "category", "conscientiousness + price sensitivity"), ("impulse_buying", "commerce", "category", "impulsivity"), ("research_before_purchase", "commerce", "category", "analytical orientation"), ("premium_preference", "commerce", "category", "income + luxury orientation"), ("cart_abandonment_tendency", "commerce", "category", "price sensitivity"),
    ("technology_affinity", "traits", "number", "latent trait"), ("digital_adoption", "traits", "number", "technology + age"), ("daily_screen_time_hours", "technology", "number", "digital adoption + age"), ("device_preference", "technology", "category", "technology affinity"), ("ai_interest", "technology", "category", "technology affinity + curiosity"), ("social_media_activity", "social_media", "category", "social orientation + digital adoption"), ("instagram_usage", "social_media", "category", "age + social orientation"), ("youtube_usage", "social_media", "category", "digital adoption"), ("facebook_usage", "social_media", "category", "age"), ("linkedin_usage", "social_media", "category", "employment"), ("messaging_frequency", "social_media", "category", "social orientation"), ("content_creation", "social_media", "category", "openness + social orientation"), ("influencer_following", "social_media", "category", "novelty seeking"),
    ("entertainment_persona", "media", "category", "technology + cultural openness + family"), ("preferred_ott_platform", "media", "category", "language"), ("preferred_movie_genres", "media", "array", "persona"), ("streaming_hours_weekly", "media", "number", "entertainment engagement"), ("gaming_frequency", "media", "category", "technology affinity"), ("music_frequency", "music", "category", "entertainment engagement"), ("preferred_music_genre", "music", "category", "age + openness"), ("regional_music_preference", "music", "category", "language"), ("international_music_preference", "music", "category", "cultural openness"),
    ("dining_frequency", "food", "category", "income + social orientation"), ("vegetarian_preference", "food", "category", "probabilistic preference"), ("food_experimentation", "food", "category", "openness"), ("travel_frequency", "travel", "category", "income + novelty seeking"), ("preferred_destination_type", "travel", "category", "family + openness"), ("travel_budget", "travel", "category", "income"), ("planning_behavior", "decision", "category", "planning orientation"), ("booking_behavior", "travel", "category", "digital adoption + planning"), ("adventure_interest", "travel", "category", "risk + novelty"), ("home_ownership", "home", "category", "age + income"), ("housing_type", "home", "category", "household + income"), ("neighborhood_type", "home", "category", "city"),
    ("openness", "traits", "number", "latent trait"), ("conscientiousness", "traits", "number", "latent trait"), ("extraversion", "traits", "number", "latent trait"), ("agreeableness", "traits", "number", "latent trait"), ("risk_tolerance", "traits", "number", "latent trait"), ("novelty_seeking", "traits", "number", "latent trait"), ("social_orientation", "traits", "number", "latent trait"), ("health_orientation", "traits", "number", "latent trait"), ("luxury_orientation", "traits", "number", "latent trait"), ("planning_orientation", "traits", "number", "latent trait"), ("cultural_openness", "traits", "number", "latent trait"), ("environmental_awareness", "traits", "number", "latent trait"),
    ("decision_speed", "decision", "category", "risk + planning"), ("comparison_behavior", "decision", "category", "analytical orientation"), ("analytical_orientation", "decision", "category", "openness + planning"), ("recommendation_dependence", "decision", "category", "social orientation"), ("brand_trust", "decision", "category", "conscientiousness"), ("information_seeking", "decision", "category", "curiosity"), ("digital_payment_preference", "payments", "category", "digital adoption"), ("card_usage", "payments", "category", "income + digital adoption"), ("wallet_usage", "payments", "category", "digital adoption"), ("cash_usage", "payments", "category", "digital adoption"), ("recurring_payment_behavior", "payments", "category", "digital adoption + conscientiousness"), ("pet_ownership", "hobbies", "category", "household + lifestyle"), ("hobby_count", "hobbies", "integer", "openness + leisure"), ("reading_frequency", "hobbies", "category", "openness"), ("sports_interest", "hobbies", "category", "health + social orientation"), ("photography_interest", "hobbies", "category", "openness + travel"),     ("creative_interest", "hobbies", "category", "openness"), ("volunteering_interest", "hobbies", "category", "agreeableness"),
    ("profile_summary", "profile", "string", "derived narrative from generated attributes"), ("social_disposition", "personality", "category", "extraversion + social orientation (Introvert/Ambivert/Extrovert)"), ("review_influence", "decision", "category", "openness + conscientiousness (information-driven; distinct from recommendation dependence)"), ("interactive_content_engagement", "digital", "category", "digital adoption + novelty (survey/quiz)"), ("social_shopping_tendency", "commerce", "category", "social orientation + online shopping"), ("advertisement_responsiveness", "marketing", "category", "novelty + social orientation + age"), ("social_consumer_tendency", "social_media", "category", "social orientation + digital adoption (Consumer)"), ("social_creator_tendency", "social_media", "category", "content creation + novelty (Creator)"), ("social_engagement_level", "social_media", "category", "activity + messaging + extraversion (Engagement)"), ("trend_sensitivity", "social_media", "category", "novelty + cultural openness (Trend Sensitivity)"), ("influencer_influence", "social_media", "category", "recommendation dependence + following (Influencer Influence)"), ("brand_interaction_tendency", "social_media", "category", "brand loyalty + activity (Brand Interaction)"),
)
GEOGRAPHY_FIELDS = (
    ("country_code", "location", "string", "geographic context"),
    ("currency", "finance", "string", "geographic context"),
    ("cultural_context", "culture", "category", "geographic probability distribution"),
    ("religious_affiliation", "culture", "category", "geographic probability distribution"),
    ("local_food_pattern", "food", "category", "geographic context + health orientation"),
    ("available_payment_method", "payments", "category", "geographic payment ecosystem"),
    ("primary_transport_mode", "mobility", "category", "geographic infrastructure + income"),
    ("transport_infrastructure", "mobility", "category", "geographic context"),
)

def build_feature_schema() -> tuple[FeatureSpec, ...]:
    fields = [FeatureSpec(*item) for item in (*CORE_FIELDS, *GEOGRAPHY_FIELDS)]
    for domain, topics in DOMAIN_TOPICS.items():
        for topic in topics:
            for measure in MEASURES:
                fields.append(FeatureSpec(f"{domain}_{topic}_{measure}", domain, "category", f"latent traits + {domain} behavior"))
    names = [field.name for field in fields]
    if len(names) != len(set(names)) or len(fields) < 500:
        raise RuntimeError("Profile schema must contain at least 500 unique columns")
    return tuple(fields)

PROFILE_SCHEMA = build_feature_schema()
PROFILE_COLUMNS = tuple(field.name for field in PROFILE_SCHEMA)

# Central core/summary field set (single source for summary views and downloads).
CORE_PROFILE_FIELDS = (
    "personality_name", "profile_id", "profile_summary", "age", "age_band", "gender",
    "country", "state", "city", "nationality", "primary_language", "life_stage",
    "marital_status", "household_size", "education_level", "field_of_study",
    "employment_status", "occupation", "industry", "job_function", "career_level",
    "years_of_experience", "annual_income", "monthly_income", "income_band",
    "monthly_expenses", "social_disposition", "financial_risk_tolerance",
    "decision_speed", "price_sensitivity", "brand_loyalty", "research_before_purchase",
    "shopping_frequency", "online_shopping_frequency", "average_order_value",
    "preferred_marketplace", "review_influence", "recommendation_dependence",
    "digital_adoption", "social_media_activity", "preferred_music_genre",
    "travel_frequency", "vegetarian_preference",
)

def _core_fields_valid() -> tuple[str, ...]:
    unknown = [name for name in CORE_PROFILE_FIELDS if name not in PROFILE_COLUMNS]
    if unknown:
        raise RuntimeError(f"Core profile fields missing from schema: {unknown}")
    if len(set(CORE_PROFILE_FIELDS)) != len(CORE_PROFILE_FIELDS):
        raise RuntimeError("Core profile fields contain duplicates")
    return CORE_PROFILE_FIELDS

CORE_PROFILE_FIELDS = _core_fields_valid()

class GenerateRequest(BaseModel):
    count: int = Field(default=1, ge=1)
    seed: int = Field(default=42, ge=0)
    # An omitted geographic scope is intentionally global.  A country is only
    # used when the caller explicitly selects the specific-country mode.
    country_mode: Literal["specific", "global", "random", "continent", "region", "subregion"] = "global"
    country: str | None = None
    countries: list[str] | None = None
    region: str | None = None
    continent: str | None = None
    subregion: str | None = None
    age_range: tuple[int, int] | None = None
    persona: str | None = None
    preferred_language: str | None = None
    format: Literal["json", "csv"] = "json"
    view: Literal["full", "summary"] = "full"
    scope: Literal["bulk", "individual"] = "bulk"
    profile_index: int | None = Field(default=None, ge=1)

    @field_validator("preferred_language")
    @classmethod
    def normalize_language(cls, value: str | None) -> str | None:
        return value.strip() if value else value

    @model_validator(mode="after")
    def valid_age_range(self):
        if self.age_range and (self.age_range[0] < 16 or self.age_range[1] > 78 or self.age_range[0] > self.age_range[1]):
            raise ValueError("age_range must be between 16 and 78 with min <= max")
        if self.countries is not None and not self.countries:
            raise ValueError("countries must be a non-empty list when provided")
        # Preserve the concise, established {"country": "..."} request form
        # without making any country an implicit default.
        if self.country and self.country_mode == "global":
            if "country_mode" not in self.model_fields_set:
                self.country_mode = "specific"
            else:
                raise ValueError("country must not be provided when country_mode is 'global'")
        if self.country_mode == "specific" and not self.country and not self.countries:
            raise ValueError("country is required when country_mode is 'specific'")
        if self.profile_index is not None and self.profile_index > self.count:
            raise ValueError("profile_index must be <= count")
        return self


class GenerationSpec(BaseModel):
    """Reusable generation parameters shared by analytics endpoints."""

    count: int = Field(default=200, ge=1, le=10000)
    seed: int = Field(default=42, ge=0)
    country_mode: Literal["specific", "global", "random", "continent", "region", "subregion"] = "global"
    country: str | None = None
    countries: list[str] | None = None
    region: str | None = None
    continent: str | None = None
    subregion: str | None = None
    age_range: tuple[int, int] | None = None
    persona: str | None = None
    preferred_language: str | None = None

    @model_validator(mode="after")
    def valid_age_range(self):
        if self.age_range and (self.age_range[0] < 16 or self.age_range[1] > 78 or self.age_range[0] > self.age_range[1]):
            raise ValueError("age_range must be between 16 and 78 with min <= max")
        if self.countries is not None and not self.countries:
            raise ValueError("countries must be a non-empty list when provided")
        if self.country and self.country_mode == "global":
            if "country_mode" not in self.model_fields_set:
                self.country_mode = "specific"
            else:
                raise ValueError("country must not be provided when country_mode is 'global'")
        if self.country_mode == "specific" and not self.country and not self.countries:
            raise ValueError("country is required when country_mode is 'specific'")
        return self


class ProfileFilter(BaseModel):
    """All fields optional; only provided fields constrain the population."""

    age_min: int | None = Field(default=None, ge=16, le=78)
    age_max: int | None = Field(default=None, ge=16, le=78)
    gender: str | None = None
    country: str | list[str] | None = None
    education: str | None = None
    employment_status: str | None = None
    career_level: str | None = None
    income_band: str | None = None
    research_intensity: str | None = None
    comparison_behaviour: str | None = None
    purchase_intent: str | None = None
    price_sensitivity: str | None = None
    brand_loyalty: str | None = None
    decision_speed: str | None = None
    planning_behaviour: str | None = None
    impulse_buying: str | None = None
    behavioural_segment: str | None = None

    @model_validator(mode="after")
    def valid_age_bounds(self):
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("age_min must be <= age_max")
        return self


class FilterRequest(BaseModel):
    generation: GenerationSpec = Field(default_factory=GenerationSpec)
    filters: ProfileFilter = Field(default_factory=ProfileFilter)


class SegmentsRequest(BaseModel):
    generation: GenerationSpec = Field(default_factory=GenerationSpec)


class AnalyticsRequest(BaseModel):
    generation: GenerationSpec = Field(default_factory=GenerationSpec)
    filters: ProfileFilter = Field(default_factory=ProfileFilter)


class PopulationSpec(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    generation: GenerationSpec = Field(default_factory=GenerationSpec)


class CompareRequest(BaseModel):
    """Two-country comparison: exactly two populations, each pinned to one
    explicitly selected country (no global or multi-country sides)."""

    populations: list[PopulationSpec]

    @field_validator("populations")
    @classmethod
    def exactly_two_countries(cls, value: list[PopulationSpec]) -> list[PopulationSpec]:
        if len(value) != 2:
            raise ValueError("comparison requires exactly two populations (Country A + Country B)")
        labels = [p.label for p in value]
        if len(set(labels)) != len(labels):
            raise ValueError("population labels must be unique")
        return value
