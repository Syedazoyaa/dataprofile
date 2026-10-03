from .geography import COUNTRIES
from .schemas import PERSONALITY_ARCHETYPES

# Rank maps for behavioral coherence (ordinal 1-5)
TRAIT_RANK = {
    "Very low":1, "Low":2, "Moderate":3, "High":4, "Very high":5,
    "Technology cautious":1, "Technology practical":2, "Technology comfortable":3, "Technology enthusiastic":4, "Technology leading":5,
    "Price insensitive":1, "Slightly price aware":2, "Price conscious":3, "Price sensitive":4, "Highly price sensitive":5,
    "Health disengaged":1, "Health aware":2, "Health balanced":3, "Health focused":4, "Highly health focused":5,
}
FREQ_RANK = {"Never":1, "Rarely":2, "Occasionally":3, "Frequently":4, "Very frequently":5}
INTEREST_RANK = {"Not interested":1, "Slightly interested":2, "Moderately interested":3, "Interested":4, "Highly interested":5}
LEVEL_RANK = {"Low":1, "Moderate":2, "High":3}

def _expected_personality_name(profile: dict) -> str | None:
    """Re-derive expected archetype by delegating to generator's deterministic mapping.
    This ensures validation uses exactly the same discretization and scoring as generation,
    avoiding label-midpoint rounding divergence.
    """
    # Lazy import to avoid circular dependency (generator imports validate_profile)
    try:
        from .generator import _derive_personality_name, _trait_label
    except ImportError:
        return None
    # Reconstruct traits dict from stored labels by mapping back to midpoints,
    # then feed through same _derive which will discretize again identically.
    label_to_val = {
        "Very low": 0.12, "Low": 0.30, "Moderate": 0.50, "High": 0.72, "Very high": 0.88,
        "Technology cautious": 0.12, "Technology practical": 0.30, "Technology comfortable": 0.50, "Technology enthusiastic": 0.72, "Technology leading": 0.88,
        "Price insensitive": 0.12, "Slightly price aware": 0.30, "Price conscious": 0.50, "Price sensitive": 0.72, "Highly price sensitive": 0.88,
        "Health disengaged": 0.12, "Health aware": 0.30, "Health balanced": 0.50, "Health focused": 0.72, "Highly health focused": 0.88,
    }
    def get_trait(name):
        v = profile.get(name)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str) and v in label_to_val:
            return label_to_val[v]
        return 0.5
    t = {k: get_trait(k) for k in ("openness","conscientiousness","extraversion","agreeableness","risk_tolerance","novelty_seeking","social_orientation","health_orientation","luxury_orientation","planning_orientation","cultural_openness","environmental_awareness","technology_affinity","price_sensitivity")}
    # _derive expects raw dict but will discretize via _trait_label internally, so passing midpoints is safe (idempotent)
    return _derive_personality_name(t)

def _rank(value, mapping):
    return mapping.get(value, 3)

def _behavioral_coherence(profile: dict) -> dict:
    """Compute heuristic behavioral alignment scores 0-1 (not realism claims).
    Each dimension compares upstream driver vs downstream observable probabilistically.
    Scores are transparent linear distances, not learned models.
    """
    scores = {}
    # Age / life stage alignment (career-aware: a reconciled stage that matches
    # career state scores highly even when it differs from the pure age anchor)
    age = profile.get("age", 0)
    life = profile.get("life_stage", "")
    expected = "Teenager" if age<18 else "University Student" if age<23 else "Early Career" if age<30 else "Established Professional" if age<40 else "Mid-Career" if age<52 else "Senior Professional" if age<64 else "Retired"
    if life == expected:
        scores["age_life_stage_alignment"] = 1.0
    else:
        order = ["Teenager", "University Student", "Early Career", "Established Professional", "Mid-Career", "Senior Professional", "Retired"]
        career = profile.get("career_level", "Early")
        exp = profile.get("years_of_experience", 0)
        # A senior/experienced career legitimately pulls the stage upward.
        career_consistent = (
            (life == "Established Professional" and expected == "Early Career"
             and (career in ("Mid-level", "Senior", "Leadership") or exp >= 5))
            or (life == "Mid-Career" and expected in ("Early Career", "Established Professional")
                and (career in ("Senior", "Leadership") or exp >= 8))
            or (life == "Early Career" and expected == "Established Professional"
                and (career == "Early" or exp <= 4))
            or (life in ("Mid-Career", "Established Professional") and expected == "Senior Professional"
                and career == "Early")
        )
        if career_consistent:
            scores["age_life_stage_alignment"] = 0.9
        elif life in order and expected in order and abs(order.index(life) - order.index(expected)) <= 1:
            scores["age_life_stage_alignment"] = 0.75
        else:
            scores["age_life_stage_alignment"] = 0.45

    # Age / education alignment (years_of_education plausible)
    yoe = profile.get("years_of_education", 10)
    edu = profile.get("education_level","")
    # Teenager must be school, student undergrad etc already hard-checked; soft score for adults
    if life in {"Teenager","University Student","Retired"}:
        scores["age_education_alignment"] = 1.0
    else:
        # Postgraduate should be >=17 etc already enforced; score high if plausible
        plausible = (edu=="School education" and yoe==10) or (edu!="School education" and yoe>=12)
        scores["age_education_alignment"] = 1.0 if plausible else 0.6

    # Education / career alignment
    # Higher education weakly associated with higher career_level (probabilistic, not deterministic)
    career = profile.get("career_level","Early")
    edu_rank = {"School education":1, "Professional diploma":2, "Undergraduate":3, "Postgraduate":4}.get(edu,2)
    career_rank = {"None":0, "Early":1, "Mid-level":2, "Senior":3, "Leadership":4, "Former professional":2}.get(career,1)
    # Alignment is not strict: score reduces only if strong mismatch (e.g., School+Leadership with no experience is less coherent)
    exp = profile.get("years_of_experience",0)
    training = profile.get("professional_training", "")
    if edu_rank <=1 and career_rank >=4 and exp < 12:
        scores["education_career_alignment"] = 0.55
    elif edu_rank <=1 and career_rank >=4:
        # Long experience and/or a professional-training pathway keeps this plausible.
        scores["education_career_alignment"] = 0.85 if training and training != "No formal additional training" else 0.72
    elif edu_rank >=4 and career_rank <=1 and exp > 8:
        scores["education_career_alignment"] = 0.62
    else:
        scores["education_career_alignment"] = 0.92

    # Career / income alignment (income should roughly increase with career+experience+education)
    income = profile.get("annual_income",0)
    country = profile.get("country","India")
    scale = COUNTRIES.get(country, {}).get("income",900000)
    income_factor = income / (scale*2.8) if scale else 0
    expected_factor = 0.15 + career_rank*0.14 + min(exp,20)/50*0.25  # heuristic expected
    diff = abs(income_factor - expected_factor)
    scores["career_income_alignment"] = max(0.45, 1 - diff*1.4)

    # Financial alignment (expenses <= income, savings rate plausible with planning)
    savings_rate = profile.get("savings_rate",0)
    planning_rank = _rank(profile.get("planning_orientation","Moderate"), TRAIT_RANK)
    # High planning should correlate with higher savings, but probabilistically
    # Score high if savings_rate in [0.05,0.45] for most, zero only if income zero
    if income==0:
        scores["financial_alignment"] = 1.0 if savings_rate==0 else 0.5
    else:
        # Check expenses consistency already hard; behavioral: savings_rate vs planning
        # Expect planning High => savings >=0.15 somewhat
        expected_savings = 0.12 + (planning_rank-3)*0.04
        diff2 = abs(savings_rate - expected_savings)
        scores["financial_alignment"] = max(0.55, 1 - diff2*2.2)

    # Family / household alignment
    marital = profile.get("marital_status","Single")
    children = profile.get("number_of_children",0)
    hsize = profile.get("household_size",1)
    # Household should be at least 1+spouse+children (+possible parents)
    min_expected = 1 + (1 if marital=="Married" else 0) + children
    if hsize < min_expected: scores["family_household_alignment"] = 0.35
    elif hsize > min_expected+2: scores["family_household_alignment"] = 0.78  # extended family plausible but slight mismatch
    else: scores["family_household_alignment"] = 1.0

    # Personality / behavior alignment (trait vs observable)
    # Tech affinity vs digital adoption & smartphone usage
    tech_r = _rank(profile.get("technology_affinity","Moderate"), TRAIT_RANK)
    dig_r = _rank(profile.get("digital_adoption","Moderate"), TRAIT_RANK) if "digital_adoption" in profile else 3
    # digital_adoption stored as label "Technology leading" etc? Actually traits all label-mapped, but digital_adoption is also label? In generator we map all traits via _trait_label, so digital_adoption label is generic Very low..Very high, not tech-specific. Use TRAIT_RANK generic.
    # For compatibility, treat both via TRAIT_RANK
    tech_digital_diff = abs(tech_r - dig_r)/4
    scores["personality_tech_alignment"] = max(0.45, 1 - tech_digital_diff*1.1)
    # Health orientation vs wellness behavior
    health_r = _rank(profile.get("health_orientation","Moderate"), TRAIT_RANK)
    wellness_freq = _rank(profile.get("wellness_fitness_usage_frequency_score","Occasionally"), FREQ_RANK)
    # Map health 1-5 vs wellness freq 1-5
    health_wellness_diff = abs(health_r - wellness_freq)/4
    scores["personality_health_alignment"] = max(0.50, 1 - health_wellness_diff*0.95)
    # Price sensitivity vs discount/brand behavior
    price_r = _rank(profile.get("price_sensitivity","Moderate"), TRAIT_RANK) if "Highly price sensitive" in str(profile.get("price_sensitivity")) or "Price" in str(profile.get("price_sensitivity")) else _rank(profile.get("price_sensitivity","Moderate"), TRAIT_RANK)
    # Actually price_sensitivity label is price-specific, rank via TRAIT_RANK works
    discount_r = _rank(profile.get("discount_sensitivity","Moderate"), LEVEL_RANK) if profile.get("discount_sensitivity") in LEVEL_RANK else 2
    # Convert LEVEL 1-3 to 1-5 scale: Low=1, Moderate=3, High=5 approx
    level_to_5 = {1:1, 2:3, 3:5}
    discount_5 = level_to_5.get(discount_r,3)
    price_discount_diff = abs(price_r - discount_5)/4
    scores["personality_price_alignment"] = max(0.50, 1 - price_discount_diff*0.9)
    # Social orientation vs social frequency
    social_r = _rank(profile.get("social_orientation","Moderate"), TRAIT_RANK)
    msg_r = _rank(profile.get("messaging_frequency","Occasionally"), FREQ_RANK)
    # scale msg 1-5 vs social 1-5
    social_msg_diff = abs(social_r - ((msg_r+1)//1))/4  # rough
    # Actually use FREQ directly: FREQ 1-5 vs TRAIT 1-5
    # Map msg freq to 1-5 already
    social_msg_diff = abs(social_r - msg_r)/4
    scores["personality_social_alignment"] = max(0.50, 1 - social_msg_diff*0.95)

    # Geography / environment alignment (check context consistency not personality)
    country_ctx = COUNTRIES.get(country)
    geo_score = 1.0
    if country_ctx:
        if profile.get("currency") != country_ctx["currency"]: geo_score *= 0.4
        if profile.get("primary_language") not in country_ctx["languages"]: geo_score *= 0.5
        if profile.get("available_payment_method") not in country_ctx["payments"]: geo_score *= 0.5
        if profile.get("primary_transport_mode") not in country_ctx["transport"]: geo_score *= 0.5
        if profile.get("local_food_pattern") not in country_ctx["foods"]: geo_score *= 0.5
    scores["geography_environment_alignment"] = geo_score

    # Overall behavioral coherence = mean of alignments
    overall = round(sum(scores.values()) / len(scores), 3) if scores else 0.0
    scores["overall_behavioral_coherence"] = overall
    # Round individual
    for k in list(scores.keys()):
        if k != "overall_behavioral_coherence":
            scores[k] = round(scores[k], 3)
    return scores

def assess_profile(profile: dict) -> dict:
    """Return structured constraints and scores derived from their outcomes."""
    violations = []
    def check(condition, rule, message):
        if not condition: violations.append({"rule": rule, "severity": "error", "message": message})
    check(16 <= profile.get("age", 0) <= 78, "age_bounds", "Age is outside the supported range.")
    _income = profile.get("monthly_income", -1)
    _savings = profile.get("monthly_savings", -1)
    _support = profile.get("financial_support_source", "Self-funded")
    if _income == 0:
        # Zero personal income with an external support source may still spend.
        check(_savings == 0, "finance_consistency", "Savings are inconsistent with monthly income.")
        check(profile.get("monthly_expenses", -1) >= 0, "finance_consistency", "Expenses are inconsistent with monthly income.")
        if profile.get("monthly_expenses", 0) > 0:
            check(_support not in (None, "", "None"), "finance_support_consistency", "Non-zero expenses with zero income require a financial support source.")
    else:
        check(_savings >= 0 and _savings <= _income, "finance_consistency", "Savings are inconsistent with monthly income.")
    check(profile.get("years_of_experience", 999) <= max(0, profile.get("age", 0) - 16), "career_age_consistency", "Experience exceeds plausible career duration.")
    check(not (profile.get("age", 0) < 20 and profile.get("number_of_children", 0) > 0), "family_age_consistency", "Child count is implausible for age.")
    check(not (profile.get("life_stage") == "University Student" and profile.get("career_level") != "None"), "student_career_consistency", "Student career level is inconsistent.")
    check(not (profile.get("life_stage") == "Retired" and profile.get("employment_status") != "Retired"), "retirement_consistency", "Retired life stage is inconsistent.")
    check(profile.get("household_size", 1) >= 1 and profile.get("household_size", 1) >= profile.get("number_of_children", 0) + (1 if profile.get("marital_status")=="Married" else 0) or profile.get("parents_in_household"), "household_consistency", "Household size inconsistent with family structure.")
    country = COUNTRIES.get(profile.get("country"))
    check(country is not None and profile.get("currency") == country["currency"], "country_currency_consistency", "Currency does not match geographic context.")
    if country:
        check(profile.get("primary_language") in country["languages"], "country_language_consistency", "Language is not available in geographic context.")
        check(profile.get("available_payment_method") in country["payments"], "country_payment_consistency", "Payment method is not available in geographic context.")
        check(profile.get("primary_transport_mode") in country["transport"], "country_transport_consistency", "Transport mode is not available in geographic context.")
        check(profile.get("local_food_pattern") in country["foods"], "country_food_consistency", "Food pattern is not available in geographic context.")
        check(profile.get("country_code") == country["code"], "country_code_consistency", "Country code mismatch.")
    # Gender values must never leak into language fields (schema/mapping guard).
    _gender_values = {"Female", "Male", "Non-binary"}
    check(profile.get("primary_language") not in _gender_values, "language_gender_mapping", "Language field contains a gender value.")
    check(profile.get("preferred_language") not in _gender_values, "language_gender_mapping", "Language field contains a gender value.")
    # Derived experience-layer attributes must carry valid categorical values.
    _level_values = {"Low", "Moderate", "High"}
    for _key in ("review_influence", "interactive_content_engagement", "social_shopping_tendency",
                 "advertisement_responsiveness", "social_consumer_tendency", "social_creator_tendency",
                 "social_engagement_level", "trend_sensitivity", "influencer_influence",
                 "brand_interaction_tendency"):
        check(profile.get(_key) in _level_values, "derived_level_consistency", f"{_key} has an invalid level.")
    check(profile.get("social_disposition") in {"Introvert", "Ambivert", "Extrovert"}, "derived_disposition_consistency", "social_disposition has an invalid value.")
    check(isinstance(profile.get("profile_summary"), str) and profile.get("profile_summary", "").strip() != "", "profile_summary_required", "profile_summary is required and non-empty.")
    # Education / experience additional hard check
    edu = profile.get("education_level")
    yoe = profile.get("years_of_education", 0)
    if edu == "School education":
        check(yoe == 10, "education_years_consistency", "Years of education inconsistent with school level.")
    # Income non-negative
    check(profile.get("annual_income", -1) >= 0, "income_nonnegative", "Income negative.")
    check(profile.get("monthly_income", -1) >= 0, "monthly_income_nonnegative", "Monthly income negative.")
    # personality_name mandatory and behavior-derived
    pname = profile.get("personality_name")
    check(isinstance(pname, str) and pname.strip() != "", "personality_name_required", "personality_name is required and non-empty.")
    check(pname in PERSONALITY_ARCHETYPES, "personality_name_archetype", f"personality_name must be one of {PERSONALITY_ARCHETYPES}.")
    # ordering: personality_name must be first key (dict insertion order)
    try:
        first_key = next(iter(profile))
        check(first_key == "personality_name", "personality_name_ordering", "personality_name must be the first column/field.")
    except StopIteration:
        check(False, "personality_name_ordering", "Profile is empty.")
    # consistency with underlying traits — archetype should be recognizable via preferred ranges with allowed variation
    # Use archetype target ranges: for claimed archetype, core traits should be within target ±0.28 (allowed) and at least 60% within ±0.18 (preferred)
    try:
        from .generator import ARCHETYPE_TARGETS
    except ImportError:
        ARCHETYPE_TARGETS = {}
    if pname in ARCHETYPE_TARGETS:
        targets = ARCHETYPE_TARGETS[pname]
        label_to_val = {
            "Very low": 0.12, "Low": 0.30, "Moderate": 0.50, "High": 0.72, "Very high": 0.88,
            "Technology cautious": 0.12, "Technology practical": 0.30, "Technology comfortable": 0.50, "Technology enthusiastic": 0.72, "Technology leading": 0.88,
            "Price insensitive": 0.12, "Slightly price aware": 0.30, "Price conscious": 0.50, "Price sensitive": 0.72, "Highly price sensitive": 0.88,
            "Health disengaged": 0.12, "Health aware": 0.30, "Health balanced": 0.50, "Health focused": 0.72, "Highly health focused": 0.88,
        }
        def get_trait(name):
            v = profile.get(name)
            if isinstance(v, (int, float)): return float(v)
            if isinstance(v, str) and v in label_to_val: return label_to_val[v]
            return 0.5
        # Check core traits for this archetype (all 14, but with archetype-specific tolerance)
        within_preferred = 0
        within_allowed = 0
        total = 0
        for trait, target in targets.items():
            total += 1
            actual = get_trait(trait)
            diff = abs(actual - target)
            if diff <= 0.18:
                within_preferred += 1
                within_allowed += 1
            elif diff <= 0.28:
                within_allowed += 1
        # Require at least 50% within preferred and 75% within allowed, else flag inconsistency
        # Balanced is more lenient (all moderate, so many traits near 0.5)
        if pname == "Balanced":
            # Balanced should have low variance (most traits near 0.5)
            vals = [get_trait(k) for k in targets]
            mad = sum(abs(v - 0.5) for v in vals) / len(vals)
            if mad > 0.22:  # too extreme for Balanced
                check(False, "personality_name_consistency", f"Balanced archetype should have traits clustered near Moderate (mad {mad:.3f} too high).")
        else:
            if within_allowed / total < 0.65:
                check(False, "personality_name_consistency", f"personality_name '{pname}' traits outside allowed variation ({within_allowed}/{total} within ±0.28).")
            elif within_preferred / total < 0.35:
                # Allow secondary variation: at least 35% within preferred, but warn if too low
                # Use softer check: if less than 30% preferred, flag
                if within_preferred / total < 0.25:
                    check(False, "personality_name_consistency", f"personality_name '{pname}' lacks archetype signature ({within_preferred}/{total} within preferred ±0.18).")
    else:
        # Fallback to scoring check
        expected = _expected_personality_name(profile)
        check(pname == expected, "personality_name_consistency", f"personality_name '{pname}' inconsistent (expected '{expected}').")

    coherence_score = round(max(0.0, 1 - len(violations) * .15), 2)
    behavioral = _behavioral_coherence(profile)
    return {"valid": not violations, "violations": violations, "coherence_score": coherence_score, "behavioral_coherence": behavioral, "behavioral_coherence_score": behavioral["overall_behavioral_coherence"]}

def validate_profile(profile: dict) -> dict:
    result = assess_profile(profile)
    if not result["valid"]: raise ValueError(result["violations"][0]["message"])
    return result
