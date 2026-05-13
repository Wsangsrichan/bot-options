import pytest

@pytest.fixture
def sample_chain():
    """Minimal SPY options chain for testing."""
    return {
        "ticker": "SPY",
        "underlying_price": 520.50,
        "options": [
            {
                "strike": 525.0,
                "expiration": "2026-06-20",
                "option_type": "C",
                "bid": 5.20,
                "ask": 5.35,
                "last": 5.25,
                "volume": 1523,
                "open_interest": 45000,
                "delta": 0.42,
                "gamma": 0.08,
                "theta": -0.15,
                "vega": 0.22,
                "iv": 0.185
            },
            {
                "strike": 515.0,
                "expiration": "2026-06-20",
                "option_type": "P",
                "bid": 3.10,
                "ask": 3.25,
                "last": 3.15,
                "volume": 892,
                "open_interest": 32000,
                "delta": -0.38,
                "gamma": 0.07,
                "theta": -0.12,
                "vega": 0.20,
                "iv": 0.190
            }
        ]
    }
