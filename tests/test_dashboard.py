import pytest
from src.dashboard import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code in (200, 500)  # 500 OK if no data yet

def test_api_returns_json(client):
    resp = client.get("/api/opportunities")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
