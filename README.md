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

Schema version `1.0` defines more than 500 unique meaningful columns spanning identity, household, education, career, finance, commerce, technology, media, food, travel, fashion, mobility, wellness, home, hobbies, payments, decision behavior, and culture. The registry is in `app/schemas.py` and records every field's domain, type, and generation dependency.

Profiles use a profile-specific hash-derived random stream, so the same seed, request configuration, profile index, and generator version always produce the same record. Latent traits (technology affinity, price sensitivity, health orientation, cultural openness, planning orientation, and others) combine with age, career, income, family, and location to produce correlated observables. Behavioral propensities are returned as clear five-level strings—not opaque floats—such as `Not interested` through `Highly interested`, or `Never` through `Very frequently`. Only genuinely continuous quantities (screen time, streaming hours, and savings rate) remain floats.

## Geographic model and validation

`app/geography.py` is the country configuration layer. It currently provides modeled contexts for India, United States, United Kingdom, Japan, Saudi Arabia, Brazil, and Nigeria. Each context supplies weighted global selection, locations, languages, currency, income scale, industries, media platforms, payment ecosystem, transport modes, food patterns, cultural/religious distributions, and digital access. Generators consume the selected context; they do not contain country-specific branches. Add a country by adding one context record and its locations.

`app/rules.py` returns structured validation violations and a coherence score derived from those checks. It verifies lifecycle, finance, country/currency, language, payment, transport, and food constraints before a profile is returned.

These country distributions and income scales are explicit modeled assumptions for behavioral simulation, not claims of empirical representativeness. No external network calls occur at generation time; future calibration can replace context values with sourced public statistics.

## Test

```powershell
pytest -q
```
