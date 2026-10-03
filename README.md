# DataProfile API

A stateless FastAPI service that creates deterministic, correlated synthetic global consumer profiles. It has no authentication, accounts, jobs, database, or generated-file storage.

## Run

```powershell
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port $env:PORT
```

For local development use `uvicorn app.main:app --reload`.

## API

- `GET /health` — service status and schema version
- `GET /personas` — valid media personas and supported languages
- `GET /countries` — canonical 193-country registry with coverage levels
- `GET /segments/definitions` — behavioural segment catalogue
- `POST /generate` — generate profiles or directly download an export
- `POST /segments` — generate and classify into behavioural segments
- `POST /filter` — generate then filter (demographic/behavioural/segment/country)
- `POST /compare` — compare two or more labelled populations
- `POST /analytics` — chart-ready dashboard data for a (filtered) population

```json
{"count": 100, "seed": 12345, "country_mode": "specific", "country": "Japan", "age_range": [24, 45], "format": "json"}
```

`format` accepts `json`, `csv`, or `parquet`. JSON returns metadata and `profiles`; CSV and Parquet return only the requested in-memory download. No files are created on disk. `country_mode` accepts `specific` (the backwards-compatible default, `India`), `global`, `continent`, `region`/`subregion`. An optional `countries` list selects a multi-country population (per-profile country picked with registry weights); a single-element list behaves like `country`. Country names and ISO 3166-1 alpha-2/alpha-3 codes are accepted anywhere a country is given.

`view` (`full` default, `summary`) selects the complete canonical attribute set or the centrally defined core set (`CORE_PROFILE_FIELDS` in `app/schemas.py`). `scope` (`bulk` default, `individual`) with optional `profile_index` (1-based, default 1) downloads one selected person instead of the whole set. Filenames: `raven_profile_<id>.json`, `raven_profiles_summary.csv`, `raven_profiles_full_<N>.csv` where `N` is the canonical count from the registry (never hardcoded).

## Schema and realism

Schema version `1.1` defines the canonical attribute registry (`PROFILE_COLUMNS` in `app/schemas.py`; core vs full via `CORE_PROFILE_FIELDS`). Canonical count is currently **625**: 611 original + `professional_training` + `financial_support_source` (v1.1) + 12 derived experience attributes (`profile_summary`, `social_disposition`, `review_influence`, interactive/social/ad engagement, 7 social-media-personality attributes). Counts are asserted by `tests/test_profile_completeness.py` (missing = unexpected = duplicates = 0); any legitimate change must update the registry, never pad it.

Profiles use a profile-specific hash-derived random stream, so the same seed, request configuration, profile index, and generator version always produce the same record. Latent traits (technology affinity, price sensitivity, health orientation, cultural openness, planning orientation, and others) combine with age, career, income, family, and location to produce correlated observables. Behavioral propensities are returned as clear five-level strings—not opaque floats—such as `Not interested` through `Highly interested`, or `Never` through `Very frequently`. Only genuinely continuous quantities (screen time, streaming hours, and savings rate) remain floats.

## Geographic model and validation

`app/geography_world.py` is the canonical registry of 193 countries (ISO 3166-1 alpha-2/alpha-3/numeric, continent, subregion, nationality, currency, languages, places, industries, payments, transport, foods, religions, weights). `app/geography.py` exposes it via `country_registry()`, `resolve_country_name()` (one shared name/code resolver for generation, filtering, analytics and validation) and `get_context()`, which conditions city, currency, language pool, income scale, industries and ecosystems **before** traits and income are derived — a selected country shapes the profile; it never overwrites a global one. Generators contain no country-specific branches. `GET /countries` serves the registry for frontend dropdowns.

Coverage levels (see `DEEP_COVERAGE`): `deep` — India, United States, United Kingdom, Japan, Saudi Arabia, Brazil, Nigeria (curated contexts plus city-language affinity data); `standard` — the other 186 countries (real registry data, probabilistic generation, no curated tuning); `fallback` — per-field default paths (generic job functions, generic language weighting, subregion/global fallbacks), not a country tier.

`app/rules.py` returns structured validation violations and a coherence score derived from those checks. It verifies lifecycle, finance, country/currency, language, payment, transport, and food constraints before a profile is returned.

These country distributions and income scales are explicit modeled assumptions for behavioral simulation, not claims of empirical representativeness. No external network calls occur at generation time; future calibration can replace context values with sourced public statistics.

## Test

```powershell
pytest -q
```

## Profile coherence (schema 1.1)

Relationships are probabilistic plausibility models, never rigid rules. Unusual but realistic profiles remain possible.

- **Life stage** (`app/coherence.py::resolve_life_stage`) reconciles the age anchor with years of experience, career level and employment status. A senior professional with 8+ years of experience is usually labelled `Established Professional` or higher rather than `Early Career`, but the early label keeps a small non-zero probability. Student/retired anchors are unchanged.
- **Career pathway**: new `professional_training` column (e.g. `Professional certification`, `Vocational training`, `On-the-job advancement`, `Management certification`, `No formal additional training`) explains non-traditional routes such as `School education` + `Leadership` via long experience. No education gate is imposed on any career.
- **Occupation specificity**: `job_function` now holds a specific function within the industry (e.g. `Healthcare administration`, `Clinical care`, `Medical research`) tilted — not dictated — by field of study; `occupation` keeps the `CareerLevel Industry Title` form (e.g. `Senior Healthcare Administrator`) for backward compatibility.
- **Language geography**: `choose_language` boosts locally dominant languages where known (Hyderabad, Bengaluru, Mumbai affinities) with a generic dominant-first fallback for all other countries, plus an 8% migration draw so combinations such as `Mumbai + Tamil` stay valid. A validation guard ensures gender values can never appear in language fields.
- **Finance**: new `financial_support_source` column (`Family support`, `Scholarship/stipend`, `Self-funded`, `Pension/savings`, `None`). Zero personal income no longer implies zero spending: supported students usually show scaled non-zero expenses with zero savings; validation accepts this combination.

## Behavioural segmentation

`app/segmentation.py` assigns every profile to exactly one segment of the **generated synthetic population** (not a claim about real customers) via deterministic scoring over existing behavioural attributes — no ML dependencies:

| segment_id | segment_name | Defining traits |
|---|---|---|
| `deliberate_researcher` | Deliberate Researcher | High research/comparison/analytical, slow decisions, low impulse |
| `price_conscious_evaluator` | Price-Conscious Evaluator | High price/discount sensitivity, low premium preference |
| `brand_loyal_buyer` | Brand-Loyal Buyer | High brand loyalty/trust, recommendation dependence |
| `impulse_oriented_buyer` | Impulse-Oriented Buyer | High impulse/fast decisions, low planning/research |
| `balanced_mixed` | Balanced/Mixed Behaviour | Mostly Moderate behaviours, no extreme tendency |

```json
{"generation": {"count": 200, "seed": 42, "country": "India"}}
```

`POST /segments` returns `{total_profiles, segments: [{segment_id, segment_name, description, profile_count, percentage, defining_characteristics}], profiles}` where each profile carries derived `behavioural_segment` / `behavioural_segment_name` keys. `GET /segments/definitions` returns the segment catalogue.

## Filtering

`POST /filter` generates a population from `generation` (same fields as `/generate`) and filters it without touching generation dependencies:

```json
{"generation": {"count": 500, "seed": 1, "country": "India"},
 "filters": {"age_min": 25, "age_max": 35, "price_sensitivity": "Highly price sensitive",
             "behavioural_segment": "deliberate_researcher"}}
```

Supported filters: `age_min`/`age_max`, `gender`, `country` (single value or list with OR semantics, e.g. `{"country": ["IN", "SA", "AE"]}`), `education`, `employment_status`, `career_level`, `income_band`, `research_intensity`, `comparison_behaviour`, `purchase_intent` (median of commerce purchase-intent scores), `price_sensitivity`, `brand_loyalty`, `decision_speed`, `planning_behaviour`, `impulse_buying`, `behavioural_segment`. Invalid values return `422` with the valid options; empty matches return `matched_count: 0` (not an error). Filter logic lives in `app/filtering.py::apply_filters` (`FILTER_REGISTRY` extends it without endpoint changes).

## Population comparison

`POST /compare` accepts two or more labelled populations of any size and returns normalised distributions:

```json
{"populations": [{"label": "India", "generation": {"count": 5000, "seed": 7, "country": "India"}},
                 {"label": "Saudi Arabia", "generation": {"count": 5000, "seed": 7, "country": "Saudi Arabia"}}]}
```

Response: `{populations: {label: {n}}, demographics: [...], behavioural: [...], segments: {...}}`. Each dimension entry is `{dimension, categories, populations: {label: {n, counts, percentages}}}` covering age/gender/education/employment/career/income, eight behavioural attributes, and segment distribution. Logic lives in `app/comparison.py::compare_populations`. Comparisons are descriptive only; no causal claims are made.

## Analytics for frontend graphs

`POST /analytics` accepts `{generation, filters}` (same generation fields as `/generate`, including `countries`; same filters as `/filter`) and returns chart-ready data computed by `app/analytics.py::compute_analytics` over the filtered in-memory population:

```json
{"generation": {"count": 10000, "seed": 7, "country": "Saudi Arabia"},
 "filters": {"age_min": 25, "age_max": 40}}
```

Response sections (categorical data as `[{label, count}]` bar-ready lists; no images are rendered server-side):

1. **overview** — total, mean/median/min/max age, mean/median income **with its currency** (largest currency group), employment rate + distribution, dominant education/segment, country/city counts.
2. **demographics** — age buckets, gender, education, employment, career level, experience buckets.
3. **geography** — country/state/city distributions (state/city top 15; no maps — no coordinates exist).
4. **financial** — currency-neutral `income_bands`, per-currency income/expense stats, expense-to-income ratio buckets, `income_vs_expenses` scatter (capped at 500 deterministic points). Raw values are **never pooled across currencies**; cross-country views must use bands or per-currency figures.
5. **behavioural** — research, comparison, price sensitivity, purchase intent (commerce median), brand loyalty, decision speed, planning, impulse, discount, information seeking, risk tolerance.
6. **segments** — reuses `summarize_segments` (no second algorithm).
7. **relationships** — numeric pairs as `{sample_size, points, correlation, method: "spearman"}` plus grouped means (education→research, career→intent). Associations within synthetic data only — never causality.
8. **data_quality** — missing values, duplicate IDs, invalid categories, nulls, inconsistency counts (age/experience, career/life-stage, income/expense, gender/language mapping), segment and country coverage, and a transparent `data_quality_score = 100 * (1 - failed_checks / (n * 7))` (a consistency score, **not** accuracy).

Empty populations return zeroed structures (score `null`); missing fields are counted, never crash. Single-pass aggregation with O(n log n) sorts; no heavy dependencies.

## Synthetic assumptions (explicit)

- Region/places, language lists, currency, income scales, digital access and ecosystem lists are **synthetic modelling assumptions** for behavioural simulation, not sourced official statistics — except ISO 3166-1 codes/names, which follow the standard.
- Income scales are relative simulation anchors (e.g. India 900000 INR vs USA 68000 USD); do not read them as real median incomes and do not convert between them.
- No external data was scraped for this task; calibration to public statistics remains future work.

## Known limitations

- Behavioural segments and synthetic comparisons describe **model-generated synthetic populations**, not empirical claims about real populations.
- No user-controlled distribution enforcement (e.g. exact age-band percentages) and no causal scenario simulation (e.g. price-change response) are implemented; new services are isolated so these can be added later without rewriting the generator.
- City-language affinities are modelled for a small set of known cities; elsewhere a generic dominant-language weighting applies.
- Same-seed outputs changed between schema `1.0` and `1.1` where coherence required new draws; determinism within `1.1` (same seed + config → same profiles) is preserved and tested.
