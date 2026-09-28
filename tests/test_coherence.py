"""Coherence tests: life-stage, career/education, occupation, language, finance.

All relationships are probabilistic: tests assert distributional properties
and the continued possibility of unusual-but-plausible profiles, never
absolute rules.
"""
from collections import Counter

from app.generator import generate_profiles
from app.geography import COUNTRIES
from app.rules import assess_profile


def test_life_stage_considers_career_not_only_age():
    pros = generate_profiles(1200, 5001)
    seniors = [p for p in pros if p["career_level"] in ("Senior", "Leadership")
               and p["years_of_experience"] >= 8 and 25 <= p["age"] <= 32]
    assert seniors, "expected senior profiles in late-20s/early-30s sample"
    early_share = sum(1 for p in seniors if p["life_stage"] == "Early Career") / len(seniors)
    # Senior professionals should not routinely carry a contradicting label.
    assert early_share < 0.35, f"too many seniors labelled Early Career: {early_share:.2f}"
    # But it must remain possible (no hard boundary).
    assert any(p["life_stage"] == "Early Career" for p in pros if 23 <= p["age"] <= 29)


def test_age_experience_career_consistency():
    pros = generate_profiles(800, 5002)
    for p in pros:
        assert p["years_of_experience"] <= max(0, p["age"] - 16)
        assert assess_profile(p)["valid"]
    # Experience grows with age on average.
    young = [p["years_of_experience"] for p in pros if 23 <= p["age"] <= 29]
    older = [p["years_of_experience"] for p in pros if 40 <= p["age"] <= 52]
    assert sum(older) / len(older) > sum(young) / len(young)


def test_student_and_retired_stages_anchored():
    pros = generate_profiles(800, 5003)
    for p in pros:
        if p["employment_status"] in ("Student", "School student"):
            assert p["life_stage"] in ("Teenager", "University Student")
        if p["employment_status"] == "Retired":
            assert p["life_stage"] == "Retired"
        if p["life_stage"] == "Retired":
            assert p["employment_status"] == "Retired"


def test_education_industry_pathway_stays_plausible():
    pros = generate_profiles(1500, 5004, country="India")
    # Business education -> Healthcare industry -> admin/management function must exist.
    assert any(p["field_of_study"] == "Business" and p["industry"] == "Healthcare"
               for p in pros), "Business->Healthcare pathway should be reachable"
    # School education -> Leadership with long experience must exist (via training pathway).
    assert any(p["education_level"] == "School education"
               and p["career_level"] == "Leadership"
               and p["years_of_experience"] >= 10 for p in pros), \
        "School->Leadership via experience should remain possible"
    # Pathway marker explains non-traditional routes.
    school_leaders = [p for p in pros if p["education_level"] == "School education"
                      and p["career_level"] in ("Senior", "Leadership")]
    if school_leaders:
        marked = sum(1 for p in school_leaders
                     if p["professional_training"] != "No formal additional training")
        assert marked / len(school_leaders) > 0.5
    for p in pros:
        assert assess_profile(p)["valid"]


def test_occupation_job_function_specificity():
    pros = generate_profiles(600, 5005)
    working = [p for p in pros if p["employment_status"] not in ("Student", "School student", "Retired")]
    assert working
    for p in working:
        # job_function is specific, not a copy of industry; occupation keeps both tokens.
        assert p["job_function"] != p["industry"] or p["industry"] not in (
            "Technology", "Finance", "Healthcare", "Manufacturing", "Media")
        if p["career_level"] == "None":
            assert p["occupation"] == f"{p['industry']} professional"
        else:
            assert p["career_level"] in p["occupation"]
            assert p["industry"] in p["occupation"]
    health = [p["job_function"] for p in working if p["industry"] == "Healthcare"]
    assert len(set(health)) >= 2, "healthcare functions should vary across paths"


def test_language_geography_probabilistic():
    pros = generate_profiles(600, 5006, country="India")
    ctx = COUNTRIES["India"]
    for p in pros:
        assert p["primary_language"] in ctx["languages"]
        assert p["preferred_language"] in ctx["languages"]
        assert p["primary_language"] not in ("Female", "Male", "Non-binary")
        assert p["preferred_language"] not in ("Female", "Male", "Non-binary")
    # Context-aware: dominant/local languages lead overall, ...
    counts = Counter(p["primary_language"] for p in pros)
    assert counts["Hindi"] + counts["English"] > counts["Bengali"]
    # ... yet unusual migrant combinations remain valid.
    mumbai = [p for p in pros if p["city"] == "Mumbai"]
    assert mumbai, "expected Mumbai profiles in India sample"
    assert len({p["primary_language"] for p in pros}) >= 3
    # Same-seed determinism of language choice.
    assert [p["primary_language"] for p in pros] == [
        p["primary_language"] for p in generate_profiles(600, 5006, country="India")]


def test_financial_support_coherence():
    pros = generate_profiles(600, 5007)
    students = [p for p in pros if p["employment_status"] in ("Student", "School student")]
    assert students
    zero_income = [p for p in students if p["monthly_income"] == 0]
    assert zero_income
    # Family-supported students usually show non-zero spending ...
    supported = [p for p in zero_income if p["financial_support_source"] == "Family support"]
    assert supported
    assert sum(1 for p in supported if p["monthly_expenses"] > 0) / len(supported) > 0.5
    # ... but zero spending stays possible (probabilistic, not blanket).
    assert any(p["monthly_expenses"] == 0 for p in zero_income)
    for p in pros:
        res = assess_profile(p)
        assert res["valid"], res["violations"]
        assert p["monthly_savings"] >= 0
        if p["monthly_income"] > 0:
            assert p["monthly_savings"] <= p["monthly_income"]
