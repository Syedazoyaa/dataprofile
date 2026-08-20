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
    assert client.post("/generate", json={"age_range": [40, 20]}).status_code == 422
    assert client.post("/generate", json={"persona": "not a persona"}).status_code == 422
    assert client.post("/generate", json={"preferred_language": "Klingon"}).status_code == 422
    assert client.post("/generate", json={"format": "xml"}).status_code == 422
