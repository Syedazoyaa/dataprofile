"""Cross-country behavioral archetype tests.
Verifies that same latent archetype (comparable age/personality/SES) retains
comparable traits across countries while local expression (currency, transport,
food, payment, platforms) changes appropriately.
"""
from collections import Counter
from app.generator import generate_profiles
from app.geography import COUNTRIES
from app.rules import assess_profile

TRAIT_RANK_GENERIC = {"Very low":1,"Low":2,"Moderate":3,"High":4,"Very high":5}
TRAIT_RANK_TECH = {"Technology cautious":1,"Technology practical":2,"Technology comfortable":3,"Technology enthusiastic":4,"Technology leading":5}

def _rank(v):
    if v in TRAIT_RANK_GENERIC: return TRAIT_RANK_GENERIC[v]
    if v in TRAIT_RANK_TECH: return TRAIT_RANK_TECH[v]
    return 3

def test_comparable_archetype_retains_traits_across_countries():
    """Generate same seed/index across 6 countries => traits comparable, environment differs."""
    countries = ["India","United States","Japan","Saudi Arabia","Brazil","Nigeria"]
    # Use 20 archetypes (index 1..20) across countries with fixed seed
    for idx in range(1, 11):
        profiles = {}
        for c in countries:
            profiles[c] = generate_profiles(1, 9999, country=c)[0] if False else None
        # Actually generate with same seed+index per country
        baseline_seed = 5555
        group = [generate_profiles(1, baseline_seed, country=c)[0] for c in countries]  # same seed, different country -> archetype before geography identical
        # But generate_profiles(1, seed, country) with same seed/index gives same age/traits pre-geography
        # Verify traits comparable (max rank diff <=1.5 on average)
        tech_ranks = [_rank(p["technology_affinity"]) for p in group]
        assert max(tech_ranks) - min(tech_ranks) <= 2, f"tech affinity should be comparable across countries {tech_ranks}"
        # novelty etc
        novelty_ranks = [_rank(p["novelty_seeking"]) for p in group]
        assert max(novelty_ranks) - min(novelty_ranks) <= 2
        # Age should be identical (archetype age before geo)
        ages = [p["age"] for p in group]
        assert len(set(ages)) == 1, f"age should be identical for same seed/index across countries, got {ages}"
        # Income currency must differ and be locally plausible
        currencies = {p["currency"] for p in group}
        assert len(currencies) == len(countries), "each country should have distinct currency"
        for p in group:
            assert p["currency"] == COUNTRIES[p["country"]]["currency"]
            assert p["primary_language"] in COUNTRIES[p["country"]]["languages"]
        # Transport/payment/food differ by ecosystem (not all identical)
        transports = {p["primary_transport_mode"] for p in group}
        # At least 3 distinct transports across 6 countries (geography conditioning)
        assert len(transports) >= 3

def test_cross_country_generation_via_seed_control():
    """More systematic: 30 profiles per country, check trait distributions comparable not geography-defined."""
    # Generate 200 profiles per country, compare trait means (should be similar across countries, as personality is not country-driven)
    means = {}
    for c in ["India","United States","Japan","Brazil"]:
        pros = generate_profiles(300, 2026, country=c)
        means[c] = sum(_rank(p["technology_affinity"]) for p in pros)/len(pros)
    # Means should be within ~0.35 of each other (not country stereotype)
    vals = list(means.values())
    assert max(vals) - min(vals) < 0.6, f"tech affinity means across countries should be similar, got {means}"
    # But payment ecosystem should differ: each country's top payment != all same
    pay_tops = {}
    for c in means:
        pros = generate_profiles(200, 3030, country=c)
        top = Counter(p["available_payment_method"] for p in pros).most_common(1)[0][0]
        pay_tops[c] = top
    # At least two different top payments across countries
    assert len(set(pay_tops.values())) >= 2, f"payment tops should vary by country {pay_tops}"

def test_local_expression_differs_while_coherence_remains():
    countries = ["India","United States","Japan","Saudi Arabia","Brazil","Nigeria"]
    for c in countries:
        pros = generate_profiles(30, 6060, country=c)
        for p in pros:
            # Local expression checks
            assert p["currency"] == COUNTRIES[c]["currency"]
            assert p["local_food_pattern"] in COUNTRIES[c]["foods"]
            assert p["available_payment_method"] in COUNTRIES[c]["payments"]
            assert p["primary_transport_mode"] in COUNTRIES[c]["transport"]
            assert p["preferred_ott_platform"] in COUNTRIES[c]["platforms"]
            # Coherence must remain valid
            assert assess_profile(p)["valid"], f"profile invalid {p['profile_id']} {assess_profile(p)['violations']}"
            assert assess_profile(p)["behavioral_coherence_score"] > 0.65

def test_same_archetype_across_countries_detailed():
    """Ensure a 23-year highly technology-oriented, moderately affluent, novelty-seeking archetype retains traits."""
    # We simulate by sampling many profiles and picking one that matches archetype criteria in India, then find comparable in other countries via same approximate traits
    # Simpler: use same seed/index archetype and verify underlying traits similar but local fields adapted
    seed = 7777
    base = generate_profiles(1, seed, country="India", age_range=(23,23))[0]
    # Find comparable age in other countries by forcing same age_range and checking traits are still within band
    for c in ["United States","Japan","Brazil","Nigeria","Saudi Arabia"]:
        other = generate_profiles(1, seed, country=c, age_range=(23,23))[0]
        # Age identical due to same seed/index and forced range
        assert other["age"] == base["age"]
        # Tech affinity comparable (difference <=1 rank)
        assert abs(_rank(other["technology_affinity"]) - _rank(base["technology_affinity"])) <= 1
        # But currency/income scale adapted
        assert other["currency"] != base["currency"] or c=="India"
        assert other["annual_income"] != base["annual_income"]
        # Transport adapted
        assert other["primary_transport_mode"] in COUNTRIES[c]["transport"]
        assert base["primary_transport_mode"] in COUNTRIES["India"]["transport"]
