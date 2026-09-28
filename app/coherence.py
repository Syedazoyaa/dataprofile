"""Probabilistic coherence helpers for Raven generation.

All relationships here are intentionally probabilistic, not rigid rules:
unusual but plausible profiles must remain possible. Each helper takes the
profile-specific RNG so output stays deterministic for a given seed/index.

Covers:
- life-stage resolution from age + experience + career level + employment
- education/industry/career pathway plausibility (professional training)
- occupation / job-function specificity
- geography-aware language selection with migration probability
- financial support for zero personal income
"""

LINGUA_FRANCA = {"English", "Hindi", "French", "Spanish", "Portuguese", "Arabic", "Swahili"}

# City/state -> locally dominant language boost. Only entries listed here get a
# boost, and only when that language is already in the country's language pool.
# Anything unlisted falls back to generic weighting, so no massive geo rewrite.
CITY_LANGUAGE_AFFINITY = {
    ("telangana", "hyderabad"): {"Telugu": 3.0, "Hindi": 1.6, "English": 1.6},
    ("karnataka", "bengaluru"): {"English": 2.2, "Hindi": 1.8, "Tamil": 1.4, "Telugu": 1.4},
    ("maharashtra", "mumbai"): {"Hindi": 2.4, "English": 1.8, "Tamil": 1.1, "Bengali": 1.1, "Telugu": 1.1},
}

# Migration/background draw probability: with this chance language is picked
# uniformly from the country pool, keeping e.g. Mumbai+Tamil valid.
MIGRATION_PROBABILITY = 0.08

# Job functions per industry: broad paths, not an exhaustive taxonomy.
INDUSTRY_JOB_FUNCTIONS = {
    "Healthcare": ("Clinical care", "Healthcare administration", "Medical research", "Health operations", "Technical/support services"),
    "Technology": ("Software & product development", "Technology operations", "Technology research", "Technical/support services", "Technology administration"),
    "Finance": ("Financial analysis", "Finance operations", "Finance administration", "Risk & compliance", "Client advisory services"),
    "Education": ("Teaching & instruction", "Education administration", "Education research", "Student support services", "Education operations"),
    "Manufacturing": ("Production operations", "Manufacturing administration", "Industrial research", "Technical/maintenance services", "Quality & logistics"),
    "Media": ("Content creation", "Media operations", "Media research", "Media administration", "Technical/support services"),
    "Retail": ("Store operations", "Retail administration", "Merchandising & buying", "Customer services", "Logistics & support"),
    "Consulting": ("Client advisory services", "Consulting operations", "Consulting research", "Consulting administration", "Analytical support"),
    "Services": ("Service operations", "Service administration", "Field & customer support", "Technical/support services", "Service research"),
    "Trade": ("Trade operations", "Trade administration", "Logistics & supply", "Client services", "Market research"),
    "Automotive": ("Automotive engineering", "Automotive operations", "Automotive research", "Technical/maintenance services", "Automotive administration"),
    "Energy": ("Energy operations", "Energy research", "Technical/field services", "Energy administration", "Safety & compliance"),
    "Construction": ("Site operations", "Construction administration", "Design & planning support", "Technical/trade services", "Project coordination"),
    "Agriculture": ("Farm operations", "Agriculture administration", "Agriculture research", "Field & technical support", "Supply & logistics"),
    "Government": ("Public administration", "Policy research", "Public operations", "Citizen services", "Technical/support services"),
    "Creative services": ("Creative production", "Creative operations", "Design research", "Studio administration", "Client & support services"),
    "Oil and gas": ("Field operations", "Energy research", "Technical/field services", "Energy administration", "Safety & compliance"),
}

GENERIC_JOB_FUNCTIONS = (
    "Operations",
    "Administration/Management",
    "Research & Development",
    "Technical/Specialist",
    "Customer & Field Support",
)

# Short title suffix per function family so occupation reads naturally while
# still containing the industry name for backward compatibility.
_FUNCTION_TITLE = {
    "Clinical care": "Clinician",
    "Healthcare administration": "Administrator",
    "Medical research": "Researcher",
    "Financial analysis": "Analyst",
    "Teaching & instruction": "Educator",
    "Content creation": "Content Specialist",
    "Software & product development": "Developer",
}
_FUNCTION_TITLE_FALLBACK = {
    "administration": "Administrator",
    "research": "Researcher",
    "operations": "Operations Specialist",
    "technical": "Technician",
    "support": "Support Specialist",
    "advisory": "Advisor",
    "analysis": "Analyst",
    "production": "Production Specialist",
    "instruction": "Educator",
    "creation": "Specialist",
}


def _choose(rng, values, weights=None):
    return rng.choices(list(values), weights=list(weights) if weights else None, k=1)[0]


def resolve_life_stage(rng, age, years_of_experience, career_level, employment_status, base_stage):
    """Reconcile the age-based stage with career state, probabilistically.

    Anchored stages (Teenager / University Student / Retired) follow employment
    and are returned unchanged. For working ages the base age stage is usually
    kept, but a career state that strongly contradicts it (e.g. Senior at 29)
    is probabilistically upgraded. No hard boundaries: every plausible stage
    keeps a non-zero probability.
    """
    if employment_status in ("School student", "Student"):
        return base_stage if base_stage in ("Teenager", "University Student") else "University Student"
    if employment_status == "Retired" or base_stage == "Retired":
        return "Retired"
    if base_stage in ("Teenager", "University Student"):
        return base_stage

    senior_career = career_level in ("Senior", "Leadership")
    experienced = years_of_experience >= 8
    mid_career = career_level in ("Mid-level", "Senior", "Leadership")

    if base_stage == "Early Career":
        if senior_career and experienced:
            # A senior professional should not routinely be labelled Early Career.
            return _choose(rng,
                           ["Established Professional", "Early Career", "Mid-Career"],
                           [78, 14, 8])
        if senior_career or years_of_experience >= 6:
            return _choose(rng,
                           ["Established Professional", "Early Career"],
                           [62, 38])
        return _choose(rng, ["Early Career", "Established Professional"], [88, 12])
    if base_stage == "Established Professional":
        if senior_career and experienced:
            return _choose(rng,
                           ["Established Professional", "Mid-Career", "Early Career"],
                           [70, 22, 8])
        if career_level == "Early" and years_of_experience <= 3:
            return _choose(rng,
                           ["Established Professional", "Early Career"],
                           [72, 28])
        return _choose(rng,
                       ["Established Professional", "Mid-Career", "Early Career"],
                       [80, 12, 8])
    if base_stage == "Mid-Career":
        if career_level == "Early" and years_of_experience <= 4:
            return _choose(rng, ["Mid-Career", "Established Professional"], [74, 26])
        return _choose(rng,
                       ["Mid-Career", "Established Professional", "Senior Professional"],
                       [78, 12, 10])
    if base_stage == "Senior Professional":
        if career_level == "Early" and not mid_career:
            return _choose(rng, ["Senior Professional", "Mid-Career"], [80, 20])
        return base_stage
    return base_stage


def job_function_for_industry(rng, industry, field_of_study, career_level):
    """Pick a specific job function within an industry.

    Field-of-study tilts the distribution (e.g. Business study nudges toward
    administration, Science toward research) but every function stays possible.
    """
    candidates = list(INDUSTRY_JOB_FUNCTIONS.get(industry, GENERIC_JOB_FUNCTIONS))
    weights = []
    for func in candidates:
        w = 1.0
        lowered = func.lower()
        if field_of_study == "Business" and "administr" in lowered:
            w *= 1.6
        if field_of_study in ("Science", "Healthcare") and "research" in lowered:
            w *= 1.5
        if field_of_study == "Healthcare" and industry == "Healthcare" and "clinical" in lowered:
            w *= 1.4
        if field_of_study == "Engineering" and "technical" in lowered:
            w *= 1.5
        if field_of_study in ("Arts and humanities",) and any(k in lowered for k in ("content", "creative", "client")):
            w *= 1.4
        if career_level == "Leadership" and "administr" in lowered:
            w *= 1.5
        weights.append(w * rng.uniform(0.85, 1.15))
    return _choose(rng, candidates, weights)


def occupation_title(career_level, industry, job_function, employment_status):
    """Human-readable occupation that keeps career + industry tokens."""
    if employment_status in ("School student", "Student", "Retired"):
        return employment_status
    if career_level in ("None", "Former professional"):
        return f"{industry} professional"
    suffix = _FUNCTION_TITLE.get(job_function)
    if not suffix:
        lowered = job_function.lower()
        suffix = "Professional"
        for key, title in _FUNCTION_TITLE_FALLBACK.items():
            if key in lowered:
                suffix = title
                break
    return f"{career_level} {industry} {suffix}"


def professional_training_for(rng, education_level, industry, career_level, years_of_experience):
    """Plausible career pathway marker (probabilistic, never a gate).

    Explains routes such as School education + Leadership via long experience:
    those profiles usually carry vocational/certification/on-the-job markers,
    while university pathways usually carry degree-linked or no extra marker.
    """
    senior = career_level in ("Senior", "Leadership")
    long_exp = years_of_experience >= 8
    if education_level == "School education" and senior and long_exp:
        return _choose(rng,
                       ["Vocational training", "Professional certification", "On-the-job advancement", "No formal additional training"],
                       [34, 30, 28, 8])
    if education_level == "School education" and senior:
        return _choose(rng,
                       ["Vocational training", "Professional certification", "On-the-job advancement", "No formal additional training"],
                       [28, 26, 26, 20])
    if education_level == "Professional diploma":
        return _choose(rng,
                       ["Vocational training", "Professional certification", "Degree-linked training", "No formal additional training"],
                       [38, 28, 18, 16])
    if career_level == "Leadership":
        return _choose(rng,
                       ["Management certification", "Professional certification", "Degree-linked training", "On-the-job advancement", "No formal additional training"],
                       [26, 24, 24, 14, 12])
    if industry in ("Healthcare", "Technology", "Finance") and senior:
        return _choose(rng,
                       ["Professional certification", "Degree-linked training", "On-the-job advancement", "No formal additional training"],
                       [36, 30, 18, 16])
    return _choose(rng,
                   ["No formal additional training", "Degree-linked training", "Professional certification", "On-the-job advancement", "Vocational training"],
                   [44, 24, 14, 10, 8])


def choose_language(rng, languages, state, city):
    """Context-aware language selection with migration probability.

    Boosts locally dominant languages where known, then falls back to a
    generic dominant-first weighting; a small migration draw keeps unusual
    combinations (e.g. Mumbai + Tamil) possible.
    """
    pool = list(languages)
    if not pool:
        return "English"
    if len(pool) == 1:
        return pool[0]
    if rng.random() < MIGRATION_PROBABILITY:
        return _choose(rng, pool)
    affinity = CITY_LANGUAGE_AFFINITY.get(
        ((state or "").strip().lower(), (city or "").strip().lower()))
    weights = []
    for i, lang in enumerate(pool):
        w = 1.0
        if affinity and lang in affinity:
            w *= affinity[lang]
        elif affinity:
            w *= 0.9
        else:
            # Generic: first-listed language is the dominant/local one.
            if i == 0:
                w *= 1.8
            elif lang in LINGUA_FRANCA:
                w *= 1.3
        weights.append(w * rng.uniform(0.85, 1.15))
    return _choose(rng, pool, weights)


def financial_support_for(rng, employment_status, monthly_income):
    """Support source for zero/low personal income (probabilistic)."""
    if monthly_income > 0:
        if employment_status in ("Student", "School student"):
            return _choose(rng, ["Family support", "Self-funded", "Scholarship/stipend"], [40, 40, 20])
        return "Self-funded"
    # Zero personal income: usually family-supported, sometimes stipend/none.
    if employment_status in ("Student", "School student"):
        return _choose(rng,
                       ["Family support", "Scholarship/stipend", "Self-funded", "None"],
                       [62, 16, 12, 10])
    if employment_status == "Retired":
        return _choose(rng, ["Pension/savings", "Family support", "Self-funded"], [60, 25, 15])
    return _choose(rng, ["Family support", "Self-funded", "None"], [55, 30, 15])


def supported_student_expenses(rng, income_scale):
    """Non-zero monthly expenses for a supported student, scaled to context."""
    monthly_scale = max(income_scale, 12000) / 12.0
    ratio = rng.uniform(0.10, 0.30)
    expenses = int(monthly_scale * ratio)
    return max(expenses, 1500)
