import csv
import io
import json
from .schemas import CORE_PROFILE_FIELDS, PROFILE_COLUMNS

def _columns(view: str) -> list[str]:
    return list(CORE_PROFILE_FIELDS) if view == "summary" else list(PROFILE_COLUMNS)

def _filename(*, individual: str | None, view: str, requested_format: str, full_count: int) -> str:
    ext = {"json": "json", "csv": "csv"}[requested_format]
    if individual:
        return f"raven_profile_{individual}.{ext}"
    if view == "summary":
        return f"raven_profiles_summary.{ext}"
    return f"raven_profiles_full_{full_count}.{ext}"

def export_bytes(profiles: list[dict], requested_format: str, view: str = "full", individual: str | None = None) -> tuple[bytes, str, str]:
    """Create only the requested in-memory representation; nothing is persisted.

    Columns come from the central schema registry (full) or the central core
    set (summary); filenames encode scope/view and the canonical full count.
    """
    columns = _columns(view)
    rows = [{col: profile.get(col) for col in columns} for profile in profiles]
    filename = _filename(individual=individual, view=view, requested_format=requested_format, full_count=len(PROFILE_COLUMNS))
    if requested_format == "json":
        return json.dumps(rows, ensure_ascii=False).encode("utf-8"), "application/json", filename
    if requested_format == "csv":
        stream = io.StringIO(newline="")
        # Explicitly use registry order so personality_name remains first regardless of dict construction details
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)
        return stream.getvalue().encode("utf-8"), "text/csv", filename
    raise ValueError("Unsupported export format")
