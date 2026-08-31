from collections import Counter
import io
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.generator import generate_profiles
from app.schemas import PROFILE_COLUMNS, PERSONALITY_ARCHETYPES
from app.rules import assess_profile
from app.exports import export_bytes
from app.geography import COUNTRIES

client = TestClient(app)

def test_every_profile_contains_personality_name():
    p = generate_profiles(1, 7)[0]
    assert "personality_name" in p
    assert isinstance(p["personality_name"], str) and p["personality_name"].strip() != ""
    assert p["personality_name"] in PERSONALITY_ARCHETYPES

def test_personality_name_is_first_column():
    assert PROFILE_COLUMNS[0] == "personality_name"
    p = generate_profiles(1, 11)[0]
    assert list(p.keys())[0] == "personality_name"
    assert list(p.keys()) == list(PROFILE_COLUMNS)
    # CSV
    profiles = generate_profiles(3, 21)
    payload, _, _ = export_bytes(profiles, "csv")
    header = payload.decode("utf-8").splitlines()[0].split(",")
    assert header[0] == "personality_name"
    # Parquet
    payload2, _, _ = export_bytes(profiles, "parquet")
    df = pd.read_parquet(io.BytesIO(payload2))
    assert list(df.columns)[0] == "personality_name"
    # API JSON order
    resp = client.post("/generate", json={"count": 1, "seed": 21})
    assert resp.status_code == 200
    profile = resp.json()["profiles"][0]
    assert list(profile.keys())[0] == "personality_name"

def test_same_seed_same_personality_name():
    a = generate_profiles(5, 123)
    b = generate_profiles(5, 123)
    for pa, pb in zip(a, b):
        assert pa["personality_name"] == pb["personality_name"]
        assert pa["personality_name"] in PERSONALITY_ARCHETYPES

def test_profiles_have_different_names():
    pros = generate_profiles(200, 999)
    names = {p["personality_name"] for p in pros}
    assert len(names) >= 3, f"expected diversity, got {names}"
    # also within same country variation
    pros_in = generate_profiles(100, 555, country="India")
    assert len({p["personality_name"] for p in pros_in}) >= 2

def test_personality_name_corresponds_to_traits():
    # high analytical traits should map to Analytical, etc. Test consistency via validation helper
    pros = generate_profiles(50, 1001)
    for p in pros:
        # validation already checks consistency, but explicitly verify expected derivation matches
        res = assess_profile(p)
        assert res["valid"], f"violations {res['violations']}"
        # changing relevant traits should be capable of changing name: we test by sampling extremes
    # ensure each archetype appears at least once in large sample (except perhaps rare Balanced)
    big = generate_profiles(800, 2026)
    counts = Counter(p["personality_name"] for p in big)
    # All archetypes should be reachable? At least 5 distinct
    assert len(counts) >= 5

def test_traits_change_can_change_name():
    # Direct test of mapping sensitivity: craft trait vectors
    from app.generator import _derive_personality_name
    base = {k: 0.5 for k in ("openness","conscientiousness","extraversion","agreeableness","risk_tolerance","novelty_seeking","social_orientation","health_orientation","luxury_orientation","planning_orientation","cultural_openness","environmental_awareness","technology_affinity","price_sensitivity")}
    name_balanced = _derive_personality_name(base)
    assert name_balanced == "Balanced"
    high_social = dict(base); high_social.update({"extraversion":0.9,"social_orientation":0.9,"agreeableness":0.85,"cultural_openness":0.8})
    assert _derive_personality_name(high_social) == "Social"
    high_adv = dict(base); high_adv.update({"novelty_seeking":0.95,"openness":0.9,"risk_tolerance":0.85,"extraversion":0.8})
    assert _derive_personality_name(high_adv) == "Adventurous"
    high_disc = dict(base); high_disc.update({"conscientiousness":0.95,"planning_orientation":0.9,"risk_tolerance":0.15,"health_orientation":0.7})
    assert _derive_personality_name(high_disc) == "Disciplined"

def test_country_does_not_directly_determine_name():
    # Same seed across 6 countries => same personality_name (traits before geography)
    seed = 777
    names = []
    for c in ("India","United States","Japan","Saudi Arabia","Brazil","Nigeria"):
        p = generate_profiles(1, seed, country=c)[0]
        names.append(p["personality_name"])
        # also check currency differs
        assert p["currency"] == COUNTRIES[c]["currency"]
    assert len(set(names)) == 1, f"same seed should give same archetype across countries, got {names}"

def test_comparable_archetype_across_countries():
    countries = ["India","United States","Japan","Saudi Arabia","Brazil","Nigeria"]
    for idx in range(1, 6):
        base_seed = 4000 + idx
        group = [generate_profiles(1, base_seed, country=c)[0] for c in countries]
        base_name = group[0]["personality_name"]
        for p in group:
            assert p["personality_name"] == base_name, f"archetype mismatch {base_name} vs {p['personality_name']} for idx {idx}"
            # environmental fields differ
            assert p["primary_transport_mode"] in COUNTRIES[p["country"]]["transport"]
        # ensure not all transports identical (geo expression varies)
        assert len({p["primary_transport_mode"] for p in group}) >= 2

def test_still_over_400_columns():
    assert len(PROFILE_COLUMNS) >= 400
    assert len(PROFILE_COLUMNS) == len(set(PROFILE_COLUMNS))
    p = generate_profiles(1, 42)[0]
    assert len(p) >= 400
    assert set(p.keys()) == set(PROFILE_COLUMNS)
    assert p["personality_name"] in PERSONALITY_ARCHETYPES
    assert list(p.keys())[0] == "personality_name"

def test_validation_rejects_bad_personality():
    p = generate_profiles(1, 1)[0]
    bad = dict(p)
    bad["personality_name"] = "NotAnArchetype"
    res = assess_profile(bad)
    assert not res["valid"]
    assert any(v["rule"] == "personality_name_archetype" for v in res["violations"])
    bad2 = dict(p)
    bad2["personality_name"] = ""
    assert not assess_profile(bad2)["valid"]
    # inconsistent name
    bad3 = dict(p)
    # flip to different archetype
    other = next(x for x in PERSONALITY_ARCHETYPES if x != p["personality_name"])
    bad3["personality_name"] = other
    # should be detected as inconsistent unless other coincidentally matches traits (rare)
    res3 = assess_profile(bad3)
    # if other happens to be expected due to ambiguous traits, allow pass, otherwise should fail
    from app.rules import _expected_personality_name
    expected = _expected_personality_name(p)
    if other != expected:
        assert not res3["valid"]
