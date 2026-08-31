from app.generator import generate_profiles
from app.geography import COUNTRIES
from app.rules import assess_profile

def test_geographic_context_controls_profile_fields():
    profiles = []
    for country in ("India", "Japan", "Saudi Arabia", "United States", "Brazil", "Nigeria"):
        profiles.extend(generate_profiles(30, 121, country=country))
    for profile in profiles:
        context = COUNTRIES[profile["country"]]
        assert profile["currency"] == context["currency"]
        assert profile["primary_language"] in context["languages"]
        assert profile["available_payment_method"] in context["payments"]
        assert profile["primary_transport_mode"] in context["transport"]
        assert assess_profile(profile)["valid"]

def test_global_mode_is_seeded_and_weighted_not_single_country():
    first = generate_profiles(200, 987, country_mode="global")
    assert first == generate_profiles(200, 987, country_mode="global")
    countries = {profile["country"] for profile in first}
    assert len(countries) >= 4
