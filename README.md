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
- `POST /generate` — generate profiles or directly download an export

```json
{"count": 100, "seed": 12345, "country_mode": "specific", "country": "Japan", "age_range": [24, 45], "format": "json"}
```

`format` accepts `json`, `csv`, or `parquet`. JSON returns metadata and `profiles`; CSV and Parquet return only the requested in-memory download. No files are created on disk. `country_mode` accepts `specific` (the backwards-compatible default, `India`) or `global`; global mode uses configured, non-uniform country weights.

## Schema and realism

Schema version `1.1` defines more than 500 unique meaningful columns spanning identity, household, education, career, finance, commerce, technology, media, food, travel, fashion, mobility, wellness, home, hobbies, payments, decision behavior, and culture. The registry is in `app/schemas.py` and records every field's domain, type, and generation dependency.

Profiles use a profile-specific hash-derived random stream, so the same seed, request configuration, profile index, and generator version always produce the same record. Latent traits (technology affinity, price sensitivity, health orientation, cultural openness, planning orientation, and others) combine with age, career, income, family, and location to produce correlated observables. Behavioral propensities are returned as clear five-level strings—not opaque floats—such as `Not interested` through `Highly interested`, or `Never` through `Very frequently`. Only genuinely continuous quantities (screen time, streaming hours, and savings rate) remain floats.

## Geographic model and validation

`app/geography.py` is the country configuration layer. It currently provides modeled contexts for India, United States, United Kingdom, Japan, Saudi Arabia, Brazil, and Nigeria. Each context supplies weighted global selection, locations, languages, currency, income scale, industries, media platforms, payment ecosystem, transport modes, food patterns, cultural/religious distributions, and digital access. Generators consume the selected context; they do not contain country-specific branches. Add a country by adding one context record and its locations.

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

Supported filters: `age_min`/`age_max`, `gender`, `country`, `education`, `employment_status`, `career_level`, `income_band`, `research_intensity`, `comparison_behaviour`, `purchase_intent` (median of commerce purchase-intent scores), `price_sensitivity`, `brand_loyalty`, `decision_speed`, `planning_behaviour`, `impulse_buying`, `behavioural_segment`. Invalid values return `422` with the valid options; empty matches return `matched_count: 0` (not an error). Filter logic lives in `app/filtering.py::apply_filters` (`FILTER_REGISTRY` extends it without endpoint changes).

## Population comparison

`POST /compare` accepts two or more labelled populations of any size and returns normalised distributions:

```json
{"populations": [{"label": "India", "generation": {"count": 5000, "seed": 7, "country": "India"}},
                 {"label": "Saudi Arabia", "generation": {"count": 5000, "seed": 7, "country": "Saudi Arabia"}}]}
```

Response: `{populations: {label: {n}}, demographics: [...], behavioural: [...], segments: {...}}`. Each dimension entry is `{dimension, categories, populations: {label: {n, counts, percentages}}}` covering age/gender/education/employment/career/income, eight behavioural attributes, and segment distribution. Logic lives in `app/comparison.py::compare_populations`.

## Known limitations

- Behavioural segments and synthetic comparisons describe **model-generated synthetic populations**, not empirical claims about real populations.
- No user-controlled distribution enforcement (e.g. exact age-band percentages) and no causal scenario simulation (e.g. price-change response) are implemented; new services are isolated so these can be added later without rewriting the generator.
- City-language affinities are modelled for a small set of known cities; elsewhere a generic dominant-language weighting applies.
- Same-seed outputs changed between schema `1.0` and `1.1` where coherence required new draws; determinism within `1.1` (same seed + config → same profiles) is preserved and tested.
