import pytest
from unittest.mock import patch, MagicMock
from src.dashboard import app

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_index_returns_html(client):
    resp = client.get("/")
    assert resp.status_code in (200, 500)

def test_api_returns_json(client):
    resp = client.get("/api/opportunities")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)

def test_api_paper_portfolio_has_new_fields(client):
    resp = client.get("/api/paper/portfolio")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "unrealized_pnl" in data
    assert "portfolio_value" in data
    assert "open_positions_data" in data
    assert "open_positions" in data
    assert isinstance(data["open_positions"], int)

def test_api_paper_portfolio_mtmcallback_none(client):
    resp = client.get("/api/paper/portfolio")
    assert resp.status_code == 200
    data = resp.get_json()
    # No open positions → all should be 0/empty
    assert data["unrealized_pnl"] == 0.0
    assert data["portfolio_value"] is not None
