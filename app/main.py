import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from .config import get_settings
from .exports import export_bytes
from .generator import LANGUAGES, generate_profiles
from .personas import PERSONAS
from .schemas import GenerateRequest, PROFILE_COLUMNS, PROFILE_SCHEMA_VERSION

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
def personas(): return {"personas": [{"name": name, "typical_genres": genres} for name, genres in PERSONAS.items()], "supported_languages": sorted(LANGUAGES)}

@app.post("/generate")
def generate(request: GenerateRequest):
    if request.count > settings.max_profiles_per_request: raise HTTPException(422, "count exceeds configured request limit")
    if request.persona and request.persona not in PERSONAS: raise HTTPException(422, "Unsupported persona")
    if request.preferred_language and request.preferred_language not in LANGUAGES: raise HTTPException(422, "Unsupported preferred_language")
    started = time.perf_counter()
    try:
        logger.info("generation started count=%s format=%s", request.count, request.format)
        profiles = generate_profiles(request.count, request.seed, request.country, request.age_range, request.preferred_language, request.persona)
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
