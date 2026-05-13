from src.config import Config


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test_key_123")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    config = Config()
    assert config.polygon_api_key == "test_key_123"
    assert config.telegram_bot_token == "bot_token"
    assert config.telegram_chat_id == "123456"


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("POLYGON_API_KEY", "test_key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")

    config = Config()
    assert config.scan_tickers == ["SPY"]
    assert config.scan_interval_minutes == 5
    assert config.polygon_api_base == "https://api.polygon.io"
    assert config.vol_oi_ratio_threshold == 0.5


def test_config_raises_on_missing_required():
    try:
        Config()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "POLYGON_API_KEY" in str(e) or "Missing required" in str(e)
