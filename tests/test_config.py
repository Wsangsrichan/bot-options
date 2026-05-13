from src.config import Config


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    config = Config()
    assert config.telegram_bot_token == "bot_token"
    assert config.telegram_chat_id == "123456"


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")

    config = Config()
    assert config.scan_tickers == ["SPY"]
    assert config.scan_interval_minutes == 5
    assert config.vol_oi_ratio_threshold == 0.5
    assert config.greeks_max_strikes_per_side == 10


def test_config_raises_on_missing_required(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    try:
        Config()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "TELEGRAM_BOT_TOKEN" in str(e)
