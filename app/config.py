from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    app_env = os.getenv("APP_ENV", "development")
    # Default cap: 2000 profiles ≈ 6s generation and ≈68MB JSON. Larger batches
    # risk proxy timeouts and multi-hundred-MB payloads; raise deliberately via
    # MAX_PROFILES_PER_REQUEST where the deployment allows it.
    max_profiles_per_request = int(os.getenv("MAX_PROFILES_PER_REQUEST", "2000"))
    log_level = os.getenv("LOG_LEVEL", "INFO")

@lru_cache
def get_settings() -> Settings:
    return Settings()
