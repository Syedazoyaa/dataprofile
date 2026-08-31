import csv
import io
import json
import pandas as pd
from .schemas import PROFILE_COLUMNS

def export_bytes(profiles: list[dict], requested_format: str) -> tuple[bytes, str, str]:
    """Create only the requested in-memory representation; nothing is persisted."""
    if requested_format == "json":
        return json.dumps(profiles, ensure_ascii=False).encode("utf-8"), "application/json", "profiles.json"
    if requested_format == "csv":
        stream = io.StringIO(newline="")
        # Explicitly use schema order so personality_name remains first regardless of dict construction details
        fieldnames = list(PROFILE_COLUMNS) if profiles else []
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader(); writer.writerows(profiles)
        return stream.getvalue().encode("utf-8"), "text/csv", "profiles.csv"
    if requested_format == "parquet":
        stream = io.BytesIO(); pd.DataFrame(profiles, columns=list(PROFILE_COLUMNS)).to_parquet(stream, index=False)
        return stream.getvalue(), "application/vnd.apache.parquet", "profiles.parquet"
    raise ValueError("Unsupported export format")
