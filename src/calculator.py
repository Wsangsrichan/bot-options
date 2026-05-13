import numpy as np
from vollib.black_scholes import black_scholes as bs_price
from vollib.black_scholes.greeks.analytical import delta, gamma, theta, vega, rho
from scipy.optimize import brentq


class OptionsCalculator:
    TOLERANCE = 1e-8

    def compute_delta(self, option_type, S, K, T, r, sigma):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        return delta(flag, S, K, T, r, sigma)

    def compute_gamma(self, option_type, S, K, T, r, sigma):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        return gamma(flag, S, K, T, r, sigma)

    def compute_all_greeks(self, option_type, S, K, T, r, sigma):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'
        return {
            'delta': delta(flag, S, K, T, r, sigma),
            'gamma': gamma(flag, S, K, T, r, sigma),
            'theta': theta(flag, S, K, T, r, sigma),
            'vega': vega(flag, S, K, T, r, sigma),
            'rho': rho(flag, S, K, T, r, sigma),
        }

    def solve_iv(self, market_price, option_type, S, K, T, r):
        flag = 'c' if option_type in ('C', 'c', 'call') else 'p'

        def objective(sigma):
            try:
                price = bs_price(flag, S, K, T, r, sigma)
                return price - market_price
            except Exception:
                return -999

        try:
            iv = brentq(objective, 0.001, 5.0, xtol=self.TOLERANCE)
            return iv
        except ValueError:
            return 0.0

    def compute_iv_rank(self, current_iv, iv_52w_low, iv_52w_high):
        if iv_52w_high <= iv_52w_low:
            return 50.0
        rank = (current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low) * 100
        return max(0.0, min(100.0, rank))

    def compute_vol_oi_ratio(self, volume, open_interest):
        if open_interest == 0:
            return 0.0
        return volume / open_interest

    def compute_premium(self, price, contracts):
        return price * contracts * 100
