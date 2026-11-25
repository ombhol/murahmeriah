from __future__ import annotations

import streamlit as st

from config import DEFAULT_WATCHLIST, LIQUIDITY_DAYS_MAP
from data_fetcher import fetch_idx_universe
from ui_components import (
    parse_ticker_input,
    render_chart_panel,
    render_fundamental_screener_section,
    render_watchlist_scanner_section,
)

st.set_page_config(
    page_title="IDX Value, Dividend, Breakout & Money Flow Screener",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Screener Saham BEI — Valuasi, Dividen, Breakout & Money Flow")
st.caption(
    "Pemindaian otomatis seluruh watchlist untuk Konfluensi Prioritas (Breakout + Spike & Akumulasi MF 5H+), plus screening fundamental interaktif."
)

with st.sidebar:
    st.header("1. Sumber Daftar Emiten")
    uploaded_watchlist = st.file_uploader(
        "Upload CSV/Excel (kolom pertama / 'Ticker')",
        type=["csv", "xlsx"],
    )
    ticker_text = st.text_area(
        "Daftar Kode Saham (pisahkan koma/baris)",
        value=", ".join(DEFAULT_WATCHLIST),
        height=110,
    )
    lookback = st.selectbox(
        "Periode Rata-Rata Likuiditas",
        options=list(LIQUIDITY_DAYS_MAP.keys()),
        index=1,
        format_func=lambda x: {
            "5d": "5 Hari Bursa",
            "1mo": "1 Bulan (~20 Hari)",
            "3mo": "3 Bulan (~60 Hari)",
        }[x],
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        refresh_btn = st.button("🔄 Refresh Data", use_container_width=True)
    with col_btn2:
        clear_cache_btn = st.button("🧹 Clear Cache", use_container_width=True)

    if clear_cache_btn:
        st.cache_data.clear()
        st.success("Cache dibersihkan.")

    st.divider()
    st.header("2. Filter Valuasi, Dividen & Risiko")

    pbv_range = st.slider(
        "Rentang PBV (x)", min_value=0.0, max_value=5.0, value=(0.05, 1.50), step=0.05
    )
    min_roe = st.slider(
        "Minimal ROE (%)", min_value=-10.0, max_value=40.0, value=5.0, step=0.5
    )
    min_div_yield = st.slider(
        "Minimal Dividend Yield (%)", min_value=0.0, max_value=20.0, value=0.0, step=0.5
    )
    max_der = st.slider(
        "Maksimal DER (x)", min_value=0.1, max_value=10.0, value=3.0, step=0.1
    )
    min_tx_miliar = st.number_input(
        "Min. Nilai Transaksi Harian (Rp Miliar)",
        min_value=0.0,
        max_value=1000.0,
        value=5.0,
        step=1.0,
    )
    min_mcap_triliun = st.number_input(
        "Min. Market Cap (Rp Triliun)",
        min_value=0.0,
        max_value=1500.0,
        value=10.0,
        step=5.0,
    )
    sort_by = st.selectbox(
        "Urutkan Berdasarkan",
        options=[
            "PBV (Terendah)",
            "Div Yield (Tertinggi)",
            "ROE (Tertinggi)",
            "DER (Terendah)",
            "Likuiditas (Tertinggi)",
        ],
    )

    st.divider()
    st.header("3. Parameter Breakout, Spike & Money Flow")
    show_sr_lines = st.checkbox("Tampilkan Support & Resistance Otomatis", value=True)
    sr_window = st.slider(
        "Sensitivitas Swing S/R (Hari)", min_value=3, max_value=12, value=5, step=1
    )
    show_spike_markers = st.checkbox("Tandai Lonjakan Volume (Volume Spike)", value=True)
    spike_mult = st.slider(
        "Ambang Volume Spike (x Rata-Rata 20H)",
        min_value=1.5,
        max_value=5.0,
        value=2.0,
        step=0.25,
    )
    show_breakouts = st.checkbox("Tandai Breakout Resistance + Volume Spike", value=True)
    bo_lookback = st.slider(
        "Periode Acuan Resistance Breakout (Hari)",
        min_value=10,
        max_value=60,
        value=20,
        step=5,
    )

target_tickers = parse_ticker_input(ticker_text, uploaded_watchlist)

if not target_tickers:
    st.warning("Masukkan minimal satu kode saham di sidebar untuk memulai screening.")
    st.stop()

if refresh_btn:
    st.cache_data.clear()

with st.spinner(f"Memindai {len(target_tickers)} emiten (fundamental, breakout & money flow)..."):
    raw_df, scan_df, failed_tickers = fetch_idx_universe(
        target_tickers,
        lookback_period=lookback,
        spike_multiplier=spike_mult,
        breakout_lookback=bo_lookback,
    )

if raw_df.empty or scan_df.empty:
    st.error("Data gagal ditarik atau tidak ada ticker valid yang ditemukan.")
    st.stop()

available_sectors = sorted(raw_df["Sektor"].dropna().unique().tolist())
selected_sectors = st.sidebar.multiselect(
    "Filter Sektor", options=available_sectors, default=available_sectors
)

selected_from_scan = render_watchlist_scanner_section(
    scan_df=scan_df,
    selected_sectors=selected_sectors,
)

st.divider()

selected_from_fund = render_fundamental_screener_section(
    raw_df=raw_df,
    selected_sectors=selected_sectors,
    pbv_range=pbv_range,
    min_roe=min_roe,
    min_div_yield=min_div_yield,
    max_der=max_der,
    min_tx_miliar=min_tx_miliar,
    min_mcap_triliun=min_mcap_triliun,
    sort_by=sort_by,
)

active_chart_target = selected_from_scan or selected_from_fund
if active_chart_target is not None:
    render_chart_panel(
        ticker=active_chart_target[0],
        emiten_name=active_chart_target[1],
        show_sr_lines=show_sr_lines,
        sr_window=sr_window,
        show_spike_markers=show_spike_markers,
        spike_mult=spike_mult,
        show_breakouts=show_breakouts,
        bo_lookback=bo_lookback,
    )

if failed_tickers:
    with st.expander(f"⚠️ {len(failed_tickers)} ticker tidak memiliki data lengkap / dilewati"):
        st.write(", ".join(failed_tickers))
