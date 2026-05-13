import statistics
from src.calculator import OptionsCalculator


class UnusualDetector:
    def __init__(self, vol_oi_threshold=0.5, premium_zscore=2.0, min_contracts=50,
                 score_weights=None):
        self.vol_oi_threshold = vol_oi_threshold
        self.premium_zscore = premium_zscore
        self.min_contracts = min_contracts
        self.score_weights = score_weights or [0.25, 0.50, 0.15, 0.10]
        self.calc = OptionsCalculator()

    def analyze_chain(self, ticker, underlying_price, options):
        alerts = []

        premiums = []
        for opt in options:
            premium = self.calc.compute_premium(opt.last, opt.volume)
            premiums.append(premium)

        mean_premium = statistics.mean(premiums) if premiums else 0
        std_premium = statistics.stdev(premiums) if len(premiums) > 1 else 1

        for opt in options:
            # Skip options with no volume or missing data
            if opt.volume < self.min_contracts:
                continue
            if opt.open_interest <= 0:
                continue  # Can't compute vol/OI ratio without OI
            if opt.bid <= 0 or opt.ask <= 0:
                continue  # No executable price

            signal = {}

            vol_oi = self.calc.compute_vol_oi_ratio(opt.volume, opt.open_interest)
            if vol_oi >= self.vol_oi_threshold:
                signal["reason"] = "high_vol_oi"
                signal["vol_oi_ratio"] = round(vol_oi, 2)

            premium = self.calc.compute_premium(opt.last, opt.volume)
            if std_premium > 0:
                z = (premium - mean_premium) / std_premium
                if z >= self.premium_zscore:
                    prefix = signal.get("reason", "")
                    signal["reason"] = (prefix + " large_premium").strip()
                    signal["premium_zscore"] = round(z, 2)

            if signal:
                signal.update({
                    "ticker": ticker,
                    "strike": opt.strike,
                    "expiration": opt.expiration,
                    "option_type": opt.option_type,
                    "bid": opt.bid,
                    "ask": opt.ask,
                    "price": opt.last,
                    "volume": opt.volume,
                    "open_interest": opt.open_interest,
                    "delta": opt.delta,
                    "iv": opt.iv,
                    "premium_usd": round(premium, 2)
                })
                alerts.append(signal)

        return alerts

    def score_opportunity(self, signal: dict) -> float:
        w1, w2, w3, w4 = self.score_weights

        vol_oi_norm = min(signal.get("vol_oi_ratio", 0) / 2.0, 1.0) * 100
        premium_mapped = min(signal.get("premium_zscore", 0) / 5.0, 1.0) * 100
        iv_rank = signal.get("iv_rank", 50.0)
        gex_contrib = min(abs(signal.get("gex_contribution", 0)) * 10, 1.0) * 100

        score = w1 * vol_oi_norm + w2 * premium_mapped + w3 * iv_rank + w4 * gex_contrib
        return round(min(score, 100.0), 1)
