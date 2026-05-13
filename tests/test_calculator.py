from src.calculator import OptionsCalculator


def test_compute_delta():
    calc = OptionsCalculator()
    d = calc.compute_delta(option_type='c', S=100, K=105, T=0.25, r=0.05, sigma=0.20)
    assert 0.30 < d < 0.45


def test_compute_gamma():
    calc = OptionsCalculator()
    g = calc.compute_gamma(option_type='c', S=100, K=100, T=0.25, r=0.05, sigma=0.20)
    assert g > 0.03


def test_compute_all_greeks():
    calc = OptionsCalculator()
    greeks = calc.compute_all_greeks(option_type='p', S=520, K=515, T=0.08, r=0.05, sigma=0.18)
    assert 'delta' in greeks
    assert 'gamma' in greeks
    assert 'theta' in greeks
    assert 'vega' in greeks
    assert 'rho' in greeks
    assert -0.55 < greeks['delta'] < -0.35


def test_solve_iv():
    calc = OptionsCalculator()
    iv = calc.solve_iv(market_price=5.25, option_type='c', S=520, K=525, T=0.10, r=0.05)
    assert 0.05 < iv < 0.30


def test_iv_rank():
    calc = OptionsCalculator()
    rank = calc.compute_iv_rank(current_iv=0.20, iv_52w_low=0.12, iv_52w_high=0.32)
    assert abs(rank - 40.0) < 1e-9


def test_compute_premium():
    calc = OptionsCalculator()
    premium = calc.compute_premium(price=5.25, contracts=100)
    assert premium == 52500.0


def test_heuristic_greeks_deep_itm_call():
    calc = OptionsCalculator()
    g = calc.heuristic_greeks('C', S=500, K=300, T=0.1, r=0.05)
    assert g is not None
    assert g['delta'] == 1.0
    assert g['gamma'] == 0.0
    assert g['vega'] == 0.0
    assert g['theta'] < 0  # negative theta
    assert g['rho'] > 0     # positive rho for call


def test_heuristic_greeks_deep_itm_put():
    calc = OptionsCalculator()
    g = calc.heuristic_greeks('P', S=300, K=500, T=0.1, r=0.05)
    assert g is not None
    assert g['delta'] == -1.0
    assert g['gamma'] == 0.0
    assert g['vega'] == 0.0
    assert g['rho'] < 0  # negative rho for put


def test_heuristic_greeks_deep_otm():
    calc = OptionsCalculator()
    # Deep OTM CALL
    g = calc.heuristic_greeks('C', S=300, K=500, T=0.1, r=0.05)
    assert g is not None
    assert g['delta'] == 0.0
    assert g['gamma'] == 0.0
    assert g['vega'] == 0.0

    # Deep OTM PUT
    g = calc.heuristic_greeks('P', S=500, K=300, T=0.1, r=0.05)
    assert g is not None
    assert g['delta'] == 0.0
    assert g['gamma'] == 0.0


def test_heuristic_greeks_near_money_returns_none():
    calc = OptionsCalculator()
    # Not deep enough — should return None (use normal solver)
    g = calc.heuristic_greeks('C', S=500, K=480, T=0.1, r=0.05)  # S/K = 1.04 < 1.3
    assert g is None


def test_max_pain():
    calc = OptionsCalculator()
    options = [
        {"strike": 520, "option_type": "C", "open_interest": 100, "last": 5.0},
        {"strike": 520, "option_type": "P", "open_interest": 50, "last": 4.0},
        {"strike": 525, "option_type": "C", "open_interest": 80, "last": 3.0},
        {"strike": 525, "option_type": "P", "open_interest": 200, "last": 6.0},
    ]
    mp = calc.max_pain(options, spot=522.5)
    assert mp == 525.0


def test_gamma_exposure():
    calc = OptionsCalculator()
    options = [
        {"strike": 520, "option_type": "C", "gamma": 0.02, "open_interest": 100},
        {"strike": 520, "option_type": "P", "gamma": 0.02, "open_interest": 50},
        {"strike": 525, "option_type": "C", "gamma": 0.01, "open_interest": 200},
    ]
    spot = 522.5
    gex = calc.gamma_exposure(options, spot)
    expected_total = (0.02 * 100 + 0.02 * 50 + 0.01 * 200) * 100 * 522.5
    assert abs(gex["total"] - expected_total) < 1
    assert 520.0 in gex["by_strike"]
    assert 525.0 in gex["by_strike"]
