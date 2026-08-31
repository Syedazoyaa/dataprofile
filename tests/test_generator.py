from app.generator import generate_profiles
from app.geography import COUNTRIES
from app.schemas import PROFILE_COLUMNS

def test_schema_is_meaningful_and_complete():
    assert len(PROFILE_COLUMNS) >= 500
    assert len(PROFILE_COLUMNS) == len(set(PROFILE_COLUMNS))
    assert not any(name.startswith(("feature_", "random_value_", "dummy_")) for name in PROFILE_COLUMNS)
    profile = generate_profiles(1, 7)[0]
    assert set(profile) == set(PROFILE_COLUMNS)
    assert profile["commerce_electronics_interest_score"] in {"Not interested", "Slightly interested", "Moderately interested", "Interested", "Highly interested"}
    assert profile["technology_smartphone_usage_frequency_score"] in {"Never", "Rarely", "Occasionally", "Frequently", "Very frequently"}
    float_columns = [name for name, value in profile.items() if isinstance(value, float)]
    assert set(float_columns) <= {"savings_rate", "daily_screen_time_hours", "streaming_hours_weekly"}

def test_determinism_uniqueness_and_constraints():
    first = generate_profiles(100, 42)
    assert first == generate_profiles(100, 42)
    assert len({p["profile_id"] for p in first}) == 100
    for profile in first:
        assert 16 <= profile["age"] <= 78
        assert profile["monthly_savings"] <= profile["monthly_income"]
        assert profile["currency"] == COUNTRIES[profile["country"]]["currency"]
        assert profile["years_of_experience"] <= profile["age"] - 16
