def validate_profile(profile: dict) -> None:
    """Explicit generation-time constraints; never use assert for validation."""
    required = {"profile_id", "age", "life_stage", "annual_income", "monthly_income", "monthly_expenses", "monthly_savings"}
    missing = required - profile.keys()
    if missing: raise ValueError(f"Profile is missing required fields: {sorted(missing)}")
    if not 16 <= profile["age"] <= 78: raise ValueError("Age is outside the supported range")
    if profile["monthly_savings"] < 0 or profile["monthly_savings"] > profile["monthly_income"]: raise ValueError("Savings are inconsistent with monthly income")
    if profile["life_stage"] == "Teenager" and profile["employment_status"] not in {"School student", "Student"}: raise ValueError("Teenager employment is inconsistent")
    if profile["life_stage"] == "University Student" and profile["career_level"] != "None": raise ValueError("Student career level is inconsistent")
    if profile["life_stage"] == "Retired" and profile["employment_status"] != "Retired": raise ValueError("Retired life stage is inconsistent")
    if profile["age"] < 20 and profile["number_of_children"] > 0: raise ValueError("Child count is implausible for age")
    if profile["years_of_experience"] > max(0, profile["age"] - 16): raise ValueError("Experience exceeds age-derived maximum")
