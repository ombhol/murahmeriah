from __future__ import annotations

import numpy as np
import pandas as pd


def calc_pbv(info: dict, last_price: float | None) -> float | None:
    pb = info.get("priceToBook")
    if isinstance(pb, (int, float)) and pb > 0:
        return float(pb)

    bvps = info.get("bookValue")
    if (
        isinstance(bvps, (int, float))
        and bvps > 0
        and isinstance(last_price, (int, float))
        and last_price > 0
    ):
        return float(last_price) / float(bvps)

    return None


def calc_der(info: dict) -> float | None:
    raw_dte = info.get("debtToEquity")
    if not isinstance(raw_dte, (int, float)):
        return None
    val = float(raw_dte)
    if val < 0:
        return None
    return round(val / 100.0, 2) if val > 10.0 else round(val, 2)


def calc_div_yield_pct(info: dict, last_price: float | None) -> float | None:
    dy = info.get("dividendYield")
    if isinstance(dy, (int, float)) and dy >= 0:
        pct = float(dy) * 100.0 if float(dy) <= 1.0 else float(dy)
        if pct <= 50.0:
            return round(pct, 2)

    div_rate = info.get("dividendRate")
    if (
        isinstance(div_rate, (int, float))
        and div_rate >= 0
        and isinstance(last_price, (int, float))
        and last_price > 0
    ):
        return round((float(div_rate) / float(last_price)) * 100.0, 2)

    return 0.0


def calc_liquidity(
    hist: pd.DataFrame, period_days: int = 20
) -> tuple[float | None, float | None, float | None]:
    if hist.empty or "Close" not in hist or "Volume" not in hist:
        return None, None, None

    close = hist["Close"].dropna()
    volume = hist["Volume"].dropna()
    if close.empty or volume.empty:
        return None, None, None

    tx_value = (hist["Close"] * hist["Volume"]).dropna()
    if tx_value.empty:
        return None, None, None

    return (
        float(close.iloc[-1]),
        float(volume.tail(period_days).mean()),
        float(tx_value.tail(period_days).mean()),
    )


def cluster_levels(
    levels: list[float], tolerance_pct: float = 0.015, max_items: int = 3
) -> list[float]:
    if not levels:
        return []
    sorted_lvls = sorted(levels)
    clusters: list[list[float]] = [[sorted_lvls[0]]]

    for price in sorted_lvls[1:]:
        ref = float(np.mean(clusters[-1]))
        if ref > 0 and abs(price - ref) / ref <= tolerance_pct:
            clusters[-1].append(price)
        else:
            clusters.append([price])

    clusters.sort(key=lambda c: (-len(c), float(np.mean(c))))
    selected = [round(float(np.mean(c)), 0) for c in clusters[:max_items]]
    return sorted(selected)


def detect_support_resistance(
    df_ohlc: pd.DataFrame, window: int = 5, max_levels_each: int = 2
) -> tuple[list[float], list[float]]:
    if len(df_ohlc) < (2 * window + 1):
        low_val = round(float(df_ohlc["Low"].min()), 0)
        high_val = round(float(df_ohlc["High"].max()), 0)
        return [low_val], [high_val]

    highs = df_ohlc["High"].to_numpy(dtype=float)
    lows = df_ohlc["Low"].to_numpy(dtype=float)
    last_close = float(df_ohlc["Close"].iloc[-1])

    raw_supports: list[float] = []
    raw_resistances: list[float] = []

    for i in range(window, len(df_ohlc) - window):
        if np.all(lows[i] <= lows[i - window : i]) and np.all(
            lows[i] <= lows[i + 1 : i + window + 1]
        ):
            raw_supports.append(float(lows[i]))
        if np.all(highs[i] >= highs[i - window : i]) and np.all(
            highs[i] >= highs[i + 1 : i + window + 1]
        ):
            raw_resistances.append(float(highs[i]))

    supports = [p for p in raw_supports if p <= last_close * 1.01]
    resistances = [p for p in raw_resistances if p >= last_close * 0.99]

    if not supports:
        supports = [float(np.percentile(lows, 15))]
    if not resistances:
        resistances = [float(np.percentile(highs, 85))]

    clustered_supports = cluster_levels(supports, tolerance_pct=0.015, max_items=max_levels_each)
    clustered_resistances = cluster_levels(
        resistances, tolerance_pct=0.015, max_items=max_levels_each
    )
    return clustered_supports, clustered_resistances


def enrich_technical_indicators(
    df_ohlc: pd.DataFrame,
    vol_ma_window: int = 20,
    spike_multiplier: float = 2.0,
    breakout_lookback: int = 20,
) -> pd.DataFrame:
    out = df_ohlc.copy()
    out["pct_change"] = out["Close"].pct_change() * 100.0
    out["ma20"] = out["Close"].rolling(window=20, min_periods=1).mean()
    out["ma50"] = out["Close"].rolling(window=50, min_periods=1).mean()

    vol_ma = out["Volume"].rolling(window=vol_ma_window, min_periods=5).mean()
    out["vol_ma"] = vol_ma
    out["vol_ratio"] = np.where(vol_ma > 0, out["Volume"] / vol_ma, np.nan)
    out["is_spike"] = (out["vol_ratio"] >= spike_multiplier) & (out["Volume"] > 0)

    prior_res = out["High"].shift(1).rolling(window=breakout_lookback, min_periods=5).max()
    out["prior_resistance"] = prior_res
    out["is_raw_breakout"] = (out["Close"] > prior_res) & prior_res.notna()
    out["is_breakout_spike"] = out["is_raw_breakout"] & out["is_spike"]

    hl_range = (out["High"] - out["Low"]).to_numpy(dtype=float)
    close_arr = out["Close"].to_numpy(dtype=float)
    low_arr = out["Low"].to_numpy(dtype=float)
    high_arr = out["High"].to_numpy(dtype=float)
    vol_arr = out["Volume"].to_numpy(dtype=float)

    mfm = np.where(
        hl_range > 0,
        ((close_arr - low_arr) - (high_arr - close_arr)) / np.where(hl_range > 0, hl_range, 1.0),
        0.0,
    )
    tx_idr = close_arr * vol_arr
    money_flow_idr = mfm * tx_idr

    out["mfm"] = mfm
    out["money_flow_m"] = money_flow_idr / 1e9
    out["cum_money_flow_m"] = pd.Series(money_flow_idr, index=out.index).cumsum() / 1e9
    return out
