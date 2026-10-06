import io
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_requested_csv_is_returned_directly():
    csv_response = client.post("/generate", json={"count": 3, "seed": 4, "format": "csv"})
    assert csv_response.status_code == 200 and csv_response.headers["content-type"].startswith("text/csv")
    assert "profile_id" in csv_response.text
    assert len(pd.read_csv(io.StringIO(csv_response.text))) == 3


def test_parquet_is_not_a_public_export_format():
    assert client.post("/generate", json={"count": 3, "seed": 4, "format": "parquet"}).status_code == 422
