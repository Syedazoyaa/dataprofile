"""Chart-ready analytics over generated (or filtered) synthetic populations.

Population -> compute_analytics -> structured JSON -> frontend charts.
The backend never renders images; it returns categorical distributions as
[{label, count}] lists, KPI numbers, capped scatter samples and documented
correlation statistics. All figures describe the model-generated synthetic
population, never real-world populations. No causality is claimed anywhere.

Currency honesty: raw income/expense values are NEVER pooled across
currencies. Cross-country views use the currency-neutral income_band plus
explicitly labelled per-currency statistics.
"""

from statistics import mean, median
from collections import Counter

from .comparison import AGE_BINS
from .segmentation import SEGMENT_DEFINITIONS, aggregate_purchase_intent, classify_profile

SYNTHETIC_NOTE = ("Figures describe the model-generated synthetic population, "
                  "not empirical claims about real populations. Correlations "
                  "are associations within synthetic data, not causal effects.")

# Canonical vocabularies for the data-quality invalid-category check.
VALID_CATEGORIES = {
    "gender": {"Female", "Male", "Non-binary"},
    "education_level": {"School education", "Professional diploma", "Undergraduate", "Postgraduate"},
    "employment_status": {"Employed full-time", "Employed part-time", "Self-employed",
                          "Student", "School student", "Retired"},
    "career_level": {"None", "Early", "Mid-level", "Senior", "Leadership", "Former professional"},
    "income_band": {"Limited", "Modest", "Comfortable", "Affluent"},
    "life_stage": {"Teenager", "University Student", "Early Career", "Established Professional",
                   "Mid-Career", "Senior Professional", "Retired"},
}

_BEHAVIOUR_KEYS = (
    "research_before_purchase",
    "comparison_behavior",
    "price_sensitivity",
    "brand_loyalty",
    "decision_speed",
    "planning_behavior",
    "impulse_buying",
    "discount_sensitivity",
    "information_seeking",
)

_INTENT_RANK = {"Very unlikely": 1, "Unlikely": 2, "Considering": 3, "Likely": 4, "Very likely": 5}
_PRICE_RANK = {"Price insensitive": 1, "Slightly price aware": 2, "Price conscious": 3,
               "Price sensitive": 4, "Highly price sensitive": 5}
_LEVEL_RANK = {"Low": 1, "Moderate": 2, "High": 3}

_MAX_SCATTER_POINTS = 500
_TOP_N_GEO = 15


def _dist(profiles, key):
    """Bar-chart-ready [{label, count}] sorted by count desc, then label."""
    counts: dict = {}
    for profile in profiles:
        label = profile.get(key)
        label = str(label) if label is not None else "Unknown"
        counts[label] = counts.get(label, 0) + 1
    return [{"label": label, "count": counts[label]}
            for label in sorted(counts, key=lambda l: (-counts[l], l))]


def _age_bin(age):
    try:
        age = int(age)
    except (TypeError, ValueError):
        return "Unknown"
    for label, low, high in AGE_BINS:
        if low <= age <= high:
            return label
    return "Unknown"


def _stats(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "min": None, "average": None, "median": None, "max": None}
    return {"n": len(values), "min": values[0],
            "average": round(mean(values), 2), "median": median(values), "max": values[-1]}


def _ranks(values):
    """Average-tie ranks (1-based) for Spearman correlation; pure stdlib."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    """Spearman rank correlation; returns None when undefined (n<3 or constant)."""
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rx, ry = _ranks(list(xs)), _ranks(list(ys))
    n = len(pairs)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    if not den:
        return None
    return round(num / den, 3)


def _numeric_relation(profiles, x_fn, y_fn):
    """Scatter sample (deterministic first-N) + Spearman correlation."""
    pairs = [(x_fn(p), y_fn(p)) for p in profiles]
    pairs = [(x, y) for x, y in pairs if x is not None and y is not None]
    return {"sample_size": len(pairs),
            "points": [{"x": x, "y": y} for x, y in pairs[:_MAX_SCATTER_POINTS]],
            "points_truncated": len(pairs) > _MAX_SCATTER_POINTS,
            "correlation": spearman([x for x, _ in pairs], [y for _, y in pairs]),
            "method": "spearman"}


def _grouped_mean(profiles, group_key, rank_fn):
    groups: dict = {}
    for profile in profiles:
        rank = rank_fn(profile)
        if rank is None:
            continue
        label = str(profile.get(group_key)) if profile.get(group_key) is not None else "Unknown"
        groups.setdefault(label, []).append(rank)
    return [{"label": label,
             "count": len(vals),
             "mean_rank": round(mean(vals), 3)}
            for label, vals in sorted(groups.items())]


def _research_rank(profile):
    # Core research_before_purchase is a Low/Moderate/High level (five-level
    # research labels live only on per-topic research_intensity_score fields).
    return _LEVEL_RANK.get(profile.get("research_before_purchase"))


def _intent_rank(profile):
    return _INTENT_RANK.get(aggregate_purchase_intent(profile))


def _overview(profiles, seg_names=None):
    n = len(profiles)
    ages = [p["age"] for p in profiles if isinstance(p.get("age"), (int, float))]
    employed = sum(1 for p in profiles if str(p.get("employment_status", "")).startswith("Employed"))
    segments = seg_names if seg_names is not None else (
        [classify_profile(p)["segment_name"] for p in profiles] if n else [])
    educations = [p.get("education_level") for p in profiles if p.get("education_level")]
    by_currency: dict = {}
    for p in profiles:
        if isinstance(p.get("annual_income"), (int, float)):
            by_currency.setdefault(str(p.get("currency", "Unknown")), []).append(p["annual_income"])
    main_currency = max(by_currency, key=lambda c: len(by_currency[c])) if by_currency else None
    main_stats = _stats(by_currency[main_currency]) if main_currency else _stats([])
    if n == 0:
        return {"total_profiles": 0, "average_age": None, "median_age": None,
                "min_age": None, "max_age": None, "average_income": None,
                "median_income": None, "income_currency": None,
                "employment_rate": None, "employment_distribution": [],
                "dominant_education": None, "dominant_segment": None,
                "country_count": 0, "city_count": 0}
    return {
        "total_profiles": n,
        "average_age": round(mean(ages), 2) if ages else None,
        "median_age": median(sorted(ages)) if ages else None,
        "min_age": min(ages) if ages else None,
        "max_age": max(ages) if ages else None,
        # Income headline figures always refer to the largest currency group.
        "average_income": main_stats["average"],
        "median_income": main_stats["median"],
        "income_currency": main_currency,
        "employment_rate": round(employed / n, 4),
        "employment_distribution": _dist(profiles, "employment_status"),
        "dominant_education": max(set(educations), key=educations.count) if educations else None,
        "dominant_segment": max(set(segments), key=segments.count),
        "country_count": len({p.get("country") for p in profiles}),
        "city_count": len({p.get("city") for p in profiles}),
    }


def _financial(profiles):
    by_currency: dict = {}
    for p in profiles:
        if isinstance(p.get("annual_income"), (int, float)):
            by_currency.setdefault(str(p.get("currency", "Unknown")), []).append(p["annual_income"])
    expense_by_currency: dict = {}
    for p in profiles:
        if isinstance(p.get("monthly_expenses"), (int, float)):
            expense_by_currency.setdefault(str(p.get("currency", "Unknown")), []).append(p["monthly_expenses"])
    ratios = []
    for p in profiles:
        income = p.get("monthly_income")
        if isinstance(income, (int, float)) and income > 0 and isinstance(
                p.get("monthly_expenses"), (int, float)):
            ratios.append(p["monthly_expenses"] / income)
    ratio_bins = (("<40%", 0, 0.40), ("40-60%", 0.40, 0.60), ("60-80%", 0.60, 0.80), (">80%", 0.80, float("inf")))
    ratio_counts = {"<40%": 0, "40-60%": 0, "60-80%": 0, ">80%": 0}
    for r in ratios:
        if r < 0.40:
            ratio_counts["<40%"] += 1
        elif r < 0.60:
            ratio_counts["40-60%"] += 1
        elif r < 0.80:
            ratio_counts["60-80%"] += 1
        else:
            ratio_counts[">80%"] += 1
    ratio_dist = [{"label": label, "count": ratio_counts[label]}
                  for label, _, _ in ratio_bins]
    # Currency with the most profiles anchors the scatter/correlation view.
    anchor = max(by_currency, key=lambda c: len(by_currency[c])) if by_currency else None
    anchor_profiles = [p for p in profiles if str(p.get("currency", "Unknown")) == anchor] if anchor else []
    scatter = _numeric_relation(
        anchor_profiles,
        lambda p: p.get("monthly_income") if isinstance(p.get("monthly_income"), (int, float)) else None,
        lambda p: p.get("monthly_expenses") if isinstance(p.get("monthly_expenses"), (int, float)) else None)
    scatter["currency"] = anchor
    return {
        "income_bands": _dist(profiles, "income_band"),
        "income_by_currency": {cur: _stats(vals) for cur, vals in sorted(by_currency.items())},
        "expense_by_currency": {cur: _stats(vals) for cur, vals in sorted(expense_by_currency.items())},
        "expense_to_income_ratio": ratio_dist,
        "income_vs_expenses": scatter,
        "note": ("Raw income/expense values are never pooled across currencies; "
                 "use income_bands or per-currency statistics for cross-country views."),
    }


def _behavioural(profiles, intent_labels=None):
    out = {}
    for key in _BEHAVIOUR_KEYS:
        out[key] = _dist(profiles, key)
    if intent_labels is None:
        intent_labels = [aggregate_purchase_intent(p) for p in profiles]
    counts: dict = {}
    for label in intent_labels:
        counts[label] = counts.get(label, 0) + 1
    out["purchase_intent"] = [{"label": label, "count": counts[label]}
                              for label in sorted(counts, key=lambda l: (-counts[l], l))]
    out["risk_tolerance"] = _dist(profiles, "financial_risk_tolerance")
    return out


def _relationships(profiles, intent_ranks=None):
    if intent_ranks is None:
        intent_ranks = [_intent_rank(p) for p in profiles]
    # Per-profile rank lists: each derived value is scanned exactly once.
    research_ranks = [_LEVEL_RANK.get(p.get("research_before_purchase")) for p in profiles]
    price_ranks = [_PRICE_RANK.get(p.get("price_sensitivity")) for p in profiles]
    brand_ranks = [_LEVEL_RANK.get(p.get("brand_loyalty")) for p in profiles]
    comparison_ranks = [_LEVEL_RANK.get(p.get("comparison_behavior")) for p in profiles]
    decision_ranks = [_LEVEL_RANK.get(p.get("decision_speed")) for p in profiles]
    ages = [p.get("age") if isinstance(p.get("age"), (int, float)) else None for p in profiles]
    incomes = [p.get("annual_income") if isinstance(p.get("annual_income"), (int, float)) else None
               for p in profiles]
    exps = [p.get("years_of_experience")
            if isinstance(p.get("years_of_experience"), (int, float)) else None for p in profiles]

    def _pair(xs, ys):
        pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        return {"sample_size": len(pairs),
                "points": [{"x": x, "y": y} for x, y in pairs[:_MAX_SCATTER_POINTS]],
                "points_truncated": len(pairs) > _MAX_SCATTER_POINTS,
                "correlation": spearman([x for x, _ in pairs], [y for _, y in pairs]),
                "method": "spearman"}

    return {
        "age_vs_income": _pair(ages, incomes),
        "experience_vs_income": _pair(exps, incomes),
        "research_vs_purchase_intent": _pair(research_ranks, intent_ranks),
        "price_vs_purchase_intent": _pair(price_ranks, intent_ranks),
        "brand_vs_purchase_intent": _pair(brand_ranks, intent_ranks),
        "comparison_vs_decision_speed": _pair(comparison_ranks, decision_ranks),
        "education_vs_research": _grouped_mean(profiles, "education_level", _research_rank),
        "career_vs_purchase_intent": _grouped_mean(profiles, "career_level", _intent_rank),
    }


def _data_quality(profiles, seg_ids=None):
    """Transparent consistency audit. Score formula (documented, not 'accuracy'):

    score = 100 * (1 - failed_checks / (n_profiles * 7)); one failure point per
    profile per failed check across the 7 consistency checks below.
    """
    n = len(profiles)
    result = {"total_profiles": n, "missing_values": {}, "duplicate_ids": 0,
              "invalid_categories": {}, "unexpected_nulls": 0,
              "inconsistencies": {}, "segment_coverage": {}, "country_coverage": [],
              "checks_per_profile": 7, "failed_checks": 0,
              "data_quality_score": None,
              "formula": ("100 * (1 - failed_checks / (total_profiles * 7)); "
                          "a synthetic-data consistency score, not accuracy")}
    if n == 0:
        return result
    core_keys = ("age", "gender", "country", "city", "education_level", "employment_status",
                 "career_level", "annual_income", "monthly_income", "monthly_expenses",
                 "primary_language", "life_stage")
    missing: dict = {}
    nulls = 0
    for p in profiles:
        for key in core_keys:
            if key not in p or p[key] is None:
                missing[key] = missing.get(key, 0) + 1
                nulls += 1
    result["missing_values"] = missing
    result["unexpected_nulls"] = nulls
    ids = [p.get("profile_id") for p in profiles]
    result["duplicate_ids"] = len(ids) - len(set(ids))
    dup_ids = {i for i, c in Counter(ids).items() if c > 1}
    invalid: dict = {}
    for key, valid in VALID_CATEGORIES.items():
        bad = sum(1 for p in profiles if p.get(key) not in valid)
        if bad:
            invalid[key] = bad
    result["invalid_categories"] = invalid

    def inconsistent_age_exp(p):
        return isinstance(p.get("years_of_experience"), (int, float)) and isinstance(
            p.get("age"), (int, float)) and p["years_of_experience"] > max(0, p["age"] - 16)

    def inconsistent_career_stage(p):
        return ((p.get("life_stage") == "Retired" and p.get("employment_status") != "Retired")
                or (p.get("life_stage") == "University Student"
                    and p.get("career_level") not in ("None",)))

    def inconsistent_income_expense(p):
        income, savings = p.get("monthly_income"), p.get("monthly_savings")
        if not isinstance(income, (int, float)) or not isinstance(savings, (int, float)):
            return True
        if income == 0:
            return savings != 0
        return savings < 0 or savings > income

    def gender_language_issue(p):
        return (p.get("primary_language") in ("Female", "Male", "Non-binary")
                or p.get("preferred_language") in ("Female", "Male", "Non-binary"))

    checks = {
        "age_experience": inconsistent_age_exp,
        "career_life_stage": inconsistent_career_stage,
        "income_expense": inconsistent_income_expense,
        "gender_language_mapping": gender_language_issue,
        "missing_core_field": lambda p: any(k not in p or p[k] is None for k in core_keys),
        "invalid_category": lambda p: any(p.get(k) not in v for k, v in VALID_CATEGORIES.items()),
        "duplicate_id": lambda p: p.get("profile_id") in dup_ids,
    }
    inconsistencies = {}
    failed = 0
    for name, fn in checks.items():
        count = sum(1 for p in profiles if fn(p))
        inconsistencies[name] = count
        failed += count
    result["inconsistencies"] = inconsistencies
    result["failed_checks"] = failed
    result["data_quality_score"] = round(100 * (1 - failed / (n * 7)), 2)
    seg_counts: dict = {}
    if seg_ids is None:
        seg_ids = [classify_profile(p)["segment_id"] for p in profiles]
    for seg in seg_ids:
        seg_counts[seg] = seg_counts.get(seg, 0) + 1
    result["segment_coverage"] = {
        d["segment_id"]: {"segment_name": d["segment_name"],
                          "count": seg_counts.get(d["segment_id"], 0),
                          "covered": d["segment_id"] in seg_counts}
        for d in SEGMENT_DEFINITIONS}
    country_counts: dict = {}
    for p in profiles:
        country_counts[str(p.get("country"))] = country_counts.get(str(p.get("country")), 0) + 1
    result["country_coverage"] = [{"label": c, "count": n_}
                                  for c, n_ in sorted(country_counts.items(),
                                                      key=lambda kv: (-kv[1], kv[0]))]
    return result


def _segments(profiles):
    from .segmentation import summarize_segments
    return summarize_segments(profiles)


def compute_analytics(profiles: list[dict]) -> dict:
    """Single-pass-friendly aggregation over an in-memory population list.

    Expensive derived values (segment assignment, purchase-intent aggregate)
    are computed once per profile up front and shared across sections.
    """
    profiles = list(profiles)
    seg_results = [classify_profile(p) for p in profiles]
    seg_ids = [r["segment_id"] for r in seg_results]
    seg_names = [r["segment_name"] for r in seg_results]
    intent_labels = [aggregate_purchase_intent(p) for p in profiles]
    intent_ranks = [_INTENT_RANK.get(label) for label in intent_labels]
    age_dist = [{"label": label, "count": 0} for label, _, _ in AGE_BINS]
    age_counts = {label: 0 for label, _, _ in AGE_BINS}
    for p in profiles:
        age_counts[_age_bin(p.get("age"))] += 1
    for entry in age_dist:
        entry["count"] = age_counts[entry["label"]]
    exp_bins = (("0-2 yrs", 0, 2), ("3-5 yrs", 3, 5), ("6-10 yrs", 6, 10),
                ("11-20 yrs", 11, 20), ("20+ yrs", 21, 10 ** 9))
    exp_counts = {label: 0 for label, _, _ in exp_bins}
    for p in profiles:
        exp = p.get("years_of_experience")
        for label, low, high in exp_bins:
            if isinstance(exp, (int, float)) and low <= exp <= high:
                exp_counts[label] += 1
                break
    geo_country = _dist(profiles, "country")
    return {
        "overview": _overview(profiles, seg_names),
        "demographics": {
            "age_distribution": age_dist,
            "gender_distribution": _dist(profiles, "gender"),
            "education_distribution": _dist(profiles, "education_level"),
            "employment_distribution": _dist(profiles, "employment_status"),
            "career_level_distribution": _dist(profiles, "career_level"),
            "experience_distribution": [{"label": l, "count": exp_counts[l]}
                                        for l, _, _ in exp_bins],
        },
        "geography": {
            "country_distribution": geo_country,
            "state_distribution": _dist(profiles, "state")[:_TOP_N_GEO],
            "city_distribution": _dist(profiles, "city")[:_TOP_N_GEO],
        },
        "financial": _financial(profiles),
        "behavioural": _behavioural(profiles, intent_labels),
        "segments": _segments(profiles),
        "relationships": _relationships(profiles, intent_ranks),
        "data_quality": _data_quality(profiles, seg_ids),
        "note": SYNTHETIC_NOTE,
    }
