from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_personas_and_json_generation():
    assert client.get("/health").json()["status"] == "ok"
    personas = client.get("/personas").json()["personas"]
    assert len(personas) > 5
    response = client.post("/generate", json={"count": 2, "seed": 42})
    assert response.status_code == 200
    assert response.json()["feature_count"] >= 500
    assert len(response.json()["profiles"]) == 2

def test_invalid_request_controls_are_rejected():
    assert client.post("/generate", json={"count": 0}).status_code == 422
    assert client.post("/generate", json={"count": 10001}).status_code == 422
    assert client.post("/generate", json={"count": 2001}).status_code == 422
    assert client.post("/generate", json={"age_range": [40, 20]}).status_code == 422
    assert client.post("/generate", json={"persona": "not a persona"}).status_code == 422
    assert client.post("/generate", json={"preferred_language": "Klingon"}).status_code == 422
    assert client.post("/generate", json={"format": "xml"}).status_code == 422
    assert client.post("/generate", json={"country": "Atlantis"}).status_code == 422

def test_global_and_specific_country_generation():
    specific = client.post("/generate", json={"count": 2, "seed": 7, "country": "Japan"})
    assert specific.status_code == 200
    assert {p["country"] for p in specific.json()["profiles"]} == {"Japan"}
    global_result = client.post("/generate", json={"count": 20, "seed": 7, "country_mode": "global"})
    assert global_result.status_code == 200
    assert len({p["country"] for p in global_result.json()["profiles"]}) > 1


def test_omitted_geography_is_global_and_country_requests_stay_explicit():
    default_result = client.post("/generate", json={"count": 50, "seed": 17})
    explicit_global = client.post("/generate", json={"count": 50, "seed": 17, "country_mode": "global"})
    assert default_result.status_code == explicit_global.status_code == 200
    assert default_result.json()["profiles"] == explicit_global.json()["profiles"]
    assert client.post("/generate", json={"count": 1, "country_mode": "global", "country": "Japan"}).status_code == 422
