import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from .config import get_settings
from .comparison import compare_populations
from .exports import export_bytes
from .filtering import active_filters, apply_filters, validate_filters
from .generator import LANGUAGES, generate_profiles
from .geography import supported_continents, supported_countries, supported_subregions
from .personas import PERSONAS
from .schemas import CompareRequest, FilterRequest, GenerateRequest, SegmentsRequest, PROFILE_COLUMNS, PROFILE_SCHEMA_VERSION
from .segmentation import SEGMENT_DEFINITIONS, classify_profile, summarize_segments

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
app = FastAPI(title="DataProfile API", version=PROFILE_SCHEMA_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root(): return {"service": "DataProfile API", "version": PROFILE_SCHEMA_VERSION, "docs": "/docs"}

@app.get("/health")
def health(): return {"status": "ok", "environment": settings.app_env, "schema_version": PROFILE_SCHEMA_VERSION}

@app.get("/personas")
def personas(): return {"personas": [{"name": name, "typical_genres": genres} for name, genres in PERSONAS.items()], "supported_languages": sorted(LANGUAGES), "supported_countries": supported_countries(), "supported_continents": supported_continents(), "supported_subregions": supported_subregions()}

def _generate_from_spec(spec) -> list[dict]:
    if spec.country_mode == "specific" and spec.country not in supported_countries(): raise ValueError("Unsupported country")
    if spec.country_mode == "continent" and spec.continent and spec.continent not in supported_continents(): raise ValueError("Unsupported continent")
    if spec.country_mode in {"region","subregion"} and spec.subregion and spec.subregion not in supported_subregions(): raise ValueError("Unsupported subregion")
    if spec.persona and spec.persona not in PERSONAS: raise ValueError("Unsupported persona")
    if spec.preferred_language and spec.preferred_language not in LANGUAGES: raise ValueError("Unsupported preferred_language")
    geo_region = spec.region or spec.subregion or spec.continent
    return generate_profiles(spec.count, spec.seed, spec.country, spec.age_range, spec.preferred_language, spec.persona, country_mode=spec.country_mode, region=geo_region, continent=spec.continent)

@app.get("/segments/definitions")
def segment_definitions():
    return {"segments": list(SEGMENT_DEFINITIONS), "note": "Segments describe the generated synthetic population, not real-world customer segments."}

@app.post("/segments")
def segments(request: SegmentsRequest):
    if request.generation.count > settings.max_profiles_per_request: raise HTTPException(422, "count exceeds configured request limit")
    try:
        profiles = _generate_from_spec(request.generation)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    summary = summarize_segments(profiles)
    classified = [{**p, "behavioural_segment": c["segment_id"], "behavioural_segment_name": c["segment_name"]} for p, c in ((p, classify_profile(p)) for p in profiles)]
    return {**summary, "profiles": classified, "note": "Segments describe the generated synthetic population, not real-world customer segments."}

@app.post("/filter")
def filter_profiles(request: FilterRequest):
    if request.generation.count > settings.max_profiles_per_request: raise HTTPException(422, "count exceeds configured request limit")
    try:
        validate_filters(request.filters, supported_countries())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        profiles = _generate_from_spec(request.generation)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    matched = apply_filters(profiles, request.filters)
    return {"total_generated": len(profiles), "matched_count": len(matched), "filters_applied": active_filters(request.filters), "profiles": matched}

@app.post("/compare")
def compare(request: CompareRequest):
    for pop in request.populations:
        if pop.generation.count > settings.max_profiles_per_request: raise HTTPException(422, f"count exceeds configured request limit for population '{pop.label}'")
    try:
        generated = {pop.label: _generate_from_spec(pop.generation) for pop in request.populations}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return compare_populations(generated)

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.count > settings.max_profiles_per_request: raise HTTPException(422, "count exceeds configured request limit")
    if request.persona and request.persona not in PERSONAS: raise HTTPException(422, "Unsupported persona")
    if request.preferred_language and request.preferred_language not in LANGUAGES: raise HTTPException(422, "Unsupported preferred_language")
    if request.country_mode == "specific" and request.country not in supported_countries(): raise HTTPException(422, "Unsupported country")
    if request.country_mode == "continent" and request.continent and request.continent not in supported_continents(): raise HTTPException(422, "Unsupported continent")
    if request.country_mode in {"region","subregion"} and request.subregion and request.subregion not in supported_subregions(): raise HTTPException(422, "Unsupported subregion")
    started = time.perf_counter()
    try:
        logger.info("generation started count=%s format=%s", request.count, request.format)
        # Map new request fields to geography context (continent/subregion via region param)
        geo_region = request.region or request.subregion or request.continent
        geo_continent = request.continent
        profiles = generate_profiles(request.count, request.seed, request.country, request.age_range, request.preferred_language, request.persona, country_mode=request.country_mode, region=geo_region, continent=geo_continent)
        duration = time.perf_counter() - started
        logger.info("generation completed count=%s format=%s duration=%.3fs", request.count, request.format, duration)
        metadata = {"count": len(profiles), "seed": request.seed, "profile_schema_version": PROFILE_SCHEMA_VERSION, "feature_count": len(PROFILE_COLUMNS), "generation_seconds": round(duration, 4)}
        if request.format == "json": return {**metadata, "profiles": profiles}
        payload, media_type, filename = export_bytes(profiles, request.format)
        return Response(payload, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Profile-Schema-Version": PROFILE_SCHEMA_VERSION})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("generation failed count=%s format=%s", request.count, request.format)
        raise HTTPException(500, "Profile generation failed") from exc
