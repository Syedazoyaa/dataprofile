from functools import lru_cache
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Runtime configuration with validated, explicit deployment defaults."""

    def __init__(self) -> None:
        self.app_env = os.getenv("APP_ENV", "development").strip().lower()
        # Default cap: 2000 profiles ≈ 6s generation and ≈68MB JSON. Larger batches
        # risk proxy timeouts and multi-hundred-MB payloads; raise deliberately via
        # MAX_PROFILES_PER_REQUEST where the deployment allows it.
        self.max_profiles_per_request = int(os.getenv("MAX_PROFILES_PER_REQUEST", "2000"))
        if self.max_profiles_per_request < 1:
            raise ValueError("MAX_PROFILES_PER_REQUEST must be at least 1")
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        # A reference date is part of every generated profile, allowing a past
        # population to be reproduced exactly.  The default is deliberately
        # evaluated once at process startup instead of hiding a hard-coded date.
        reference_text = os.getenv("GENERATION_REFERENCE_DATE", date.today().isoformat())
        try:
            self.generation_reference_date = date.fromisoformat(reference_text)
        except ValueError as exc:
            raise ValueError("GENERATION_REFERENCE_DATE must use YYYY-MM-DD") from exc

        origins_text = os.getenv("CORS_ORIGINS", "*" if self.app_env == "development" else "")
        self.cors_origins = tuple(origin.strip() for origin in origins_text.split(",") if origin.strip())

@lru_cache
def get_settings() -> Settings:
    return Settings()
