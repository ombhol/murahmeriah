from __future__ import annotations

import time

import pandas as pd
import streamlit as st
import yfinance as yf

from config import LIQUIDITY_DAYS_MAP
from indicators import (
    calc_der,
    calc_div_yield_pct,
    calc_liquidity,
    calc_pbv,
    enrich_technical_indicators,
)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ohlcv_chart_data(ticker: str, period: str = "6mo") -> pd.DataFrame:
    symbol = f"{ticker.strip().upper()}.JK"
    df = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=False)
    if df.empty:
        return pd.DataFrame()
    df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
    df.index = pd.to_datetime(df.index)
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_idx_universe(
    tickers: tuple[str, ...],
    lookback_period: str = "1mo",
    spike_multiplier: float = 2.0,
    breakout_lookback: int = 20,
    request_delay: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    liq_days = LIQUIDITY_DAYS_MAP.get(lookback_period, 20)

    fund_rows: list[dict] = []
    scan_rows: list[dict] = []
    failed: list[str] = []

    for raw_code in tickers:
        code = raw_code.strip().upper()
        if not code:
            continue
        symbol = code if code.endswith(".JK") else f"{code}.JK"

        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="6mo", interval="1d", auto_adjust=False)
            if hist.empty or not {"Open", "High", "Low", "Close", "Volume"}.issubset(hist.columns):
                failed.append(code.replace(".JK", ""))
                continue

            hist = hist.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
            hist.index = pd.to_datetime(hist.index)

            last_price, avg_vol, avg_tx_idr = calc_liquidity(hist, period_days=liq_days)
            if last_price is None or avg_tx_idr is None:
                failed.append(code.replace(".JK", ""))
                continue

            info = t.info or {}
            pbv = calc_pbv(info, last_price)
            roe = info.get("returnOnEquity")
            per = info.get("trailingPE")
            der = calc_der(info)
            div_yield = calc_div_yield_pct(info, last_price)
            mcap = info.get("marketCap")
            sector = info.get("sector") or "-"
            name = info.get("shortName") or code.replace(".JK", "")
            ticker_clean = code.replace(".JK", "")

            fund_rows.append(
                {
                    "Ticker": ticker_clean,
                    "Emiten": name,
                    "Sektor": sector,
                    "Harga (Rp)": round(last_price, 0),
                    "PBV (x)": round(pbv, 2) if pbv is not None else None,
                    "PER (x)": round(float(per), 2) if isinstance(per, (int, float)) and per > 0 else None,
                    "ROE (%)": round(float(roe) * 100, 2) if isinstance(roe, (int, float)) else None,
                    "DER (x)": der,
                    "Div Yield (%)": div_yield,
                    "Avg Tx (Rp M)": round(avg_tx_idr / 1e9, 2),
                    "Avg Vol (Lot)": round((avg_vol or 0.0) / 100.0, 0),
                    "Market Cap (Rp T)": round(float(mcap) / 1e12, 2) if isinstance(mcap, (int, float)) else 0.0,
                }
            )

            df_tech = enrich_technical_indicators(
                hist,
                vol_ma_window=20,
                spike_multiplier=spike_multiplier,
                breakout_lookback=breakout_lookback,
            )

            last_pct = float(df_tech["pct_change"].iloc[-1]) if pd.notna(df_tech["pct_change"].iloc[-1]) else 0.0
            last_vol_ratio = float(df_tech["vol_ratio"].iloc[-1]) if pd.notna(df_tech["vol_ratio"].iloc[-1]) else 0.0
            is_bo_spike_today = bool(df_tech["is_breakout_spike"].iloc[-1])
            is_spike_today = bool(df_tech["is_spike"].iloc[-1])
            bo_spike_5d = bool(df_tech["is_breakout_spike"].tail(5).any())
            mf_5d_m = float(df_tech["money_flow_m"].tail(5).sum())
            mf_today_m = float(df_tech["money_flow_m"].iloc[-1])

            is_priority_confluence = (bo_spike_5d or is_bo_spike_today) and (mf_5d_m > 0)

            if is_priority_confluence and is_bo_spike_today:
                status_sinyal = "⭐ Konfluensi Prioritas (BO+Spike Hari Ini & MF 5H+)"
            elif is_priority_confluence:
                status_sinyal = "⭐ Konfluensi Prioritas (BO+Spike 5H & MF 5H+)"
            elif is_bo_spike_today:
                status_sinyal = "🚀 Breakout + Spike (Hari Ini)"
            elif bo_spike_5d:
                status_sinyal = "✨ Breakout + Spike (5H)"
            elif is_spike_today:
                status_sinyal = "⚡ Volume Spike (Hari Ini)"
            elif mf_5d_m > 0:
                status_sinyal = "🟢 Akumulasi MF 5H"
            elif mf_5d_m < 0:
                status_sinyal = "🔴 Distribusi MF 5H"
            else:
                status_sinyal = "⚪ Netral"

            scan_rows.append(
                {
                    "Ticker": ticker_clean,
                    "Emiten": name,
                    "Sektor": sector,
                    "Harga (Rp)": round(last_price, 0),
                    "% Chg": round(last_pct, 2),
                    "Vol Ratio (x)": round(last_vol_ratio, 2),
                    "Konfluensi Prioritas": is_priority_confluence,
                    "BO+Spike Hari Ini": is_bo_spike_today,
                    "BO+Spike 5H": bo_spike_5d,
                    "MF 5H (Rp Jt)": round(mf_5d_m, 1),
                    "MF Hari Ini (Rp Jt)": round(mf_today_m, 1),
                    "Status Sinyal": status_sinyal,
                }
            )

        except Exception:
            failed.append(code.replace(".JK", ""))

        time.sleep(request_delay)

    return pd.DataFrame(fund_rows), pd.DataFrame(scan_rows), failed
