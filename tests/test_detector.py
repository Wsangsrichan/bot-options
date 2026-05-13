from src.detector import UnusualDetector
from src.yfinance_client import OptionData


def make_option(**overrides):
    defaults = {
        "strike": 525.0, "expiration": "2026-06-20", "option_type": "C",
        "bid": 5.20, "ask": 5.35, "last": 5.25,
        "volume": 500, "open_interest": 1000,
        "delta": 0.42, "gamma": 0.08, "theta": -0.15, "vega": 0.22, "rho": 0.05, "iv": 0.18
    }
    defaults.update(overrides)
    return OptionData(**defaults)


def test_detect_high_vol_oi():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=3.0, min_contracts=50)
    opt = make_option(volume=800, open_interest=1000)  # 0.8 ratio > 0.5
    alerts = detector.analyze_chain("SPY", 520.50, [opt])
    assert len(alerts) == 1
    assert alerts[0]["reason"] == "high_vol_oi"


def test_normal_activity_no_alert():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=3.0, min_contracts=50)
    opt = make_option(volume=100, open_interest=5000, last=0.50)
    alerts = detector.analyze_chain("SPY", 520.50, [opt])
    assert len(alerts) == 0


def test_skip_low_contracts():
    detector = UnusualDetector(vol_oi_threshold=0.5, premium_zscore=3.0, min_contracts=100)
    opt = make_option(volume=95, open_interest=100, last=10.0)
    alerts = detector.analyze_chain("SPY", 520.50, [opt])
    assert len(alerts) == 0


def test_large_premium_zscore():
    detector = UnusualDetector(vol_oi_threshold=0.9, premium_zscore=1.0, min_contracts=50)
    cheap = [make_option(volume=100, last=0.10) for _ in range(4)]
    expensive = make_option(volume=200, last=50.0)
    alerts = detector.analyze_chain("SPY", 520.50, cheap + [expensive])
    assert len(alerts) == 1
    assert "large_premium" in alerts[0]["reason"]


def test_combined_reasons():
    detector = UnusualDetector(vol_oi_threshold=0.3, premium_zscore=1.0, min_contracts=50)
    cheap = [make_option(volume=100, last=0.10) for _ in range(4)]
    unusual = make_option(volume=800, open_interest=1000, last=50.0)  # vol_oi 0.8 + large premium
    alerts = detector.analyze_chain("SPY", 520.50, cheap + [unusual])
    assert len(alerts) == 1
    assert "high_vol_oi" in alerts[0]["reason"]
    assert "large_premium" in alerts[0]["reason"]
