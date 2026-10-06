import json
import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from .config import get_settings
from .analytics import compute_analytics
from .comparison import compare_populations
from .exports import export_bytes
from .filtering import active_filters, apply_filters, validate_filters
from .generator import LANGUAGES, generate_profiles
from .geography import country_registry, resolve_country_name, supported_continents, supported_countries, supported_subregions
from .personas import PERSONAS
from .schemas import AnalyticsRequest, CompareRequest, FilterRequest, GenerateRequest, SegmentsRequest, CORE_PROFILE_FIELDS, PROFILE_COLUMNS, PROFILE_SCHEMA_VERSION
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
    if spec.countries is not None:
        # Multi-country selection: each entry validated once via the shared registry.
        try:
            resolved = [resolve_country_name(entry) for entry in spec.countries]
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if spec.country_mode == "specific" and len(set(resolved)) == 1:
            spec_country, mode, countries = resolved[0], "specific", None
        else:
            spec_country, mode, countries = spec.country, "multiple", resolved
    else:
        spec_country = spec.country
        if spec.country_mode == "specific" and spec_country not in supported_countries():
            # Allow alpha-2/alpha-3 codes through the shared resolver as well.
            try:
                spec_country = resolve_country_name(spec_country)
            except ValueError:
                raise ValueError("Unsupported country") from None
        mode, countries = spec.country_mode, None
    if mode == "specific" and spec_country not in supported_countries(): raise ValueError("Unsupported country")
    if mode == "continent" and spec.continent and spec.continent not in supported_continents(): raise ValueError("Unsupported continent")
    if mode in {"region","subregion"} and spec.subregion and spec.subregion not in supported_subregions(): raise ValueError("Unsupported subregion")
    if spec.persona and spec.persona not in PERSONAS: raise ValueError("Unsupported persona")
    if spec.preferred_language and spec.preferred_language not in LANGUAGES: raise ValueError("Unsupported preferred_language")
    geo_region = spec.region or spec.subregion or spec.continent
    return generate_profiles(spec.count, spec.seed, spec_country, spec.age_range, spec.preferred_language, spec.persona, country_mode=mode, region=geo_region, continent=spec.continent, countries=countries)

@app.get("/countries")
def countries():
    """Canonical country registry for frontend dropdowns, filters and analytics."""
    return {"count": len(country_registry()), "countries": country_registry()}

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
    # Each side must pin exactly one explicitly selected country.
    pinned = []
    for pop in request.populations:
        spec = pop.generation
        try:
            if spec.countries is not None:
                resolved = [resolve_country_name(entry) for entry in spec.countries]
                if len(set(resolved)) != 1:
                    raise ValueError(f"population '{pop.label}' must select exactly one country")
                pinned.append(resolved[0])
            elif spec.country_mode == "specific" and spec.country:
                pinned.append(resolve_country_name(spec.country))
            else:
                raise ValueError(f"population '{pop.label}' must select exactly one country")
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    if len(set(pinned)) != 2:
        raise HTTPException(422, "comparison requires two different countries")
    try:
        generated = {pop.label: _generate_from_spec(pop.generation) for pop in request.populations}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return compare_populations(generated)

@app.post("/analytics")
def analytics(request: AnalyticsRequest):
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
    result = compute_analytics(matched)
    result["total_generated"] = len(profiles)
    result["filters_applied"] = active_filters(request.filters)
    return result

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.count > settings.max_profiles_per_request: raise HTTPException(422, "count exceeds configured request limit")
    if request.persona and request.persona not in PERSONAS: raise HTTPException(422, "Unsupported persona")
    if request.preferred_language and request.preferred_language not in LANGUAGES: raise HTTPException(422, "Unsupported preferred_language")
    if request.country_mode == "continent" and request.continent and request.continent not in supported_continents(): raise HTTPException(422, "Unsupported continent")
    if request.country_mode in {"region","subregion"} and request.subregion and request.subregion not in supported_subregions(): raise HTTPException(422, "Unsupported subregion")
    mode, gen_country, gen_countries = request.country_mode, request.country, None
    if request.countries is not None:
        try:
            resolved = [resolve_country_name(entry) for entry in request.countries]
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if mode == "specific" and len(set(resolved)) == 1:
            gen_country = resolved[0]
        else:
            mode, gen_countries = "multiple", resolved
    elif mode == "specific":
        try:
            gen_country = resolve_country_name(gen_country)
        except ValueError:
            raise HTTPException(422, "Unsupported country") from None
    started = time.perf_counter()
    try:
        logger.info("generation started count=%s format=%s", request.count, request.format)
        # Map new request fields to geography context (continent/subregion via region param)
        geo_region = request.region or request.subregion or request.continent
        geo_continent = request.continent
        profiles = generate_profiles(request.count, request.seed, gen_country, request.age_range, request.preferred_language, request.persona, country_mode=mode, region=geo_region, continent=geo_continent, countries=gen_countries)
        duration = time.perf_counter() - started
        logger.info("generation completed count=%s format=%s duration=%.3fs", request.count, request.format, duration)
        if request.scope == "individual":
            index = request.profile_index or 1
            profiles = profiles[index - 1:index]
            individual_id = profiles[0]["profile_id"] if profiles else None
        else:
            individual_id = None
        if request.view == "summary":
            profiles = [{col: profile.get(col) for col in CORE_PROFILE_FIELDS} for profile in profiles]
        metadata = {"count": len(profiles), "seed": request.seed, "profile_schema_version": PROFILE_SCHEMA_VERSION, "view": request.view, "scope": request.scope, "feature_count": len(profiles[0]) if profiles else 0, "canonical_feature_count": len(PROFILE_COLUMNS), "generation_seconds": round(duration, 4)}
        if request.format == "json" and individual_id is None: return {**metadata, "profiles": profiles}
        if individual_id is not None and request.format == "json":
            filename = f"raven_profile_{individual_id}.json"
            return Response(json.dumps(profiles[0], ensure_ascii=False).encode("utf-8"), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Profile-Schema-Version": PROFILE_SCHEMA_VERSION})
        payload, media_type, filename = export_bytes(profiles, request.format, view=request.view, individual=individual_id)
        return Response(payload, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Profile-Schema-Version": PROFILE_SCHEMA_VERSION})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        logger.exception("generation failed count=%s format=%s", request.count, request.format)
        raise HTTPException(500, "Profile generation failed") from exc
