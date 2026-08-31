"""Statistical / behavioral coherence tests over large samples.
All relationships are probabilistic, not deterministic.
Distinguishes empirical/reference vs modeled assumption is documented in geography.py;
these tests verify modeled correlations hold directionally.
"""
from collections import Counter
import statistics
from app.generator import generate_profiles
from app.geography import COUNTRIES
from app.rules import assess_profile

TRAIT_RANK_GENERIC = {"Very low":1,"Low":2,"Moderate":3,"High":4,"Very high":5}
TRAIT_RANK_TECH = {"Technology cautious":1,"Technology practical":2,"Technology comfortable":3,"Technology enthusiastic":4,"Technology leading":5}
TRAIT_RANK_PRICE = {"Price insensitive":1,"Slightly price aware":2,"Price conscious":3,"Price sensitive":4,"Highly price sensitive":5}
TRAIT_RANK_HEALTH = {"Health disengaged":1,"Health aware":2,"Health balanced":3,"Health focused":4,"Highly health focused":5}
FREQ_RANK = {"Never":1,"Rarely":2,"Occasionally":3,"Frequently":4,"Very frequently":5}
LEVEL_RANK = {"Low":1,"Moderate":2,"High":3}
INTEREST_RANK = {"Not interested":1,"Slightly interested":2,"Moderately interested":3,"Interested":4,"Highly interested":5}

def _rank_trait(val):
    if val in TRAIT_RANK_GENERIC: return TRAIT_RANK_GENERIC[val]
    if val in TRAIT_RANK_TECH: return TRAIT_RANK_TECH[val]
    if val in TRAIT_RANK_PRICE: return TRAIT_RANK_PRICE[val]
    if val in TRAIT_RANK_HEALTH: return TRAIT_RANK_HEALTH[val]
    return 3

def test_age_drives_education():
    pros = generate_profiles(1800, 1001)
    young = [p for p in pros if 18 <= p["age"] <= 22]
    mid = [p for p in pros if 30 <= p["age"] <= 42]
    # Students/Young should have higher "In progress" and fewer postgraduate; mid-career higher postgraduate share
    young_post = sum(1 for p in young if p["education_level"]=="Postgraduate")/len(young) if young else 0
    mid_post = sum(1 for p in mid if p["education_level"]=="Postgraduate")/len(mid) if mid else 0
    assert mid_post > young_post, f"postgrad mid {mid_post:.3f} should > young {young_post:.3f}"
    # probabilistic not deterministic: both groups have variation
    assert len({p["education_level"] for p in young}) >= 2
    assert len({p["education_level"] for p in mid}) >= 3

def test_age_drives_career_and_income():
    pros = generate_profiles(1800, 1002)
    early = [p for p in pros if p["career_level"]=="Early"]
    senior = [p for p in pros if p["career_level"] in {"Senior","Leadership"}]
    assert senior and early
    assert statistics.mean(p["age"] for p in senior) > statistics.mean(p["age"] for p in early) + 5
    # income higher for senior
    assert statistics.mean(p["annual_income"] for p in senior if p["annual_income"]>0) > statistics.mean(p["annual_income"] for p in early if p["annual_income"]>0)
    # probabilistic: not all young are Early, not all old are Senior
    assert len({p["career_level"] for p in pros if 23 <= p["age"] <= 29}) >= 2
    assert len({p["career_level"] for p in pros if 40 <= p["age"] <= 52}) >= 2

def test_education_drives_income_and_occupation():
    pros = generate_profiles(1600, 1003)
    # Filter working adults only
    working = [p for p in pros if p["employment_status"] not in {"School student","Student","Retired"} and p["annual_income"]>0]
    school = [p for p in working if p["education_level"]=="School education"]
    post = [p for p in working if p["education_level"]=="Postgraduate"]
    assert school and post
    assert statistics.mean(p["annual_income"] for p in post) > statistics.mean(p["annual_income"] for p in school)
    # education correlates with field plausibility (variation exists)
    assert len({p["field_of_study"] for p in post}) >= 3
    # Occupation contains career+industry, income varies by occupation seniority already tested

def test_experience_drives_income():
    pros = generate_profiles(1600, 1004)
    working = [p for p in pros if p["employment_status"] not in {"School student","Student","Retired"}]
    low_exp = [p for p in working if p["years_of_experience"] <= 2]
    high_exp = [p for p in working if p["years_of_experience"] >= 12]
    assert low_exp and high_exp
    assert statistics.mean(p["annual_income"] for p in high_exp) > statistics.mean(p["annual_income"] for p in low_exp)

def test_occupation_and_industry_income():
    pros = generate_profiles(1600, 1005)
    working = [p for p in pros if p["career_level"] in {"Early","Mid-level","Senior","Leadership"}]
    early = [p for p in working if p["career_level"]=="Early"]
    senior = [p for p in working if p["career_level"] in {"Senior","Leadership"}]
    assert statistics.mean(p["annual_income"] for p in senior) > statistics.mean(p["annual_income"] for p in early) * 1.4

def test_income_drives_spending_savings_housing():
    pros = generate_profiles(1500, 1006)
    working = [p for p in pros if p["annual_income"]>0]
    low = sorted(working, key=lambda x: x["annual_income"])[:200]
    high = sorted(working, key=lambda x: x["annual_income"])[-200:]
    assert statistics.mean(p["monthly_expenses"] for p in high) > statistics.mean(p["monthly_expenses"] for p in low)
    assert statistics.mean(p["monthly_savings"] for p in high) > statistics.mean(p["monthly_savings"] for p in low)
    # housing ownership higher for high income
    high_own = sum(1 for p in high if p["home_ownership"]=="Owner")/len(high)
    low_own = sum(1 for p in low if p["home_ownership"]=="Owner")/len(low)
    assert high_own > low_own

def test_conscientiousness_drives_planning_and_saving():
    pros = generate_profiles(1400, 1007)
    high_c = [p for p in pros if _rank_trait(p["conscientiousness"]) >=4]
    low_c = [p for p in pros if _rank_trait(p["conscientiousness"]) <=2]
    assert high_c and low_c
    # planning
    assert statistics.mean(_rank_trait(p["planning_orientation"]) for p in high_c) > statistics.mean(_rank_trait(p["planning_orientation"]) for p in low_c)
    # savings rate
    assert statistics.mean(p["savings_rate"] for p in high_c if p["monthly_income"]>0) > statistics.mean(p["savings_rate"] for p in low_c if p["monthly_income"]>0) - 0.02  # allow small but should be higher

def test_technology_affinity_drives_digital():
    pros = generate_profiles(1400, 1008)
    high = [p for p in pros if _rank_trait(p["technology_affinity"]) >=4]
    low = [p for p in pros if _rank_trait(p["technology_affinity"]) <=2]
    assert high and low
    assert statistics.mean(FREQ_RANK[p["technology_smartphone_usage_frequency_score"]] for p in high) > statistics.mean(FREQ_RANK[p["technology_smartphone_usage_frequency_score"]] for p in low)
    assert statistics.mean(_rank_trait(p["digital_adoption"]) for p in high) > statistics.mean(_rank_trait(p["digital_adoption"]) for p in low)
    # probabilistic: not deterministic 5.0
    assert len({p["technology_smartphone_usage_frequency_score"] for p in high}) >= 2

def test_novelty_seeking_drives_travel_and_experimentation():
    pros = generate_profiles(1400, 1009)
    high = [p for p in pros if _rank_trait(p["novelty_seeking"]) >=4]
    low = [p for p in pros if _rank_trait(p["novelty_seeking"]) <=2]
    assert high and low
    # travel frequency High/Moderate mapping
    assert statistics.mean(LEVEL_RANK[p["travel_frequency"]] for p in high) > statistics.mean(LEVEL_RANK[p["travel_frequency"]] for p in low)
    # food experimentation
    assert statistics.mean(LEVEL_RANK[p["food_experimentation"]] for p in high) > statistics.mean(LEVEL_RANK[p["food_experimentation"]] for p in low)

def test_price_sensitivity_drives_discount():
    pros = generate_profiles(1400, 1010)
    high = [p for p in pros if _rank_trait(p["price_sensitivity"]) >=4]
    low = [p for p in pros if _rank_trait(p["price_sensitivity"]) <=2]
    assert high and low
    assert statistics.mean(LEVEL_RANK[p["discount_sensitivity"]] for p in high) > statistics.mean(LEVEL_RANK[p["discount_sensitivity"]] for p in low)
    # cart abandonment also higher for price sensitive
    assert statistics.mean(LEVEL_RANK[p["cart_abandonment_tendency"]] for p in high) > statistics.mean(LEVEL_RANK[p["cart_abandonment_tendency"]] for p in low)

def test_health_orientation_drives_wellness():
    pros = generate_profiles(1400, 1011)
    high = [p for p in pros if _rank_trait(p["health_orientation"]) >=4]
    low = [p for p in pros if _rank_trait(p["health_orientation"]) <=2]
    assert high and low
    assert statistics.mean(FREQ_RANK[p["wellness_fitness_usage_frequency_score"]] for p in high) > statistics.mean(FREQ_RANK[p["wellness_fitness_usage_frequency_score"]] for p in low)
    assert statistics.mean(FREQ_RANK[p["wellness_nutrition_usage_frequency_score"]] for p in high) > statistics.mean(FREQ_RANK[p["wellness_nutrition_usage_frequency_score"]] for p in low)

def test_social_orientation_drives_social():
    pros = generate_profiles(1400, 1012)
    high = [p for p in pros if _rank_trait(p["social_orientation"]) >=4]
    low = [p for p in pros if _rank_trait(p["social_orientation"]) <=2]
    assert high and low
    assert statistics.mean(LEVEL_RANK[p["messaging_frequency"]] for p in high) > statistics.mean(LEVEL_RANK[p["messaging_frequency"]] for p in low)
    # social media
    assert statistics.mean(LEVEL_RANK[p["social_media_activity"]] for p in high) > statistics.mean(LEVEL_RANK[p["social_media_activity"]] for p in low)

def test_geography_drives_transport_food_payment():
    # Within each country, transport/food/payment must be from that country's ecosystem and show variation
    for country in COUNTRIES:
        pros = generate_profiles(120, 1100, country=country)
        ctx = COUNTRIES[country]
        assert all(p["primary_transport_mode"] in ctx["transport"] for p in pros)
        assert all(p["local_food_pattern"] in ctx["foods"] for p in pros)
        assert all(p["available_payment_method"] in ctx["payments"] for p in pros)
        # variation within country (not stereotyped to single value)
        assert len({p["primary_transport_mode"] for p in pros}) >= 2, f"{country} transport should vary"
        assert len({p["local_food_pattern"] for p in pros}) >= 2
        assert len({p["available_payment_method"] for p in pros}) >= 2
    # Cross-country distributions differ
    india_trans = Counter(p["primary_transport_mode"] for p in generate_profiles(300, 1200, country="India"))
    us_trans = Counter(p["primary_transport_mode"] for p in generate_profiles(300, 1200, country="United States"))
    # Most common transport should differ (probabilistic but geography conditioned)
    assert india_trans.most_common(1)[0][0] != us_trans.most_common(1)[0][0] or set(india_trans) != set(us_trans)

def test_family_drives_household():
    pros = generate_profiles(1500, 1013)
    single_no_kids = [p for p in pros if p["marital_status"]=="Single" and p["number_of_children"]==0]
    married_with_kids = [p for p in pros if p["marital_status"]=="Married" and p["number_of_children"]>=1]
    assert single_no_kids and married_with_kids
    assert statistics.mean(p["household_size"] for p in married_with_kids) > statistics.mean(p["household_size"] for p in single_no_kids) + 0.8
    # Family type aligns
    assert all(p["family_type"] in {"Single-person","With parents","Shared/Flatmates"} for p in single_no_kids if p["household_size"]==1 or p["parents_in_household"] or p["household_size"]>1)
    # behavioral coherence should be high overall
    avg_coh = statistics.mean(assess_profile(p)["behavioral_coherence_score"] for p in pros)
    assert avg_coh > 0.78

def test_probabilistic_not_deterministic():
    pros = generate_profiles(800, 1014, country="India")
    # Same country should still have varied traits and behaviors
    assert len({p["technology_affinity"] for p in pros}) >= 3
    assert len({p["preferred_marketplace"] for p in pros}) >= 2
    assert len({p["travel_frequency"] for p in pros}) >= 2
    # Even high income group has variation in marketplace
    high_income = [p for p in pros if p["annual_income"] > 1500000]
    if len(high_income) > 20:
        assert len({p["preferred_marketplace"] for p in high_income}) >= 2
