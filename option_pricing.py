"""Put/Call 合理價計算 — Black-Scholes + Put/Call Ratio 溢價避險
Usage: from option_pricing import OptionPricing, put_call_ratio_analysis
"""
import math
from dataclasses import dataclass


@dataclass
class OptionResult:
    call_price: float
    put_price: float
    call_iv: float
    put_iv: float
    parity_diff: float
    fair_call: float
    fair_put: float
    call_premium_pct: float
    put_premium_pct: float


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class OptionPricing:
    """Black-Scholes 選擇權定價 + Put/Call Parity 驗證。"""

    def __init__(self, rate: float = 0.0125, days_per_year: int = 252):
        self.rate = rate
        self.days_per_year = days_per_year

    def _d1_d2(self, S: float, K: float, T: float, sigma: float) -> tuple:
        if sigma <= 0 or T <= 0:
            return 0, 0
        d1 = (math.log(S / K) + (self.rate + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return d1, d2

    def black_scholes(self, S: float, K: float, T: float, sigma: float,
                      is_call: bool = True) -> float:
        """Black-Scholes 理論價。"""
        d1, d2 = self._d1_d2(S, K, T, sigma)
        df = math.exp(-self.rate * T)
        if is_call:
            return S * _norm_cdf(d1) - K * df * _norm_cdf(d2)
        return K * df * _norm_cdf(-d2) - S * _norm_cdf(-d1)

    def implied_vol(self, market_price: float, S: float, K: float, T: float,
                    is_call: bool = True, tol: float = 1e-6, max_iter: int = 100) -> float:
        """Newton-Raphson 反推隱含波動率。"""
        if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
            return 0
        sigma = 0.3
        for i in range(max_iter):
            price = self.black_scholes(S, K, T, sigma, is_call)
            vega = self._vega(S, K, T, sigma)
            if vega < 1e-9:
                break
            diff = price - market_price
            if abs(diff) < tol:
                return sigma
            sigma -= diff / vega
            sigma = max(0.01, min(sigma, 2.0))
        return sigma if 0.01 <= sigma <= 2.0 else 0

    def _vega(self, S: float, K: float, T: float, sigma: float) -> float:
        d1, _ = self._d1_d2(S, K, T, sigma)
        return S * math.sqrt(T) * _norm_pdf(d1) if T > 0 and sigma > 0 else 0

    def put_call_parity(self, S: float, K: float, T: float,
                        call_market: float, put_market: float) -> float:
        """Put-Call Parity 偏差: C - P vs S - K*e^(-rT)。正=Call偏貴, 負=Put偏貴。"""
        df = math.exp(-self.rate * T)
        theoretical = S - K * df
        market_diff = call_market - put_market
        return market_diff - theoretical

    def evaluate(self, S: float, K: float, days_to_expiry: int,
                 call_market: float, put_market: float,
                 vol_estimate: float = 0.25) -> OptionResult:
        """完整評估: 理論價 + IV + 溢價% + Parity 偏差。"""
        T = max(days_to_expiry, 1) / self.days_per_year
        fair_call = self.black_scholes(S, K, T, vol_estimate, is_call=True)
        fair_put = self.black_scholes(S, K, T, vol_estimate, is_call=False)
        call_iv = self.implied_vol(call_market, S, K, T, is_call=True)
        put_iv = self.implied_vol(put_market, S, K, T, is_call=False)
        parity_diff = self.put_call_parity(S, K, T, call_market, put_market)

        return OptionResult(
            call_price=call_market,
            put_price=put_market,
            call_iv=round(call_iv, 4),
            put_iv=round(put_iv, 4),
            parity_diff=round(parity_diff, 2),
            fair_call=round(fair_call, 2),
            fair_put=round(fair_put, 2),
            call_premium_pct=round((call_market / fair_call - 1) * 100, 1) if fair_call > 0 else 0,
            put_premium_pct=round((put_market / fair_put - 1) * 100, 1) if fair_put > 0 else 0,
        )


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def put_call_ratio_analysis(call_vol: float, put_vol: float,
                            call_oi: float = None, put_oi: float = None) -> dict:
    """Put/Call 成交量/未平倉比率分析。
    PCR > 1.2 → 偏空避險需求高; PCR < 0.7 → 偏多。
    """
    result = {}
    if call_vol > 0:
        result["vol_ratio"] = round(put_vol / call_vol, 2)
    else:
        result["vol_ratio"] = None

    if call_oi and put_oi and call_oi > 0:
        result["oi_ratio"] = round(put_oi / call_oi, 2)
    else:
        result["oi_ratio"] = None

    ratio = result.get("oi_ratio") or result.get("vol_ratio")
    if ratio is not None:
        if ratio > 1.2:
            result["signal"] = "偏空避險"
        elif ratio < 0.7:
            result["signal"] = "偏多"
        else:
            result["signal"] = "中性"
    else:
        result["signal"] = "N/A"
    return result
