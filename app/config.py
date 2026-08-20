from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    app_env = os.getenv("APP_ENV", "development")
    max_profiles_per_request = int(os.getenv("MAX_PROFILES_PER_REQUEST", "10000"))
    log_level = os.getenv("LOG_LEVEL", "INFO")

@lru_cache
def get_settings() -> Settings:
    return Settings()
