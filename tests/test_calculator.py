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
