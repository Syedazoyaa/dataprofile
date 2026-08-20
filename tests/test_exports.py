import io
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_requested_csv_and_parquet_are_returned_directly():
    csv_response = client.post("/generate", json={"count": 3, "seed": 4, "format": "csv"})
    assert csv_response.status_code == 200 and csv_response.headers["content-type"].startswith("text/csv")
    assert "profile_id" in csv_response.text
    parquet_response = client.post("/generate", json={"count": 3, "seed": 4, "format": "parquet"})
    assert parquet_response.status_code == 200
    assert len(pd.read_parquet(io.BytesIO(parquet_response.content))) == 3
