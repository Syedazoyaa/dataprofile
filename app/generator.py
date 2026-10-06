from datetime import date, timedelta

from .personas import PERSONAS
from .derived import derive_extras
from .coherence import (
    choose_language,
    financial_support_for,
    job_function_for_industry,
    occupation_title,
    professional_training_for,
    resolve_life_stage,
    supported_student_expenses,
)
from .geography import get_context, supported_languages
from .rules import validate_profile
from .schemas import DOMAIN_TOPICS, MEASURES, PERSONALITY_ARCHETYPES, PROFILE_COLUMNS, PROFILE_SCHEMA_VERSION
from .utils import choose, level, profile_rng

AGE_BANDS = ((16, 17, 3), (18, 22, 13), (23, 29, 20), (30, 39, 24), (40, 49, 18), (50, 59, 12), (60, 69, 7), (70, 78, 3))
LANGUAGES = supported_languages()

FIELD_OPTIONS = ["Engineering", "Business", "Arts and humanities", "Science", "Commerce", "Healthcare"]
INDUSTRY_FIELD_WEIGHTS = {
    "Engineering": {"Technology": 3.0, "Manufacturing": 2.2, "Automotive": 2.0, "Energy": 1.6, "Construction": 1.2, "Technology": 3.0},
    "Business": {"Finance": 2.8, "Consulting": 2.0, "Retail": 1.6, "Technology": 1.4, "Services": 1.8, "Trade": 1.2},
    "Arts and humanities": {"Media": 2.6, "Creative services": 2.4, "Education": 2.0, "Retail": 1.0, "Services": 1.2},
    "Science": {"Healthcare": 2.2, "Technology": 2.0, "Manufacturing": 1.4, "Education": 1.6, "Services": 1.2},
    "Commerce": {"Finance": 2.5, "Trade": 2.0, "Services": 1.8, "Retail": 1.6, "Technology": 1.2},
    "Healthcare": {"Healthcare": 3.2, "Services": 1.5, "Education": 1.2, "Technology": 1.0},
}
EDUCATION_EDU_SCORE = {"School education": 0.30, "Professional diploma": 0.50, "Undergraduate": 0.65, "Postgraduate": 0.85}
CAREER_SCORE = {"None": 0.0, "Early": 0.30, "Mid-level": 0.60, "Senior": 0.85, "Leadership": 1.0, "Former professional": 0.55}

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

AGE_BAND_CHOICES = list(AGE_BANDS)
AGE_BAND_WEIGHTS = [band[2] for band in AGE_BANDS]

def _age(rng, age_range) -> int:
    if age_range:
        return rng.randint(*age_range)
    band = choose(rng, AGE_BAND_CHOICES, AGE_BAND_WEIGHTS)
    return rng.randint(band[0], band[1])

def _category(value: float) -> str:
    return level(value)

def _five_level(value: float, measure: str) -> str:
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

# --- Archetype-anchored personality generation (behavioral anchor) ---
ARCHETYPE_TARGETS = {
    "Analytical":   {"openness":0.78, "conscientiousness":0.80, "extraversion":0.42, "agreeableness":0.50, "risk_tolerance":0.28, "novelty_seeking":0.55, "social_orientation":0.42, "health_orientation":0.55, "luxury_orientation":0.42, "planning_orientation":0.80, "cultural_openness":0.62, "environmental_awareness":0.55, "technology_affinity":0.72, "price_sensitivity":0.55},
    "Adventurous":  {"openness":0.78, "conscientiousness":0.38, "extraversion":0.76, "agreeableness":0.48, "risk_tolerance":0.78, "novelty_seeking":0.82, "social_orientation":0.55, "health_orientation":0.60, "luxury_orientation":0.55, "planning_orientation":0.30, "cultural_openness":0.74, "environmental_awareness":0.48, "technology_affinity":0.62, "price_sensitivity":0.42},
    "Social":       {"openness":0.62, "conscientiousness":0.48, "extraversion":0.82, "agreeableness":0.76, "risk_tolerance":0.55, "novelty_seeking":0.62, "social_orientation":0.82, "health_orientation":0.55, "luxury_orientation":0.55, "planning_orientation":0.42, "cultural_openness":0.72, "environmental_awareness":0.48, "technology_affinity":0.55, "price_sensitivity":0.48},
    "Creative":     {"openness":0.84, "conscientiousness":0.38, "extraversion":0.62, "agreeableness":0.52, "risk_tolerance":0.62, "novelty_seeking":0.76, "social_orientation":0.55, "health_orientation":0.48, "luxury_orientation":0.55, "planning_orientation":0.35, "cultural_openness":0.82, "environmental_awareness":0.70, "technology_affinity":0.62, "price_sensitivity":0.48},
    "Disciplined":  {"openness":0.48, "conscientiousness":0.84, "extraversion":0.42, "agreeableness":0.55, "risk_tolerance":0.26, "novelty_seeking":0.35, "social_orientation":0.42, "health_orientation":0.70, "luxury_orientation":0.35, "planning_orientation":0.84, "cultural_openness":0.48, "environmental_awareness":0.55, "technology_affinity":0.48, "price_sensitivity":0.62},
    "Empathetic":   {"openness":0.55, "conscientiousness":0.52, "extraversion":0.52, "agreeableness":0.84, "risk_tolerance":0.38, "novelty_seeking":0.48, "social_orientation":0.80, "health_orientation":0.72, "luxury_orientation":0.42, "planning_orientation":0.48, "cultural_openness":0.70, "environmental_awareness":0.65, "technology_affinity":0.42, "price_sensitivity":0.48},
    "Independent":  {"openness":0.74, "conscientiousness":0.52, "extraversion":0.48, "agreeableness":0.30, "risk_tolerance":0.76, "novelty_seeking":0.68, "social_orientation":0.35, "health_orientation":0.52, "luxury_orientation":0.48, "planning_orientation":0.48, "cultural_openness":0.62, "environmental_awareness":0.52, "technology_affinity":0.78, "price_sensitivity":0.48},
    "Practical":    {"openness":0.42, "conscientiousness":0.76, "extraversion":0.42, "agreeableness":0.52, "risk_tolerance":0.35, "novelty_seeking":0.35, "social_orientation":0.42, "health_orientation":0.62, "luxury_orientation":0.30, "planning_orientation":0.78, "cultural_openness":0.48, "environmental_awareness":0.55, "technology_affinity":0.48, "price_sensitivity":0.80},
    "Ambitious":    {"openness":0.62, "conscientiousness":0.78, "extraversion":0.76, "agreeableness":0.48, "risk_tolerance":0.70, "novelty_seeking":0.62, "social_orientation":0.62, "health_orientation":0.52, "luxury_orientation":0.76, "planning_orientation":0.68, "cultural_openness":0.55, "environmental_awareness":0.48, "technology_affinity":0.74, "price_sensitivity":0.40},
    "Balanced":     {"openness":0.52, "conscientiousness":0.52, "extraversion":0.52, "agreeableness":0.52, "risk_tolerance":0.50, "novelty_seeking":0.52, "social_orientation":0.52, "health_orientation":0.52, "luxury_orientation":0.50, "planning_orientation":0.52, "cultural_openness":0.52, "environmental_awareness":0.52, "technology_affinity":0.52, "price_sensitivity":0.52},
}
ARCHETYPE_WEIGHTS = [10,10,10,10,10,10,10,10,10,8]  # Balanced slightly less to avoid moderate over-representation

# Hoisted immutable structures: building these per profile wastes ~5% of
# generation time with zero behavioral effect. Module constants are read-only,
# so determinism and thread safety are unaffected.
ARCHETYPE_NAMES = list(PERSONALITY_ARCHETYPES)
ARCHETYPE_INDEX = {name: i for i, name in enumerate(ARCHETYPE_NAMES)}
PERSONA_NAMES = list(PERSONAS)
PROFILE_COLUMN_SET = frozenset(PROFILE_COLUMNS)

def _entertainment_latents(rng) -> tuple:
    """Shared latent entertainment factors for the joint persona model.

    Drawn before the personality anchor and consumed by BOTH archetype
    selection and entertainment-persona selection, so movie/series taste
    participates in persona construction through shared latents rather than
    being appended after the fact. Strictly feedforward: nothing downstream
    ever feeds back into these factors or the personality anchor.
    - media_appetite: appetite for intense, novel, diverse media.
    - communal_viewing: orientation toward shared/social viewing.
    """
    return _clip(rng.gauss(0.5, 0.16)), _clip(rng.gauss(0.5, 0.16))

def _generate_traits(rng, age: int, context=None) -> dict:
    """Legacy factor-model fallback (kept for compatibility)."""
    # Base latent factors (standard normal via rng)
    f_open = rng.gauss(0, 1)
    f_consc = rng.gauss(0, 1)
    f_extra = rng.gauss(0, 1)
    f_agree = rng.gauss(0, 1)
    f_stable = rng.gauss(0, 1)
    f_tech = rng.gauss(0, 1)
    f_health = rng.gauss(0, 1)
    f_lux = rng.gauss(0, 1)
    z_risk = rng.gauss(0, 1)
    z_novel = rng.gauss(0, 1)
    z_price = rng.gauss(0, 1)
    z_cult = rng.gauss(0, 1)
    z_env = rng.gauss(0, 1)
    def to_prob(z, sd=0.14):
        return _clip(0.5 + z * sd)
    openness_z = 0.65 * f_open + 0.20 * f_tech + 0.15 * z_novel
    conscientiousness_z = 0.75 * f_consc + 0.25 * f_stable
    extraversion_z = 0.70 * f_extra + 0.20 * f_open + 0.10 * f_agree
    agreeableness_z = 0.70 * f_agree + 0.20 * f_extra + 0.10 * f_health * 0.3
    risk_z = 0.40 * z_risk + 0.25 * f_open - 0.25 * f_consc + 0.10 * f_extra
    novelty_z = 0.50 * f_open + 0.30 * z_novel + 0.20 * f_extra
    social_z = 0.55 * f_extra + 0.30 * f_agree + 0.15 * f_open
    health_z = 0.65 * f_health + 0.20 * f_consc + 0.15 * f_open
    luxury_z = 0.60 * f_lux + 0.20 * f_extra + 0.20 * rng.gauss(0, 0.6)
    planning_z = 0.65 * f_consc + 0.25 * f_stable + 0.10 * rng.gauss(0, 0.7)
    cultural_z = 0.55 * f_open + 0.25 * f_agree + 0.20 * z_cult
    env_z = 0.50 * f_health + 0.25 * f_agree + 0.25 * z_env
    tech_z = 0.60 * f_tech + 0.25 * f_open + 0.15 * rng.gauss(0, 0.7)
    price_z = -0.50 * f_lux + 0.30 * f_consc + 0.20 * z_price
    traits = {
        "openness": to_prob(openness_z),
        "conscientiousness": to_prob(conscientiousness_z),
        "extraversion": to_prob(extraversion_z),
        "agreeableness": to_prob(agreeableness_z),
        "risk_tolerance": to_prob(risk_z),
        "novelty_seeking": to_prob(novelty_z),
        "social_orientation": to_prob(social_z),
        "health_orientation": to_prob(health_z),
        "luxury_orientation": to_prob(luxury_z),
        "planning_orientation": to_prob(planning_z),
        "cultural_openness": to_prob(cultural_z),
        "environmental_awareness": to_prob(env_z),
        "technology_affinity": to_prob(tech_z),
        "price_sensitivity": to_prob(price_z),
    }
    age_factor = (age - 30) / 50.0
    traits["technology_affinity"] = _clip(traits["technology_affinity"] - age_factor * 0.08)
    traits["novelty_seeking"] = _clip(traits["novelty_seeking"] - max(0, age - 45) * 0.003)
    traits["health_orientation"] = _clip(traits["health_orientation"] + max(0, age - 40) * 0.004)
    traits["planning_orientation"] = _clip(traits["planning_orientation"] + max(0, age - 28) * 0.002)
    traits["digital_adoption"] = _clip(0.55 * traits["technology_affinity"] + 0.18 * traits["openness"] + 0.12 * (1 - max(age - 25, 0) / 70) + rng.gauss(0, 0.07))
    if traits["luxury_orientation"] > 0.7 and traits["price_sensitivity"] > 0.6:
        traits["price_sensitivity"] = _clip(traits["price_sensitivity"] - 0.12)
    if traits["luxury_orientation"] < 0.3 and traits["price_sensitivity"] < 0.4:
        traits["price_sensitivity"] = _clip(traits["price_sensitivity"] + 0.10)
    return traits

def _generate_traits_for_archetype(rng, age: int, archetype: str) -> dict:
    """Archetype-anchored generation: samples each trait around archetype target with controlled variation (0-100 internal, then 0-1).
    Preserves age moderation and anti-correlation, but ensures recognizable archetype signature with diversity.
    Uses tighter sd (0.09) to keep archetype distinctive while allowing variation.
    """
    targets = ARCHETYPE_TARGETS.get(archetype, ARCHETYPE_TARGETS["Balanced"])
    traits = {}
    for trait in ("openness","conscientiousness","extraversion","agreeableness","risk_tolerance","novelty_seeking","social_orientation","health_orientation","luxury_orientation","planning_orientation","cultural_openness","environmental_awareness","technology_affinity","price_sensitivity"):
        base = targets[trait]
        # internal 0-100 then 0-1: sample gauss with sd 9 (~0.09) for tighter archetype signature, clipped
        val = rng.gauss(base, 0.09)
        # add small correlated jitter for realism (e.g., conscientiousness ↔ planning)
        if trait == "planning_orientation":
            val = 0.7 * val + 0.3 * traits.get("conscientiousness", base)
        if trait == "cultural_openness" and "openness" in traits:
            val = 0.75 * val + 0.25 * traits["openness"]
        if trait == "social_orientation" and "extraversion" in traits:
            val = 0.7 * val + 0.3 * traits["extraversion"]
        traits[trait] = _clip(val)
    # Age moderation (weak)
    age_factor = (age - 30) / 50.0
    traits["technology_affinity"] = _clip(traits["technology_affinity"] - age_factor * 0.07)
    traits["novelty_seeking"] = _clip(traits["novelty_seeking"] - max(0, age - 45) * 0.003)
    traits["health_orientation"] = _clip(traits["health_orientation"] + max(0, age - 40) * 0.004)
    traits["planning_orientation"] = _clip(traits["planning_orientation"] + max(0, age - 28) * 0.002)
    # Digital adoption derived from traits + age (geo refined later)
    traits["digital_adoption"] = _clip(0.55 * traits["technology_affinity"] + 0.18 * traits["openness"] + 0.12 * (1 - max(age - 25, 0) / 70) + rng.gauss(0, 0.07))
    if traits["luxury_orientation"] > 0.7 and traits["price_sensitivity"] > 0.6:
        traits["price_sensitivity"] = _clip(traits["price_sensitivity"] - 0.12)
    if traits["luxury_orientation"] < 0.3 and traits["price_sensitivity"] < 0.4:
        traits["price_sensitivity"] = _clip(traits["price_sensitivity"] + 0.10)
    return traits

def _refine_digital_adoption(rng, traits: dict, context, age: int):
    base = traits["digital_adoption"]
    # Geo-conditioned refinement: digital_access adds environmentally conditioned boost
    traits["digital_adoption"] = _clip(base * 0.78 + 0.15 * context.digital_access + 0.07 * traits["technology_affinity"] + rng.gauss(0, 0.05))

def _derive_personality_name(traits: dict[str, float]) -> str:
    """Deterministic behavior-derived archetype summary (not random).
    Uses weighted multi-trait scores; geography does not directly influence.
    Scores are 0-1; Balanced is fallback when no archetype dominates.
    Ordering of PERSONALITY_ARCHETYPES defines deterministic tie-break.
    To ensure validation consistency (profile stores traits as 5-level labels),
    we discretize raw trait values to the same label-midpoints validator uses.
    """
    # Discretize to label midpoints for validator consistency
    def _discretize(name: str, val: float) -> float:
        label = _trait_label(name, val)
        mapping = {
            "Very low": 0.12, "Low": 0.30, "Moderate": 0.50, "High": 0.72, "Very high": 0.88,
            "Technology cautious": 0.12, "Technology practical": 0.30, "Technology comfortable": 0.50, "Technology enthusiastic": 0.72, "Technology leading": 0.88,
            "Price insensitive": 0.12, "Slightly price aware": 0.30, "Price conscious": 0.50, "Price sensitive": 0.72, "Highly price sensitive": 0.88,
            "Health disengaged": 0.12, "Health aware": 0.30, "Health balanced": 0.50, "Health focused": 0.72, "Highly health focused": 0.88,
        }
        return mapping.get(label, 0.50)
    t = {k: _discretize(k, v) for k, v in traits.items()}
    # Helper for inverse
    def inv(v): return 1 - v
    scores = {
        "Analytical":  0.34 * t["openness"] + 0.30 * t["conscientiousness"] + 0.20 * t["planning_orientation"] + 0.10 * t["technology_affinity"] + 0.06 * inv(t["risk_tolerance"]),
        "Adventurous": 0.34 * t["novelty_seeking"] + 0.24 * t["openness"] + 0.20 * t["risk_tolerance"] + 0.12 * t["extraversion"] + 0.10 * t["cultural_openness"],
        "Social":       0.30 * t["extraversion"] + 0.28 * t["social_orientation"] + 0.20 * t["agreeableness"] + 0.12 * t["cultural_openness"] + 0.10 * t["novelty_seeking"],
        "Creative":     0.38 * t["openness"] + 0.24 * t["cultural_openness"] + 0.16 * t["novelty_seeking"] + 0.12 * t["extraversion"] + 0.10 * t["environmental_awareness"],
        "Disciplined":  0.34 * t["conscientiousness"] + 0.30 * t["planning_orientation"] + 0.14 * t["health_orientation"] + 0.12 * inv(t["risk_tolerance"]) + 0.10 * t["conscientiousness"] * 0.2,
        "Empathetic":   0.34 * t["agreeableness"] + 0.24 * t["social_orientation"] + 0.16 * t["health_orientation"] + 0.14 * t["cultural_openness"] + 0.12 * t["openness"],
        "Independent":  0.28 * t["openness"] + 0.24 * t["risk_tolerance"] + 0.20 * t["technology_affinity"] + 0.16 * inv(t["agreeableness"]) + 0.12 * t["extraversion"],
        "Practical":    0.30 * t["conscientiousness"] + 0.24 * t["planning_orientation"] + 0.20 * t["price_sensitivity"] + 0.14 * inv(t["luxury_orientation"]) + 0.12 * t["health_orientation"],
        "Ambitious":    0.28 * t["conscientiousness"] + 0.20 * t["extraversion"] + 0.20 * t["luxury_orientation"] + 0.16 * t["technology_affinity"] + 0.16 * t["risk_tolerance"],
    }
    # Balanced score: high when traits cluster near 0.5 (low variance)
    vals = [t[k] for k in ("openness","conscientiousness","extraversion","agreeableness","risk_tolerance","novelty_seeking","social_orientation","health_orientation","luxury_orientation","planning_orientation","cultural_openness","environmental_awareness","technology_affinity","price_sensitivity")]
    mad = sum(abs(v - 0.5) for v in vals) / len(vals)
    balanced_score = _clip(1 - mad * 2.2)  # 1 at 0.5, ~0.56 at 0.2 avg deviation
    # Slight boost to keep Balanced achievable but not dominant (~8-15% population)
    scores["Balanced"] = balanced_score * 0.92
    # Deterministic winner: max score, tie-break by PERSONALITY_ARCHETYPES order
    best = None
    best_score = -1
    for name in PERSONALITY_ARCHETYPES:
        s = scores[name]
        if s > best_score + 1e-9:
            best_score = s
            best = name
    return best

def _domain_base(domain: str, traits: dict[str, float], income_factor: float, age: int, children: int, ses: float, context) -> float:
    # SES and income_factor now intermediate upstream
    mapping = {
        "commerce": .28 * traits["digital_adoption"] + .20 * income_factor + .15 * traits["novelty_seeking"] + .15 * traits["luxury_orientation"] + .12 * ses + .10 * traits["planning_orientation"],
        "technology": .52 * traits["technology_affinity"] + .25 * traits["digital_adoption"] + .10 * traits["openness"] + .08 * ses + .05 * (1 - max(age-50,0)/50),
        "media": .30 * traits["digital_adoption"] + .25 * traits["social_orientation"] + .20 * traits["cultural_openness"] + .15 * traits["novelty_seeking"] + .10 * ses,
        "food": .30 * traits["openness"] + .20 * income_factor + .15 * traits["social_orientation"] + .12 * traits["health_orientation"] + .13 * ses + .10 * traits["cultural_openness"],
        "travel": .28 * income_factor + .25 * traits["novelty_seeking"] + .18 * traits["cultural_openness"] + .12 * traits["risk_tolerance"] + .10 * ses + .07 * (1 - children/4),
        "fashion": .28 * traits["luxury_orientation"] + .22 * income_factor + .20 * traits["social_orientation"] + .12 * traits["openness"] + .10 * ses + .08 * traits["cultural_openness"],
        "mobility": .30 * income_factor + .18 * traits["environmental_awareness"] + .15 * traits["technology_affinity"] + .12 * ses + .10 * (1 - children/4) + .08 * context.digital_access + .07 * (1 if context.urban_rural=="Urban" else 0),
        "wellness": .50 * traits["health_orientation"] + .18 * traits["planning_orientation"] + .12 * traits["conscientiousness"] + .10 * ses + .10 * traits["openness"],
        "home": .32 * income_factor + .20 * traits["planning_orientation"] + .15 * traits["environmental_awareness"] + .13 * ses + .10 * min(children/2, 1) + .10 * context.cost_factor * 0.2,
        "hobbies": .28 * traits["openness"] + .25 * traits["social_orientation"] + .18 * traits["novelty_seeking"] + .12 * traits["health_orientation"] + .10 * ses + .07 * traits["cultural_openness"],
        "finance": .28 * income_factor + .25 * traits["planning_orientation"] + .18 * traits["conscientiousness"] + .15 * traits["digital_adoption"] + .14 * ses,
    }
    # age tilt: older slightly lower for tech/commerce/media, higher for wellness/home
    age_tilt = 0
    if domain in {"technology","commerce","media"}:
        age_tilt = -max(0, age - 58) * 0.004
    elif domain in {"wellness","home"}:
        age_tilt = min(0.06, max(0, age - 40) * 0.002)
    return _clip(mapping[domain] + age_tilt)

def _education_for_stage(rng, stage: str, age: int, traits: dict, context) -> tuple[str, int, str]:
    if stage == "Teenager":
        return "School education", 10, "In progress"
    if stage == "University Student":
        # 18-22: mix of school vs undergrad, postgrad rare
        edu = choose(rng, ["School education", "Undergraduate", "Professional diploma"], [22, 62, 16])
        years = {"School education": 10, "Undergraduate": 13, "Professional diploma": 12}[edu]
        grad = "In progress" if rng.random() < 0.78 else "Completed"
        return edu, years, grad
    if stage == "Retired":
        # older cohort slightly lower postgrad rates, include all
        edu = choose(rng, ["School education", "Undergraduate", "Postgraduate", "Professional diploma"], [28, 38, 20, 14])
        years = {"School education": 10, "Undergraduate": 15, "Postgraduate": 17, "Professional diploma": 13}[edu]
        return edu, years, "Completed"
    # Working ages: probability conditioned on traits/SES proxy (conscientiousness/openness) and age cohort
    # Base weights evolve with age: younger higher undergrad share
    if age < 30:
        base_weights = [14, 52, 18, 16]
    elif age < 40:
        base_weights = [12, 44, 26, 18]
    elif age < 52:
        base_weights = [13, 42, 28, 17]
    else:
        base_weights = [18, 40, 26, 16]
    # Adjust by conscientiousness/openness: higher conscientiousness+openness nudges postgraduate
    adj = (traits["conscientiousness"] + traits["openness"]) / 2
    if adj > 0.65:
        base_weights[2] += 8  # postgraduate up
        base_weights[0] -= 4
    elif adj < 0.35:
        base_weights[0] += 6
        base_weights[2] -= 4
    # normalize positive
    base_weights = [max(2, w) for w in base_weights]
    edu = choose(rng, ["School education", "Undergraduate", "Postgraduate", "Professional diploma"], base_weights)
    years = {"School education": 10, "Undergraduate": 15, "Postgraduate": 17, "Professional diploma": 13}[edu]
    return edu, years, "Completed"

def _field_of_study(rng, education: str, traits: dict) -> str:
    if education == "School education":
        # For school level, map to generic streams but keep original vocabulary limited
        return choose(rng, FIELD_OPTIONS, [12, 18, 22, 18, 18, 12])
    # Personality-conditioned weights
    # High tech -> Engineering, high openness -> Arts/Science, high conscientiousness -> Healthcare/Business etc.
    weights = {
        "Engineering": 10 + traits["technology_affinity"] * 22 + traits["openness"] * 6,
        "Business": 10 + traits["extraversion"] * 10 + traits["planning_orientation"] * 10 + (1 - traits["openness"]) * 5,
        "Arts and humanities": 8 + traits["openness"] * 18 + traits["cultural_openness"] * 12,
        "Science": 10 + traits["openness"] * 14 + traits["conscientiousness"] * 8,
        "Commerce": 10 + traits["planning_orientation"] * 10 + traits["conscientiousness"] * 6,
        "Healthcare": 8 + traits["health_orientation"] * 18 + traits["agreeableness"] * 8,
    }
    options = list(weights)
    w = [weights[o] for o in options]
    return choose(rng, options, w)

def _industry_for_field(rng, field: str, context) -> str:
    field_weights = INDUSTRY_FIELD_WEIGHTS.get(field, {})
    # Intersect with context industries: weight context industries by field relevance + fallback uniform
    candidates = list(context.industries)
    weights = []
    for ind in candidates:
        base = field_weights.get(ind, 1.0)
        # small random jitter for probabilistic not deterministic
        jitter = rng.uniform(0.85, 1.15)
        weights.append(base * jitter)
    return choose(rng, candidates, weights)

def _family_generation(rng, age: int, stage: str, context, traits: dict, ses: float):
    # Marital status conditional on age (probabilistic distributions, not stereotyped)
    if age < 18:
        marital = "Single"
    elif age < 21:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [78, 18, 3, 1])
    elif age < 25:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [52, 27, 18, 3])
    elif age < 30:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [32, 22, 41, 5])
    elif age < 40:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [16, 12, 63, 9])
    elif age < 50:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [11, 8, 66, 15])
    elif age < 64:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [9, 5, 63, 23])
    else:
        marital = choose(rng, ["Single", "In a relationship", "Married", "Separated/Widowed"], [7, 3, 58, 32])
    # Slight cultural openness mod: higher openness slightly delays marriage, but keep weak
    # Not geografy stereotype; keep universal
    children = 0
    if age < 20 or marital in {"Single", "In a relationship"}:
        # Small probability of children even if single (non-marital) for realism, age dependent
        if marital in {"Single","In a relationship"} and age >= 22 and rng.random() < 0.07 + traits["social_orientation"]*0.04:
            children = choose(rng, [1,2], [80,20])
        else:
            children = 0
    else:
        # Married / Separated/Widowed with children probability age conditioned
        if age < 22:
            children = choose(rng, [0,1,2], [68, 26, 6])
        elif age < 30:
            children = choose(rng, [0,1,2,3], [34, 42, 20, 4])
        elif age < 40:
            children = choose(rng, [0,1,2,3], [18, 28, 40, 14])
        elif age < 50:
            children = choose(rng, [0,1,2,3], [14, 22, 42, 22])
        else:
            children = choose(rng, [0,1,2,3], [18, 26, 38, 18])
            # older may have adult children not counted? keep as is for household
    # Siblings independent demographic
    siblings = choose(rng, [0,1,2,3], [18,48,26,8])
    # Parents in household conditioned on age, marital, ses, urban
    parents_prob = 0.0
    if age < 24: parents_prob = 0.68
    elif age < 30: parents_prob = 0.42 if marital == "Single" else 0.18
    elif age < 35: parents_prob = 0.22 if marital == "Single" else 0.09
    else: parents_prob = 0.07
    # Lower SES slightly higher co-residence
    if ses < 0.35: parents_prob += 0.08
    parents_in_house = rng.random() < parents_prob
    # Household size: base 1 + spouse + children + parents + extra flatmate if young urban single
    hsize = 1
    if marital == "Married": hsize += 1
    hsize += children
    if parents_in_house: hsize += 1 if rng.random() < 0.78 else 2  # usually one parent
    if age < 30 and marital == "Single" and not parents_in_house and rng.random() < 0.32:
        hsize += 1  # flatmate
    hsize = max(1, hsize)
    # Family type
    if marital == "Married" and children>0: family_type = "Nuclear" if hsize<=4 else "Joint/Extended"
    elif marital == "Married": family_type = "Couple"
    elif children>0: family_type = "Single parent"
    elif parents_in_house: family_type = "With parents"
    elif hsize==1: family_type = "Single-person"
    else: family_type = "Shared/Flatmates"
    # Living arrangement conditioned on age+ses+household
    if age < 23: living = "Family home"
    elif age > 38 and ses > 0.42 and hsize>1: living = choose(rng, ["Owned home","Rented home"], [62,38])
    elif age > 32 and ses > 0.35: living = choose(rng, ["Owned home","Rented home","Family home"], [38,48,14])
    elif age > 27: living = choose(rng, ["Rented home","Family home","Shared housing"], [58,18,24])
    else: living = choose(rng, ["Rented home","Family home","Shared housing"], [42,32,26])
    dependents = children + (1 if age>48 and rng.random()<0.18 else 0)
    return marital, children, dependents, hsize, family_type, living, parents_in_house, siblings

def _career_chain(rng, age: int, stage: str, education: str, field: str, traits: dict, context, ses_hint: float):
    if stage == "Teenager":
        return "School student", "Education", "None", 0, "School", "Not applicable", 0, "Not applicable", "Not applicable", "Low"
    if stage == "University Student":
        # Student employment: part-time or student status, field relevant industry as internship context
        emp = choose(rng, ["Student", "Employed part-time"], [78,22])
        industry = _industry_for_field(rng, field, context) if rng.random()<0.7 else choose(rng, list(context.industries))
        career = "None"
        exp = 0 if emp=="Student" else rng.randint(0,1)
        employer = "University/Internship" if emp=="Student" else choose(rng, ["Startup","Mid-size company","Part-time employer"], [35,30,35])
        work_mode = "Hybrid" if traits["digital_adoption"]>0.58 else "On-site"
        hours = 0 if emp=="Student" else rng.randint(12,28)
        leadership = "Not applicable"
        job_stability = _category(0.35 + traits["conscientiousness"]*0.25)
        growth = _category((traits["novelty_seeking"]+traits["planning_orientation"])/2)
        return emp, industry, career, exp, employer, work_mode, hours, leadership, job_stability, growth
    if stage == "Retired":
        industry = _industry_for_field(rng, field, context)
        career = "Former professional"
        exp = max(0, age - (22 if education in {"Undergraduate","Postgraduate"} else 18) - rng.randint(0,5))
        employer = "Retired"
        work_mode = "Not applicable"
        hours = 0
        leadership = "Not applicable"
        job_stability = "High"
        growth = "Low"
        return industry, industry, career, exp, employer, work_mode, hours, leadership, job_stability, growth
    # Working adults
    # Employment status conditioned on SES, children, gender placeholder not used, industry
    # Keep within legacy values but allow variation
    if rng.random() < 0.04:  # small unemployed/homemaker gap -> map to part-time/self
        employment = choose(rng, ["Employed part-time","Self-employed"], [60,40])
    else:
        employment = choose(rng, ["Employed full-time","Self-employed","Employed part-time"], [74,16,10])
    industry = _industry_for_field(rng, field, context)
    # Experience: age - graduation age - gap, correlated with career interruptions (children)
    grad_age = 22 if education in {"Undergraduate","Postgraduate"} else 18 if education=="School education" else 19
    max_exp = max(0, age - grad_age)
    gap = rng.randint(0,2)
    # career gap for parents
    if rng.random() < 0.12:
        gap += 1
    experience = max(0, max_exp - gap)
    # Career level conditional on experience + education + conscientiousness/planning
    merit = (traits["conscientiousness"]+traits["planning_orientation"])/2
    if experience < 2: career = "Early"
    elif experience < 5:
        career = choose(rng, ["Early","Mid-level"], [68 - merit*20, 32 + merit*20])
    elif experience < 10:
        career = choose(rng, ["Early","Mid-level","Senior"], [18, 58 - merit*10, 24 + merit*10])
    elif experience < 16:
        career = choose(rng, ["Mid-level","Senior","Leadership"], [32, 52, 16 + merit*12])
    else:
        # 16+ years
        edu_boost = 8 if education=="Postgraduate" else 0
        career = choose(rng, ["Mid-level","Senior","Leadership"], [18, 48, 34 + edu_boost])
    # Employer type
    if career in {"Senior","Leadership"}:
        employer = choose(rng, ["Large enterprise","Public sector","Mid-size company"], [42,28,30])
    else:
        employer = choose(rng, ["Startup","Mid-size company","Large enterprise","Public sector"], [28,32,24,16])
    # Work mode
    if industry in {"Technology","Consulting","Media","Finance"} and traits["digital_adoption"]>0.58:
        work_mode = choose(rng, ["Remote/hybrid","On-site","Hybrid"], [42,28,30])
    elif traits["digital_adoption"]>0.68:
        work_mode = choose(rng, ["Remote/hybrid","On-site"], [32,68])
    else:
        work_mode = "On-site"
    hours = rng.randint(38,54) if employment=="Employed full-time" else rng.randint(22,48) if employment=="Employed part-time" else rng.randint(35,58)
    leadership = "People manager" if career=="Leadership" else "Team lead" if career=="Senior" and rng.random()<0.28 else "Individual contributor"
    # job stability categorical
    stab_score = min(experience,15)/15*0.5 + traits["conscientiousness"]*0.35 + (0.15 if employment=="Employed full-time" else 0)
    job_stability = _category(stab_score)
    growth = _category((traits["novelty_seeking"]+traits["planning_orientation"]+ (0.2 if age<40 else 0))/2.2)
    # For retired early returns shape mismatch, handle above
    # Normal return
    return employment, industry, career, experience, employer, work_mode, hours, leadership, job_stability, growth

def _housekeeping_career(rng, age, stage, education, field, traits, context):
    # Wrapper to normalize return length
    res = _career_chain(rng, age, stage, education, field, traits, context, 0)
    if stage in {"Teenager","University Student"}:
        # unpack special
        employment, industry, career, exp, employer, work_mode, hours, leadership, job_stab, growth = res[0], res[1], res[2], res[3], res[4], res[5], res[6], res[7], res[8], res[9]
        return employment, industry, career, exp, employer, work_mode, hours, leadership, job_stab, growth
    if stage == "Retired":
        # _career_chain for retired returned 9 values (industry duplicated) need map
        # Actually returns industry, industry, career, exp, employer, work_mode, hours, leadership, job_stability, growth ? check
        # For retired we returned 10 values with duplicate industry
        employment = "Retired"
        industry = res[0] if isinstance(res[0], str) else res[1]
        # Simpler: recompute
        industry = _industry_for_field(rng, field, context)
        career = "Former professional"
        exp = max(0, age - (22 if education in {"Undergraduate","Postgraduate"} else 18) - rng.randint(0,5))
        employer = "Retired"
        work_mode = "Not applicable"
        hours = 0
        leadership = "Not applicable"
        job_stab = "High"
        growth = "Low"
        return employment, industry, career, exp, employer, work_mode, hours, leadership, job_stab, growth
    # adult
    employment, industry, career, exp, employer, work_mode, hours, leadership, job_stab, growth = res
    return employment, industry, career, exp, employer, work_mode, hours, leadership, job_stab, growth

def _income_model(rng, context, education: str, field: str, industry: str, career: str, experience: int, employment: str, traits: dict, ses: float, age: int):
    if employment in {"School student","Student","Retired"}:
        if employment == "Retired":
            base_ret = {"School education": 260000, "Undergraduate": 480000, "Postgraduate": 720000, "Professional diploma": 380000}[education]
            income = int(max(context.income_scale * 0.14, base_ret * (context.income_scale/900000) * rng.uniform(0.75,1.15) * (0.9 + ses*0.3)))
            return income
        return 0
    # base median per career
    career_base = {"None": 0, "Early": 420000, "Mid-level": 800000, "Senior": 1350000, "Leadership": 2300000, "Former professional": 600000}.get(career, 500000)
    edu_premium = {"School education":0.78, "Professional diploma":0.92, "Undergraduate":1.0, "Postgraduate":1.32}[education]
    field_premium = {"Engineering":1.18, "Business":1.14, "Healthcare":1.24, "Science":1.05, "Commerce":1.0, "Arts and humanities":0.86}[field]
    # industry premium varies by context: adapt via digital/access but keep generic multipliers
    industry_premium_map = {"Technology":1.28, "Finance":1.26, "Energy":1.34, "Oil and gas":1.30, "Healthcare":1.22, "Manufacturing":1.05, "Automotive":1.12, "Government":1.02, "Consulting":1.18, "Media":1.03, "Retail":1.0, "Education":0.98, "Agriculture":0.92, "Services":1.04, "Trade":1.01, "Creative services":1.06, "Construction":1.08}
    ind_prem = industry_premium_map.get(industry, 1.05)
    exp_factor = 1 + min(experience, 25) / 100 * 0.95  # up to ~1.24
    emp_factor = {"Employed full-time":1.0, "Self-employed":0.96, "Employed part-time":0.52}.get(employment, 1.0)
    ambition_factor = 0.88 + traits["conscientiousness"]*0.10 + traits["luxury_orientation"]*0.10 + traits["planning_orientation"]*0.07
    # Lognormal-like noise
    noise = rng.lognormvariate(0, 0.28) if hasattr(rng, 'lognormvariate') else rng.gauss(1.0, 0.28)
    # Guard lognorm deviate extreme
    noise = max(0.55, min(1.85, noise))
    # Context scaling
    context_scale = context.income_scale / 900000
    # SES influence weak
    ses_factor = 0.92 + ses * 0.18
    raw = career_base * edu_premium * field_premium * ind_prem * exp_factor * emp_factor * ambition_factor * context_scale * ses_factor * noise
    # Cost adjustment: higher cost markets have nominally higher income but we keep scale already reflects
    floor = context.income_scale * 0.11
    income = int(max(floor, raw))
    # Cap unrealistic extremes
    cap = context.income_scale * 6.5
    income = int(min(income, cap))
    return income

def _conditional_food_pattern(rng, context, income_factor: float, health_orientation: float, age: int, household_size: int):
    # Weighted by geography foods but with health/income tilts (probabilistic)
    foods = list(context.foods)
    weights = []
    for f in foods:
        w = 1.0
        # health orientation boosts healthy/plant-forward/vegetarian patterns
        if f in {"Vegetarian","Plant-forward","Healthy_food","Seafood","Regional cuisine"} and health_orientation > 0.60:
            w *= 1.35
        if f in {"Street food","Fast food","Barbecue"} and health_orientation > 0.65:
            w *= 0.72
        if f in {"Global cuisine","Premium_dining","Western","Global cuisine"} and income_factor > 0.55:
            w *= 1.25
        if f in {"Street food","Regional Indian","Nigerian","Brazilian"} and income_factor < 0.30:
            w *= 1.18
        # household size: larger families favor shared/traditional
        if household_size > 3 and f in {"Regional Indian","Nigerian","Brazilian","Arabian","Japanese"}:
            w *= 1.12
        weights.append(w * rng.uniform(0.9,1.1))
    return choose(rng, foods, weights)

def _conditional_transport(rng, context, income_factor: float, traits: dict, age: int, urban_rural: str, employment: str):
    opts = list(context.transport)
    weights = []
    for t in opts:
        w = 1.0
        # Income higher -> car
        if t == "Car" and income_factor > 0.50: w *= 1.6
        if t == "Car" and income_factor < 0.25: w *= 0.45
        if t in {"Bus","Public transit","Metro","Rail","Walking"} and income_factor < 0.32: w *= 1.35
        if t in {"Two-wheeler","Motorcycle taxi"} and age < 42 and income_factor < 0.55: w *= 1.25
        if t in {"Ride-hailing","Metro"} and context.digital_access > 0.78: w *= 1.18
        if t in {"Walking","Cycling","Public transit"} and traits["environmental_awareness"] > 0.62: w *= 1.30
        if t in {"Car","Domestic flight"} and traits["environmental_awareness"] > 0.72: w *= 0.78
        if urban_rural == "Rural" and t in {"Metro","Public transit"}: w *= 0.55
        if urban_rural == "Urban" and t in {"Metro","Public transit","Ride-hailing"}: w *= 1.22
        if employment in {"Student","School student"} and t in {"Two-wheeler","Bus","Metro","Walking"}: w *= 1.15
        weights.append(w * rng.uniform(0.88,1.12))
    return choose(rng, opts, weights)

def _conditional_payment(rng, context, income_factor: float, digital_adoption: float, age: int):
    opts = list(context.payments)
    weights = []
    for p in opts:
        w = 1.0
        # digital adoption boosts digital methods
        if p in {"UPI","PIX","Digital wallet","Mobile payment","Mobile money"} and digital_adoption > 0.60: w *= 1.55
        if p in {"UPI","PIX","Mobile money"} and digital_adoption < 0.35: w *= 0.50
        if p == "Cash" and digital_adoption > 0.70: w *= 0.58
        if p == "Cash" and digital_adoption < 0.35: w *= 1.45
        if p == "Cash" and age > 58: w *= 1.25
        if p in {"Card","Bank transfer"} and income_factor > 0.50: w *= 1.22
        if p in {"Card"} and age < 30 and digital_adoption > 0.60: w *= 0.88  # younger prefer wallet/UPI
        # context-specific boosts still probabilistic
        if context.country == "India" and p == "UPI" and digital_adoption>0.45: w*=1.30
        if context.country == "Brazil" and p == "PIX" and digital_adoption>0.45: w*=1.30
        if context.country == "Nigeria" and p == "Mobile money" and digital_adoption<0.60: w*=1.20
        if context.country == "United States" and p == "Card": w*=1.15
        weights.append(w * rng.uniform(0.90,1.10))
    return choose(rng, opts, weights)

def _conditional_platform(rng, context, language: str, traits: dict):
    # Behavior-first weighting for platform affinity, geography defines availability
    # All platforms available in context are plausible; weight by language familiarity + digital/tech
    opts = list(context.platforms)
    weights = []
    for plat in opts:
        w = 1.0
        # Language-specific affinity (not hardcode country→preference, but language ecosystem)
        if language in {"Hindi","Telugu","Tamil","Bengali"} and plat in {"JioHotstar","ZEE5","Aha","Sun NXT"}: w*=1.35
        if language == "Japanese" and plat in {"U-NEXT"}: w*=1.40
        if language == "Portuguese" and plat in {"Globoplay"}: w*=1.40
        if language == "Arabic" and plat in {"Shahid"}: w*=1.40
        # Tech affinity slightly prefers global tech platforms
        if plat in {"Netflix","YouTube","Amazon Prime Video"} and traits["technology_affinity"]>0.60: w*=1.12
        if plat in {"BBC iPlayer"} and traits["cultural_openness"]>0.60: w*=1.10
        weights.append(w * rng.uniform(0.88,1.12))
    return choose(rng, opts, weights)

def generate_profile(seed: int, index: int, country: str | None = None, age_range=None, preferred_language=None, persona=None, country_mode=None, region=None, continent=None, countries=None) -> dict:
    if preferred_language and preferred_language not in LANGUAGES: raise ValueError("Unsupported preferred_language")
    if persona and persona not in PERSONAS: raise ValueError("Unsupported persona")
    rng = profile_rng(seed, index)
    age = _age(rng, age_range); stage = _stage(age)
    # Shared latent persona factors (joint model): these shape both the
    # personality anchor below and entertainment/media choice later.
    # Drawn before geography so they never depend on country.
    media_appetite, communal_viewing = _entertainment_latents(rng)
    # Step 1: Personality Archetype → Core Traits (anchor, not derived after random)
    # Archetype selection is jointly conditioned on the entertainment latents
    # (mild tilt only; the anchor still dominates trait generation).
    _arch_weights = list(ARCHETYPE_WEIGHTS)
    _arch_weights[ARCHETYPE_INDEX["Creative"]] *= 0.60 + 1.10 * media_appetite
    _arch_weights[ARCHETYPE_INDEX["Adventurous"]] *= 0.60 + 1.10 * media_appetite
    _arch_weights[ARCHETYPE_INDEX["Social"]] *= 0.60 + 1.10 * communal_viewing
    _arch_weights[ARCHETYPE_INDEX["Empathetic"]] *= 0.82 + 0.55 * communal_viewing
    archetype = choose(rng, ARCHETYPE_NAMES, _arch_weights)
    traits = _generate_traits_for_archetype(rng, age, archetype)
    # Keep legacy factor diversity as small blended noise for realism (optional)
    # Validate archetype signature remains recognizable but with variation

    # Direct library callers may omit geography; that means global, while an
    # explicitly supplied country remains a specific-country request.
    if country_mode is None:
        country_mode = "specific" if country else "global"
    context = get_context(rng, country_mode, country, region, continent, countries)
    _refine_digital_adoption(rng, traits, context, age)
    # Personality name is the anchor archetype (ensures archetype → traits → behavior)
    personality_name = archetype
    # Optional consistency check: derived should match anchor most of the time; if not, keep anchor (anchor is truth)
    # We do not overwrite anchor with derived to preserve archetype → traits direction
    # Step 2: Language (geography-conditioned with migration probability, never deterministic)
    language = preferred_language or choose_language(rng, list(context.languages), context.state, context.city)
    # Step 3: Education chain (age → education → field)
    education, years_of_education, graduation_status = _education_for_stage(rng, stage, age, traits, context)
    field_of_study = _field_of_study(rng, education, traits)
    institution_type = choose(rng, ["Public", "Private", "Professional institute"], [42,38,20]) if education != "School education" else choose(rng, ["Public","Private"], [62,38])
    # Adjust institution by SES proxy (income_factor not yet known, use traits as proxy)
    # academic orientation / quality later

    # Step 4: Family/Household (age/life stage + SES proxy) - SES preliminary via education
    prelim_ses = _clip(EDUCATION_EDU_SCORE[education]*0.55 + traits["planning_orientation"]*0.15 + traits["conscientiousness"]*0.15 + rng.uniform(-0.07,0.07))
    marital, children, dependents, household_size, family_type, living_arrangement, parents_in_house, siblings = _family_generation(rng, age, stage, context, traits, prelim_ses)

    # Step 5: Career chain (education→field→industry→career→experience)
    employment, industry, career, experience, employer_type, work_mode, weekly_hours, leadership_status, job_stability, growth_orientation = _housekeeping_career(rng, age, stage, education, field_of_study, traits, context)

    # Step 6: Socioeconomic state (intermediate driver)
    edu_score = EDUCATION_EDU_SCORE[education]
    career_score = CAREER_SCORE.get(career, 0.3)
    exp_score = _clip(min(experience, 20) / 20)
    # income_factor not yet known; use proxy SES then update after income
    ses = _clip(0.32 * edu_score + 0.22 * career_score + 0.15 * exp_score + 0.12 * traits["conscientiousness"] + 0.10 * prelim_ses + 0.09 * (context.digital_access))
    # Allow slight geographic cost adjustment
    ses = _clip(ses + (context.cost_factor - 0.7) * 0.04 + rng.gauss(0, 0.05))
    # Fix employer_type levels etc for retired/student handled

    # Step 7: Income (education+field+industry+experience+career+employment+SES+geography)
    annual_income = _income_model(rng, context, education, field_of_study, industry, career, experience, employment, traits, ses, age)
    monthly_income = annual_income // 12 if annual_income else 0
    household_income = annual_income + (int(annual_income * rng.uniform(.22, .88)) if marital == "Married" and employment not in {"School student","Student"} else 0)
    # Update income_factor and SES with realized income
    income_factor = _clip(annual_income / (context.income_scale * 2.8) if context.income_scale else 0)
    # Refine SES with income_factor
    ses = _clip(0.45 * ses + 0.45 * income_factor + 0.10 * edu_score)
    # Re-derive some SES-dependent categorical fields after income known
    # Housing adjustment already done via living_arrangement but keep consistent
    # Recalculate living if mismatch with income_factor extreme
    if monthly_income > 0:
        # Ensure owned vs rented aligns loosely with SES/income_factor
        pass

    # Finance (support-aware: zero personal income does not imply zero spending)
    financial_support = financial_support_for(rng, employment, monthly_income)
    # expense_ratio conditional on children, luxury, planning, household, ses
    expense_ratio = _clip(0.36 + children * 0.055 + traits["luxury_orientation"]*0.16 - traits["planning_orientation"]*0.13 + (0.05 if household_size>4 else 0) - ses*0.04 + rng.gauss(0,0.04))
    expense_ratio = max(0.28, min(0.92, expense_ratio))
    if monthly_income:
        expenses = int(monthly_income * expense_ratio)
        savings = monthly_income - expenses
        # ensure savings non-negative (allow small negative jitter then clip)
        if savings < 0: savings = 0; expenses = monthly_income
    elif financial_support in ("Family support", "Scholarship/stipend", "Self-funded", "Pension/savings"):
        # Supported with no personal income: probabilistic non-zero spending, no savings.
        expenses = supported_student_expenses(rng, context.income_scale) if rng.random() < 0.72 else 0
        savings = 0
    else:
        expenses = 0
        savings = 0

    # Life stage reconciliation: age anchor adjusted by realised career state.
    life_stage = resolve_life_stage(rng, age, experience, career, employment, stage)

    # Persona - behavior first (traits/culture/age) then geography platform mapping
    # Weight personas by traits + shared entertainment latents, not country.
    # The same latents that tilted the personality anchor also tilt media
    # choice, which is what makes taste participate in the persona jointly.
    persona_weights = []
    for name in PERSONAS:
        w = 1.0
        if name == "Sci-Fi Enthusiast": w += 1.8 * traits["technology_affinity"] + 0.9 * traits["openness"] + 1.4 * media_appetite
        if name == "International Cinema Explorer": w += 1.8 * traits["cultural_openness"] + 0.7 * traits["openness"] + 1.4 * media_appetite
        if name == "Family Entertainment Viewer": w += 0.9 * children + 0.4 * traits["agreeableness"] + 1.4 * communal_viewing + 0.5 * traits["extraversion"]
        if name == "Action Enthusiast": w += 0.8 * traits["risk_tolerance"] + 0.5 * traits["extraversion"] + 0.5 * media_appetite if age<40 else 0
        if name == "Documentary Viewer": w += 0.9 * traits["openness"] + 0.6 * traits["conscientiousness"] + 0.5 * media_appetite if age>32 else 0
        if name == "Animation / Anime Fan": w += 0.8 * traits["openness"] + 0.5 * media_appetite if age < 36 else -0.4
        if name == "Classic Cinema Lover": w += 0.7 * traits["cultural_openness"] if age>48 else 0
        if name == "Horror Fan": w += 0.7 * traits["risk_tolerance"] + 0.5 * media_appetite if age<38 else -0.3
        persona_weights.append(max(0.2, w))
    persona_value = persona or choose(rng, PERSONA_NAMES, persona_weights)
    if employment in {"School student", "Student", "Retired"}:
        job_function = "Not applicable"
        occupation = employment
    else:
        job_function = job_function_for_industry(rng, industry, field_of_study, career)
        occupation = occupation_title(career, industry, job_function, employment)
    professional_training = professional_training_for(rng, education, industry, career, experience) if employment not in {"School student", "Student"} else ("In progress" if employment == "Student" else "Not applicable")
    degree_years = {"School education": 10, "Undergraduate": 15, "Postgraduate": 17, "Professional diploma": 13}[education] if education in {"School education","Undergraduate","Postgraduate","Professional diploma"} else years_of_education
    # Conditional geography behavior (not deterministic)
    local_food_pattern = _conditional_food_pattern(rng, context, income_factor, traits["health_orientation"], age, household_size)
    primary_transport_mode = _conditional_transport(rng, context, income_factor, traits, age, context.urban_rural, employment)
    available_payment_method = _conditional_payment(rng, context, income_factor, traits["digital_adoption"], age)
    preferred_ott_platform = _conditional_platform(rng, context, language, traits)

    profile = {
        "personality_name": personality_name, "profile_id": f"{context.country_code}-{seed:08x}-{index:05d}", "profile_schema_version": PROFILE_SCHEMA_VERSION, "age": age, "age_band": next(f"{a}-{b}" for a,b,_ in AGE_BANDS if a <= age <= b), "date_of_birth": str(date(2026, 8, 20) - timedelta(days=age * 365 + rng.randint(0, 364))), "gender": choose(rng, ["Female", "Male", "Non-binary"], [48, 48, 4]), "country": context.country, "country_code": context.country_code, "state": context.state, "city": context.city, "region": context.region, "urban_rural": context.urban_rural, "nationality": context.nationality, "primary_language": language, "preferred_language": language if traits["cultural_openness"] < .65 else choose_language(rng, list(context.languages), context.state, context.city), "population_segment": "Working professional" if employment.startswith("Employed") else life_stage, "life_stage": life_stage,
        "marital_status": marital, "relationship_status": "Married" if marital == "Married" else marital, "number_of_children": children, "dependents_count": dependents, "household_size": household_size, "family_type": family_type, "living_arrangement": living_arrangement, "parents_in_household": parents_in_house, "siblings_count": siblings,
        "education_level": education, "highest_degree": education, "field_of_study": field_of_study, "institution_type": institution_type, "graduation_status": graduation_status, "years_of_education": degree_years, "academic_orientation": _category((traits["openness"] + traits["conscientiousness"]) / 2), "education_quality": _category(.35 + income_factor * .28 + traits["conscientiousness"] * .22 + edu_score*0.15),
        "employment_status": employment, "occupation": occupation, "industry": industry, "job_function": job_function, "professional_training": professional_training, "career_level": career, "years_of_experience": experience, "employer_type": employer_type, "work_mode": work_mode, "weekly_work_hours": weekly_hours, "leadership_status": leadership_status, "job_stability": job_stability, "career_growth_orientation": growth_orientation,
        "annual_income": annual_income, "monthly_income": monthly_income, "income_band": "Limited" if annual_income < 300000 and context.currency=="INR" else ("Limited" if annual_income < context.income_scale*0.45 else "Modest" if annual_income < context.income_scale*0.85 else "Comfortable" if annual_income < context.income_scale*1.6 else "Affluent"), "household_income": household_income, "financial_support_source": financial_support, "monthly_expenses": expenses, "monthly_savings": savings, "savings_rate": round(savings / monthly_income, 3) if monthly_income else 0, "financial_stability": _category((traits["planning_orientation"] + min(savings / max(monthly_income,1) * 2, 1)) / 2), "spending_power": _category(_clip(0.55*income_factor+0.45*ses)), "price_sensitivity": traits["price_sensitivity"], "financial_risk_tolerance": _category(traits["risk_tolerance"]), "investment_interest": _category(_clip(0.42*income_factor + 0.38*traits["risk_tolerance"] + 0.20*ses)), "credit_behavior": _category((income_factor + traits["conscientiousness"]) / 2),
        "shopping_frequency": _category(_clip(0.42*income_factor + 0.32*traits["digital_adoption"] + 0.16*ses + 0.10*traits["social_orientation"])), "online_shopping_frequency": _category(_clip(0.65*traits["digital_adoption"]+0.20*income_factor+0.15*ses)), "offline_shopping_frequency": _category(traits["social_orientation"] *0.7 + (0.3 if context.shopping_ecosystems else 0)), "preferred_marketplace": "Value marketplace" if traits["price_sensitivity"] > .58 else "Brand marketplace" if traits["luxury_orientation"]>0.58 else choose(rng, ["Value marketplace","Brand marketplace","Balanced marketplace"], [32,28,40]), "preferred_category": "Home and family" if children else "Electronics" if traits["technology_affinity"] > .62 else "Fashion" if traits["luxury_orientation"]>0.56 else choose(rng, ["Home and family","Electronics","Fashion","Groceries"], [22,28,24,26]), "average_order_value": int(520 + income_factor * 5200 + traits["luxury_orientation"] * 2400 + ses*1200 + rng.randint(-280,420)), "discount_sensitivity": _category(traits["price_sensitivity"]), "brand_loyalty": _category(_clip(0.45*traits["conscientiousness"] + 0.25*(1-traits["price_sensitivity"]) + 0.20*income_factor +0.10*ses)), "impulse_buying": _category(1 - traits["planning_orientation"]*0.75 - traits["conscientiousness"]*0.15 + traits["risk_tolerance"]*0.10), "research_before_purchase": _category((traits["openness"] + traits["planning_orientation"]) / 2), "premium_preference": _category(_clip(0.42*income_factor + 0.36*traits["luxury_orientation"] +0.22*ses)), "cart_abandonment_tendency": _category(_clip(0.55*traits["price_sensitivity"]+0.25*(1-traits["planning_orientation"])+0.20*(1-income_factor))),
        "technology_affinity": traits["technology_affinity"], "digital_adoption": traits["digital_adoption"], "daily_screen_time_hours": round(max(0.8, 1.2 + traits["digital_adoption"] * 6.2 - max(age-50,0)*.038 + (0.6 if employment in {"Student","School student"} else 0) + rng.gauss(0,0.45)), 1), "device_preference": "Smartphone-first" if traits["technology_affinity"] < .60 else "Multi-device", "ai_interest": _category((traits["technology_affinity"] + traits["openness"]) / 2), "social_media_activity": _category((traits["social_orientation"] + traits["digital_adoption"]) / 2), "instagram_usage": _category((traits["social_orientation"] + (1 if age < 40 else .36)) / 2), "youtube_usage": _category(traits["digital_adoption"]), "facebook_usage": _category(.68 if age > 42 else .34), "linkedin_usage": _category(.74 if employment.startswith("Employed") else .28), "messaging_frequency": _category(traits["social_orientation"]), "content_creation": _category((traits["openness"] + traits["social_orientation"]) / 2), "influencer_following": _category(traits["novelty_seeking"]*0.7 + traits["social_orientation"]*0.3),
        "entertainment_persona": persona_value, "preferred_ott_platform": preferred_ott_platform, "preferred_movie_genres": PERSONAS[persona_value][:2], "streaming_hours_weekly": round(max(1.2, 1.8 + traits["digital_adoption"] * 13.5 + traits["openness"]*2.1 + rng.gauss(0,1.2)), 1), "gaming_frequency": _category(traits["technology_affinity"] * (1.05 if age < 40 else .62) + traits["novelty_seeking"]*0.12), "music_frequency": _category((traits["openness"] + traits["digital_adoption"]) / 2), "preferred_music_genre": choose(rng, ["Film music", "Pop", "Indie", "Regional", "Classical", "Hip-hop", "Electronic"], [18,24,14,18,8,10,8]), "regional_music_preference": _category(.48 + (.22 if language != "English" else 0) + traits["cultural_openness"]*0.18), "international_music_preference": _category(traits["cultural_openness"]*0.75 + traits["openness"]*0.25),
        "dining_frequency": _category(_clip(0.42*income_factor + 0.32*traits["social_orientation"] + 0.14*ses +0.12*traits["openness"])), "vegetarian_preference": _vegetarian_choice(rng, context, traits["health_orientation"], age), "food_experimentation": _category(_clip(traits["openness"]*0.62 + traits["cultural_openness"]*0.28 + traits["novelty_seeking"]*0.10)), "travel_frequency": _category(_domain_base("travel", traits, income_factor, age, children, ses, context)), "preferred_destination_type": "Family and relaxation" if children else "Culture and cities" if traits["cultural_openness"] > .62 else "Nature and short breaks" if traits["environmental_awareness"]>0.60 else "Adventure" if traits["risk_tolerance"]>0.66 else choose(rng, ["Culture and cities","Nature and short breaks","Relaxation"], [34,32,34]), "travel_budget": _category(_clip(0.58*income_factor+0.22*ses+0.20*traits["luxury_orientation"])), "planning_behavior": _category(traits["planning_orientation"]), "booking_behavior": "Digital self-service" if traits["digital_adoption"] > .52 else "Assisted booking", "adventure_interest": _category((traits["risk_tolerance"] + traits["novelty_seeking"]) / 2), "home_ownership": "Owner" if (age > 36 and (income_factor > .42 or ses>0.52)) else "Renter", "housing_type": _housing_choice(rng, context, income_factor, household_size, ses), "neighborhood_type": "Urban residential" if context.urban_rural=="Urban" else "Rural/Semi-urban",
        "currency": context.currency, "cultural_context": context.region, "religious_affiliation": choose(rng, list(context.religions)), "local_food_pattern": local_food_pattern, "available_payment_method": available_payment_method, "primary_transport_mode": primary_transport_mode, "transport_infrastructure": "High access" if context.digital_access > .80 else "Moderate access" if context.digital_access>0.65 else "Mixed access", 
        **{key: _trait_label(key, value) for key, value in traits.items()}, "decision_speed": _category(0.55*traits["risk_tolerance"]+0.30*(1-traits["planning_orientation"])+0.15*traits["extraversion"]), "comparison_behavior": _category(0.50*traits["planning_orientation"]+0.30*traits["openness"]+0.20*traits["conscientiousness"]), "analytical_orientation": _category((traits["openness"] + traits["planning_orientation"]) / 2), "recommendation_dependence": _category(traits["social_orientation"]*0.75 + traits["agreeableness"]*0.25), "brand_trust": _category(0.55*traits["conscientiousness"]+0.25*traits["agreeableness"]+0.20*income_factor), "information_seeking": _category(traits["openness"]*0.68 + traits["planning_orientation"]*0.32), "digital_payment_preference": _category(_clip(0.68*traits["digital_adoption"]+0.18*income_factor+0.14*ses)), "card_usage": _category(_clip(0.42*income_factor + 0.38*traits["digital_adoption"] + 0.20*ses)), "wallet_usage": _category(_clip(0.72*traits["digital_adoption"]+0.18*income_factor+0.10*ses)), "cash_usage": _category(_clip(0.65*(1-traits["digital_adoption"])+0.20*(1-income_factor)+0.15*(1-ses))), "recurring_payment_behavior": _category((traits["digital_adoption"] + traits["conscientiousness"]) / 2), "pet_ownership": "Yes" if rng.random() < (0.18 + (0.10 if household_size>2 and income_factor>0.35 else 0) + (0.06 if context.housing_types and "Independent house" in context.housing_types else 0)) else "No", "hobby_count": max(1, round(1 + (traits["openness"] + traits["social_orientation"]) * 2.8 + rng.gauss(0,0.45))), "reading_frequency": _category(0.68*traits["openness"]+0.32*traits["planning_orientation"]), "sports_interest": _category((traits["health_orientation"] + traits["social_orientation"]) / 2), "photography_interest": _category((traits["openness"] + traits["cultural_openness"]) / 2), "creative_interest": _category(traits["openness"]*0.78 + traits["novelty_seeking"]*0.22), "volunteering_interest": _category(0.62*traits["agreeableness"]+0.28*traits["environmental_awareness"]+0.10*traits["social_orientation"]),
    }
    # Ensure housing consistency: home_ownership Owner implies housing_type not Shared housing
    if profile["home_ownership"] == "Owner" and profile["housing_type"] == "Shared/compact home":
        profile["housing_type"] = choose(rng, list(context.housing_types))
    for domain, topics in DOMAIN_TOPICS.items():
        base = _domain_base(domain, traits, income_factor, age, children, ses, context)
        for topic in topics:
            topic_adjustment = .12 if any(word in topic for word in ("international", "artificial", "luxury", "electric", "premium")) and traits["openness"] > .55 else 0
            # culture/environment tweaks
            if topic in {"regional_content","regional_cuisine","ethnic_wear"} and traits["cultural_openness"]<0.38: topic_adjustment -= 0.07
            if topic in {"sustainable_fashion","energy_saving","electric_vehicle"} and traits["environmental_awareness"]>0.62: topic_adjustment += 0.08
            for measure in MEASURES:
                measure_adjustment = {"interest_score": .04, "usage_frequency_score": 0, "purchase_intent_score": income_factor * .08 + ses*0.04, "research_intensity_score": traits["planning_orientation"] * .08}[measure]
                # health tweak for wellness
                if domain=="food" and topic=="healthy_food" and traits["health_orientation"]>0.60: measure_adjustment+=0.07
                if domain=="wellness" and traits["health_orientation"]>0.60: measure_adjustment+=0.06
                profile[f"{domain}_{topic}_{measure}"] = _five_level(_score(rng, base + topic_adjustment + measure_adjustment), measure)
    # Derived experience layer: summary, disposition, review/social-media attributes
    # (built from generated traits + observables, seeded for determinism).
    profile.update(derive_extras(rng, traits, profile, age))
    # Ensure consistent numeric traits overwritten? Keep label version as canonical (as before)
    # Price sensitivity and others already labels; reset numeric version for statistical tests? Keep labels per existing behavior
    missing = PROFILE_COLUMN_SET - profile.keys()
    if missing: raise RuntimeError(f"Generator missed schema columns: {sorted(missing)}")
    # Explicitly order output so personality_name is first (and matches PROFILE_COLUMNS)
    profile = {col: profile[col] for col in PROFILE_COLUMNS}
    # Extra coherence: validate hard constraints
    validate_profile(profile)
    return profile

def _vegetarian_choice(rng, context, health_orientation: float, age: int):
    # Country base rates (modeled, not stereotyped immutable) with probabilistic variation
    base_veg = {"India": 0.32, "United States": 0.06, "United Kingdom": 0.09, "Japan": 0.05, "Saudi Arabia": 0.03, "Brazil": 0.06, "Nigeria": 0.04}.get(context.country, 0.07)
    # Health orientation slightly increases veg/flexible
    veg_prob = base_veg + (health_orientation - 0.5) * 0.10
    # Age slight: younger more flexible
    flex_prob = 0.22 + (0.06 if age<35 else -0.04) + (health_orientation-0.5)*0.08
    meat_prob = 1 - veg_prob - flex_prob
    veg_prob = max(0.02, veg_prob); flex_prob = max(0.12, flex_prob); meat_prob = max(0.35, meat_prob)
    total = veg_prob+flex_prob+meat_prob
    veg_prob/=total; flex_prob/=total; meat_prob/=total
    return choose(rng, ["Vegetarian","Non-vegetarian","Flexible"], [veg_prob, meat_prob, flex_prob])

def _housing_choice(rng, context, income_factor: float, household_size: int, ses: float):
    # Conditional on income, household size, geography housing ecosystem
    # Prefer context.housing_types but weight by income/ses
    candidates = list(context.housing_types) if context.housing_types else ["Apartment","Independent house"]
    # Also add generic fallbacks
    generic = ["Apartment","Independent house","Shared/compact home"]
    # Weighting
    weights = []
    for h in candidates:
        w = 1.0
        if h in {"Independent house","Villa","Single-family home","Bungalow","Compound"} and (income_factor>0.55 or ses>0.60) and household_size>2: w*=1.45
        if h in {"Apartment","Condo","Gated community"} and income_factor>0.42: w*=1.20
        if h in {"Shared housing","Shared/compact home","Favela/Community housing"} and income_factor<0.30: w*=1.40
        if h in {"Council housing","Compound","Traditional house"} and ses<0.35: w*=1.15
        weights.append(w * rng.uniform(0.9,1.1))
    # ensure we can return a value that maps to expected housing_type categories in profile
    chosen = choose(rng, candidates, weights)
    # Normalize to profile housing_type vocabulary: keep original choice if matches expected, else map
    if chosen in {"Apartment","Independent house","Villa","Single-family home","Bungalow","Condo","Terraced house","Semi-detached"}:
        return chosen if rng.random()<0.7 else ("Apartment" if income_factor>0.45 else "Shared/compact home" if income_factor<0.28 else "Independent house")
    return chosen

def _behavioral_vector(profile: dict) -> tuple:
    """Compact behavioral signature for duplicate/near-duplicate detection."""
    keys = (
        "personality_name","openness","conscientiousness","extraversion","agreeableness","risk_tolerance","novelty_seeking","social_orientation","health_orientation","luxury_orientation","planning_orientation","cultural_openness","environmental_awareness","technology_affinity","price_sensitivity",
        "decision_speed","comparison_behavior","analytical_orientation","recommendation_dependence","brand_trust","information_seeking","discount_sensitivity","impulse_buying","research_before_purchase","premium_preference","cart_abandonment_tendency","booking_behavior","digital_payment_preference",
    )
    return tuple(profile.get(k) for k in keys)

def _is_excessive_moderate(profile: dict) -> bool:
    """Check if too many behavioral dimensions are simultaneously Moderate (low diversity).
    Only traits-derived fields are considered: brand_trust mixes in income (and
    therefore country), which would make retry behaviour country-dependent and
    break same-seed reproducibility across countries."""
    moderate_fields = ["decision_speed","comparison_behavior","analytical_orientation","recommendation_dependence","information_seeking","discount_sensitivity","impulse_buying","research_before_purchase"]
    mods = sum(1 for f in moderate_fields if profile.get(f) == "Moderate")
    return mods / len(moderate_fields) > 0.75

def generate_profiles(count: int, seed: int, country=None, age_range=None, preferred_language=None, persona=None, workers=1, country_mode=None, region=None, continent=None, countries=None) -> list[dict]:
    profiles = []
    seen = set()
    recent = []
    for idx in range(count):
        attempts = 0
        while True:
            eff_seed = seed + attempts * 1000003
            eff_index = idx + 1 + attempts * 1009
            p = generate_profile(eff_seed, eff_index, country, age_range, preferred_language, persona, country_mode, region, continent, countries)
            vec = _behavioral_vector(p)
            if vec in seen:
                attempts += 1
                if attempts > 5:
                    break
                continue
            # Near-duplicate: only check recent 80 to keep O(n) not O(n^2) for large batches
            is_near = False
            # Skip near-duplicate check for very large batches to keep tests fast
            if count <= 500:
                for existing_vec in recent[-80:]:
                    dist = sum(1 for a,b in zip(vec, existing_vec) if a != b)
                    if dist < 3:
                        is_near = True
                        break
            if is_near:
                attempts += 1
                if attempts > 5:
                    break
                continue
            if _is_excessive_moderate(p):
                attempts += 1
                if attempts > 3:
                    break
                continue
            break
        seen.add(vec)
        recent.append(vec)
        # keep recent window bounded
        if len(recent) > 120:
            recent.pop(0)
        profiles.append(p)
    return profiles
