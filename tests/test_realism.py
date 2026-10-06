from app.generator import generate_profiles

RANK = {"Technology cautious": 1, "Technology practical": 2, "Technology comfortable": 3, "Technology enthusiastic": 4, "Technology leading": 5, "Health disengaged": 1, "Health aware": 2, "Health balanced": 3, "Health focused": 4, "Highly health focused": 5, "Never": 1, "Rarely": 2, "Occasionally": 3, "Frequently": 4, "Very frequently": 5}

def test_joint_persona_model_correlations():
    """Shared entertainment latents shape both the personality anchor and media
    choice: exploratory personas concentrate openness; anchors stay distinct."""
    profiles = generate_profiles(1500, 4242)
    trait_rank = {"Very low": 1, "Low": 2, "Moderate": 3, "High": 4, "Very high": 5}
    exploratory = [p for p in profiles if p["entertainment_persona"] in
                   ("Sci-Fi Enthusiast", "International Cinema Explorer", "Documentary Viewer")]
    mainstream = [p for p in profiles if p["entertainment_persona"] in
                  ("Family Entertainment Viewer", "Casual Viewer", "Mainstream Movie Lover")]
    assert exploratory and mainstream
    exploratory_open = sum(trait_rank[p["openness"]] for p in exploratory) / len(exploratory)
    mainstream_open = sum(trait_rank[p["openness"]] for p in mainstream) / len(mainstream)
    assert exploratory_open > mainstream_open + 0.05
    creative = [p for p in profiles if p["personality_name"] == "Creative"]
    practical = [p for p in profiles if p["personality_name"] == "Practical"]
    assert creative and practical
    creative_open = sum(trait_rank[p["openness"]] for p in creative) / len(creative)
    practical_open = sum(trait_rank[p["openness"]] for p in practical) / len(practical)
    assert creative_open > practical_open + 1.0


def test_directional_correlations():
    profiles = generate_profiles(1000, 999)
    junior = [p["annual_income"] for p in profiles if p["career_level"] in {"Early", "None"}]
    senior = [p["annual_income"] for p in profiles if p["career_level"] in {"Senior", "Leadership"}]
    assert senior and sum(senior) / len(senior) > sum(junior) / len(junior)
    high_tech = [RANK[p["technology_smartphone_usage_frequency_score"]] for p in profiles if RANK[p["technology_affinity"]] >= 4]
    low_tech = [RANK[p["technology_smartphone_usage_frequency_score"]] for p in profiles if RANK[p["technology_affinity"]] <= 2]
    assert sum(high_tech) / len(high_tech) > sum(low_tech) / len(low_tech)
    high_health = [RANK[p["wellness_fitness_usage_frequency_score"]] for p in profiles if RANK[p["health_orientation"]] >= 4]
    low_health = [RANK[p["wellness_fitness_usage_frequency_score"]] for p in profiles if RANK[p["health_orientation"]] <= 2]
    assert sum(high_health) / len(high_health) > sum(low_health) / len(low_health)
