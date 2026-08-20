# DataProfile API

A stateless FastAPI service that creates deterministic, correlated synthetic Indian consumer profiles. It has no authentication, accounts, jobs, database, or generated-file storage.

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
{"count": 100, "seed": 12345, "age_range": [24, 45], "format": "json"}
```

`format` accepts `json`, `csv`, or `parquet`. JSON returns metadata and `profiles`; CSV and Parquet return only the requested in-memory download. No files are created on disk.

## Schema and realism

Schema version `1.0` defines more than 500 unique meaningful columns spanning identity, household, education, career, finance, commerce, technology, media, food, travel, fashion, mobility, wellness, home, hobbies, payments, and decision behavior. The registry is in `app/schemas.py` and records every field's domain, type, and generation dependency.

Profiles use a profile-specific hash-derived random stream, so the same seed and profile index always produce the same record. Latent traits (technology affinity, price sensitivity, health orientation, cultural openness, planning orientation, and others) combine with age, career, income, family, and location to produce correlated observables. Behavioral propensities are returned as clear five-level strings—not opaque floats—such as `Not interested` through `Highly interested`, or `Never` through `Very frequently`. Only genuinely continuous quantities (screen time, streaming hours, and savings rate) remain floats.

## Test

```powershell
pytest -q
```
