from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from charts import build_candlestick_figure
from config import CHART_PERIOD_LABELS
from data_fetcher import fetch_ohlcv_chart_data
from indicators import detect_support_resistance, enrich_technical_indicators


def parse_ticker_input(raw_text: str, uploaded_file) -> tuple[str, ...]:
    codes: list[str] = []

    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df_up = pd.read_csv(uploaded_file)
            else:
                df_up = pd.read_excel(uploaded_file)
            col = "Ticker" if "Ticker" in df_up.columns else df_up.columns[0]
            codes.extend(df_up[col].dropna().astype(str).tolist())
        except Exception as exc:
            st.sidebar.error(f"Gagal membaca file: {exc}")

    if raw_text.strip():
        tokens = raw_text.replace("\n", ",").replace(";", ",").split(",")
        codes.extend(tokens)

    seen: set[str] = set()
    cleaned: list[str] = []
    for c in codes:
        sym = c.strip().upper().replace(".JK", "")
        if sym and sym not in seen:
            seen.add(sym)
            cleaned.append(sym)
    return tuple(cleaned)


def render_watchlist_scanner_section(
    scan_df: pd.DataFrame,
    selected_sectors: list[str],
) -> tuple[str, str] | None:
    st.subheader(
        "⚡ Pemindaian Otomatis Watchlist — Konfluensi Prioritas, Breakout + Spike & Money Flow 5H"
    )
    st.caption(
        "Konfluensi Prioritas = (Breakout + Volume Spike Hari Ini atau 5H) sekaligus akumulasi Money Flow 5 hari positif (MF 5H > 0)."
    )

    fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
    with fcol1:
        signal_filter = st.selectbox(
            "Filter Sinyal Pemindaian Watchlist",
            options=[
                "Semua Watchlist",
                "Konfluensi Prioritas (BO+Spike & MF 5H+)",
                "Breakout + Spike (Hari Ini)",
                "Breakout + Spike (5 Hari Terakhir)",
                "Akumulasi Money Flow 5H (Positif > 0)",
            ],
        )
    with fcol2:
        min_mf_5d_filter = st.number_input(
            "Min. Akumulasi MF 5H (Rp Juta)",
            min_value=-100000.0,
            max_value=100000.0,
            value=0.0,
            step=500.0,
        )
    with fcol3:
        scan_sort = st.selectbox(
            "Urutan Pemindaian",
            options=[
                "Konfluensi Prioritas Dulu",
                "Breakout Dulu -> MF 5H",
                "MF 5H Tertinggi",
                "Vol Ratio Tertinggi",
                "% Chg Tertinggi",
            ],
        )

    scan_view_df = scan_df[scan_df["Sektor"].isin(selected_sectors)].copy()
    if signal_filter == "Konfluensi Prioritas (BO+Spike & MF 5H+)":
        scan_view_df = scan_view_df[scan_view_df["Konfluensi Prioritas"]]
    elif signal_filter == "Breakout + Spike (Hari Ini)":
        scan_view_df = scan_view_df[scan_view_df["BO+Spike Hari Ini"]]
    elif signal_filter == "Breakout + Spike (5 Hari Terakhir)":
        scan_view_df = scan_view_df[scan_view_df["BO+Spike 5H"]]
    elif signal_filter == "Akumulasi Money Flow 5H (Positif > 0)":
        scan_view_df = scan_view_df[scan_view_df["MF 5H (Rp Jt)"] > 0]

    if min_mf_5d_filter != 0.0:
        scan_view_df = scan_view_df[scan_view_df["MF 5H (Rp Jt)"] >= min_mf_5d_filter]

    if scan_sort == "Konfluensi Prioritas Dulu":
        scan_view_df = scan_view_df.sort_values(
            by=["Konfluensi Prioritas", "BO+Spike Hari Ini", "MF 5H (Rp Jt)"],
            ascending=[False, False, False],
        )
    elif scan_sort == "Breakout Dulu -> MF 5H":
        scan_view_df = scan_view_df.sort_values(
            by=["BO+Spike Hari Ini", "BO+Spike 5H", "MF 5H (Rp Jt)"],
            ascending=[False, False, False],
        )
    elif scan_sort == "MF 5H Tertinggi":
        scan_view_df = scan_view_df.sort_values(by="MF 5H (Rp Jt)", ascending=False)
    elif scan_sort == "Vol Ratio Tertinggi":
        scan_view_df = scan_view_df.sort_values(by="Vol Ratio (x)", ascending=False)
    else:
        scan_view_df = scan_view_df.sort_values(by="% Chg", ascending=False)

    scan_view_df = scan_view_df.reset_index(drop=True)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Konfluensi Prioritas", f"{int(scan_df['Konfluensi Prioritas'].sum())} emiten")
    s2.metric("Breakout + Spike (Hari Ini)", f"{int(scan_df['BO+Spike Hari Ini'].sum())} emiten")
    s3.metric("Breakout + Spike (5 Hari)", f"{int(scan_df['BO+Spike 5H'].sum())} emiten")
    s4.metric("Akumulasi MF 5H Positif", f"{int((scan_df['MF 5H (Rp Jt)'] > 0).sum())} / {len(scan_df)} emiten")

    if scan_view_df.empty:
        st.info("Tidak ada saham pada watchlist yang cocok dengan filter sinyal pemindaian saat ini.")
        return None

    scan_event = st.dataframe(
        scan_view_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="watchlist_scan_table",
        column_config={
            "Ticker": st.column_config.TextColumn("Kode", width="small"),
            "Harga (Rp)": st.column_config.NumberColumn("Harga (Rp)", format="Rp %d"),
            "% Chg": st.column_config.NumberColumn("% Chg", format="%+.2f%%"),
            "Vol Ratio (x)": st.column_config.NumberColumn("Vol Ratio", format="%.2fx"),
            "Konfluensi Prioritas": st.column_config.CheckboxColumn("Konfluensi Prioritas"),
            "BO+Spike Hari Ini": st.column_config.CheckboxColumn("BO+Spike Hari Ini"),
            "BO+Spike 5H": st.column_config.CheckboxColumn("BO+Spike 5H"),
            "MF 5H (Rp Jt)": st.column_config.NumberColumn("MF 5H (Rp Jt)", format="%+.1f"),
            "MF Hari Ini (Rp Jt)": st.column_config.NumberColumn("MF Hari Ini (Rp Jt)", format="%+.1f"),
        },
    )

    scan_csv_buffer = io.StringIO()
    scan_view_df.to_csv(scan_csv_buffer, index=False)
    st.download_button(
        label="⬇️ Download Hasil Pemindaian Watchlist (.CSV)",
        data=scan_csv_buffer.getvalue(),
        file_name="hasil_pemindaian_watchlist_idx.csv",
        mime="text/csv",
        key="download_watchlist_scan_csv",
    )

    scan_rows_sel = scan_event.selection.rows if scan_event and scan_event.selection else []
    if scan_rows_sel:
        r_pick = scan_view_df.iloc[scan_rows_sel[0]]
        return (str(r_pick["Ticker"]), str(r_pick["Emiten"]))
    return None


def render_fundamental_screener_section(
    raw_df: pd.DataFrame,
    selected_sectors: list[str],
    pbv_range: tuple[float, float],
    min_roe: float,
    min_div_yield: float,
    max_der: float,
    min_tx_miliar: float,
    min_mcap_triliun: float,
    sort_by: str,
) -> tuple[str, str] | None:
    filtered_df = raw_df.dropna(subset=["PBV (x)", "ROE (%)"]).copy()
    filtered_df["DER_cmp"] = filtered_df["DER (x)"].fillna(999.0)
    filtered_df["Div_cmp"] = filtered_df["Div Yield (%)"].fillna(0.0)

    filtered_df = filtered_df[
        (filtered_df["PBV (x)"] >= pbv_range[0])
        & (filtered_df["PBV (x)"] <= pbv_range[1])
        & (filtered_df["ROE (%)"] >= min_roe)
        & (filtered_df["Div_cmp"] >= min_div_yield)
        & (filtered_df["DER_cmp"] <= max_der)
        & (filtered_df["Avg Tx (Rp M)"] >= min_tx_miliar)
        & (filtered_df["Market Cap (Rp T)"] >= min_mcap_triliun)
        & (filtered_df["Sektor"].isin(selected_sectors))
    ].drop(columns=["DER_cmp", "Div_cmp"])

    sort_map = {
        "PBV (Terendah)": (["PBV (x)", "ROE (%)"], [True, False]),
        "Div Yield (Tertinggi)": (["Div Yield (%)", "PBV (x)"], [False, True]),
        "ROE (Tertinggi)": (["ROE (%)", "PBV (x)"], [False, True]),
        "DER (Terendah)": (["DER (x)", "PBV (x)"], [True, True]),
        "Likuiditas (Tertinggi)": (["Avg Tx (Rp M)", "PBV (x)"], [False, True]),
    }
    sort_cols, sort_asc = sort_map[sort_by]
    filtered_df = filtered_df.sort_values(
        by=sort_cols, ascending=sort_asc, na_position="last"
    ).reset_index(drop=True)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Lolos Filter Valuasi", f"{len(filtered_df)} / {len(raw_df)}")
    m2.metric("Median PBV", f"{filtered_df['PBV (x)'].median():.2f}x" if not filtered_df.empty else "-")
    m3.metric("Median ROE", f"{filtered_df['ROE (%)'].median():.2f}%" if not filtered_df.empty else "-")
    m4.metric(
        "Median Div Yield",
        f"{filtered_df['Div Yield (%)'].median():.2f}%" if not filtered_df.empty else "-",
    )
    m5.metric(
        "Median DER",
        f"{filtered_df['DER (x)'].dropna().median():.2f}x"
        if not filtered_df["DER (x)"].dropna().empty
        else "-",
    )

    if filtered_df.empty:
        st.info("Tidak ada saham yang memenuhi kombinasi filter valuasi/dividen/DER saat ini.")
        return None

    st.subheader("Hasil Screening Fundamental & Likuiditas (Klik 1 Baris untuk Buka Chart)")
    fund_event = st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="fundamental_screener_table",
        column_config={
            "Ticker": st.column_config.TextColumn("Kode", width="small"),
            "Harga (Rp)": st.column_config.NumberColumn("Harga (Rp)", format="Rp %d"),
            "PBV (x)": st.column_config.NumberColumn("PBV (x)", format="%.2fx"),
            "PER (x)": st.column_config.NumberColumn("PER (x)", format="%.2fx"),
            "ROE (%)": st.column_config.NumberColumn("ROE (%)", format="%.2f%%"),
            "DER (x)": st.column_config.NumberColumn("DER (x)", format="%.2fx"),
            "Div Yield (%)": st.column_config.NumberColumn("Div Yield (%)", format="%.2f%%"),
            "Avg Tx (Rp M)": st.column_config.NumberColumn("Avg Tx/Hari (Rp M)", format="%.2f"),
            "Avg Vol (Lot)": st.column_config.NumberColumn("Avg Vol (Lot)", format="%d"),
            "Market Cap (Rp T)": st.column_config.NumberColumn("Market Cap (Rp T)", format="%.2f"),
        },
    )

    csv_buffer = io.StringIO()
    filtered_df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="⬇️ Download Hasil Screening Fundamental (.CSV)",
        data=csv_buffer.getvalue(),
        file_name="hasil_screener_idx_lengkap.csv",
        mime="text/csv",
        key="download_fundamental_screener_csv",
    )

    fund_rows_sel = fund_event.selection.rows if fund_event and fund_event.selection else []
    if fund_rows_sel:
        f_pick = filtered_df.iloc[fund_rows_sel[0]]
        return (str(f_pick["Ticker"]), str(f_pick["Emiten"]))
    return None


def render_chart_panel(
    ticker: str,
    emiten_name: str,
    show_sr_lines: bool,
    sr_window: int,
    show_spike_markers: bool,
    spike_mult: float,
    show_breakouts: bool,
    bo_lookback: int,
) -> None:
    st.divider()
    hdr_col, range_col = st.columns([3, 1])
    with hdr_col:
        st.subheader(f"📈 Analisis Harian: {ticker} — {emiten_name}")
    with range_col:
        chart_period = st.selectbox(
            "Rentang Grafik",
            options=list(CHART_PERIOD_LABELS.keys()),
            index=2,
            key=f"candlestick_period_{ticker}",
            format_func=lambda p: CHART_PERIOD_LABELS[p],
        )

    with st.spinner(f"Menghitung indikator {ticker}.JK..."):
        df_ohlc = fetch_ohlcv_chart_data(ticker, period=chart_period)

    if df_ohlc.empty:
        st.warning(f"Data OHLCV harian untuk {ticker}.JK tidak tersedia.")
        return

    df_tech = enrich_technical_indicators(
        df_ohlc,
        vol_ma_window=20,
        spike_multiplier=spike_mult,
        breakout_lookback=bo_lookback,
    )
    supports, resistances = detect_support_resistance(
        df_tech, window=sr_window, max_levels_each=2
    )

    last_close = float(df_tech["Close"].iloc[-1])
    last_pct = float(df_tech["pct_change"].iloc[-1]) if pd.notna(df_tech["pct_change"].iloc[-1]) else 0.0
    last_vol_ratio = float(df_tech["vol_ratio"].iloc[-1]) if pd.notna(df_tech["vol_ratio"].iloc[-1]) else 0.0
    last_mf_m = float(df_tech["money_flow_m"].iloc[-1])
    last_mf_5d_m = float(df_tech["money_flow_m"].tail(5).sum())
    bo_spike_count = int(df_tech["is_breakout_spike"].sum())
    last_is_bo_spike = bool(df_tech["is_breakout_spike"].iloc[-1])

    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric("Penutupan Terakhir", f"Rp{int(round(last_close)):,}", f"{last_pct:+.2f}%")
    t2.metric("Rasio Volume Hari Ini", f"{last_vol_ratio:.2f}x", f"Spike >= {spike_mult:.2f}x")
    t3.metric(
        "Breakout + Spike",
        f"{bo_spike_count} sinyal",
        "Sinyal Aktif Hari Ini!" if last_is_bo_spike else f"Acuan {bo_lookback}H",
    )
    t4.metric("Est. Money Flow Hari Ini", f"Rp {last_mf_m:+,.1f} Jt", f"5H: Rp {last_mf_5d_m:+,.1f} Jt")
    t5.metric(
        "S / R Utama",
        f"S1: Rp{int(supports[0]):,}" if supports else "-",
        f"R1: Rp{int(resistances[0]):,}" if resistances else "-",
    )

    fig_candle = build_candlestick_figure(
        ticker=ticker,
        df_tech=df_tech,
        supports=supports,
        resistances=resistances,
        show_sr=show_sr_lines,
        show_spikes=show_spike_markers,
        show_breakouts=show_breakouts,
    )
    st.plotly_chart(fig_candle, use_container_width=True)

    bo_rows = df_tech[df_tech["is_breakout_spike"]].sort_index(ascending=False)
    if not bo_rows.empty:
        with st.expander(
            f"🚀 Riwayat Breakout Resistance + Volume Spike ({len(bo_rows)} Hari Terkonfirmasi)"
        ):
            bo_view = pd.DataFrame(
                {
                    "Tanggal": bo_rows.index.strftime("%Y-%m-%d"),
                    "Close (Rp)": bo_rows["Close"].round(0).astype(int),
                    "Prev Res (Rp)": bo_rows["prior_resistance"].round(0).astype(int),
                    "Perubahan (%)": bo_rows["pct_change"].round(2),
                    "Rasio Vol (x)": bo_rows["vol_ratio"].round(2),
                    "Est. Money Flow (Rp Jt)": bo_rows["money_flow_m"].round(1),
                }
            )
            st.dataframe(bo_view, use_container_width=True, hide_index=True)

    spike_rows = df_tech[df_tech["is_spike"]].sort_index(ascending=False)
    if not spike_rows.empty:
        with st.expander(f"⚡ Riwayat Lonjakan Volume ({len(spike_rows)} Hari Terdeteksi)"):
            spike_view = pd.DataFrame(
                {
                    "Tanggal": spike_rows.index.strftime("%Y-%m-%d"),
                    "Close (Rp)": spike_rows["Close"].round(0).astype(int),
                    "Perubahan (%)": spike_rows["pct_change"].round(2),
                    "Volume (Lot)": (spike_rows["Volume"] / 100.0).round(0).astype(int),
                    "Rasio Vol (x)": spike_rows["vol_ratio"].round(2),
                    "Est. Money Flow (Rp Jt)": spike_rows["money_flow_m"].round(1),
                }
            )
            st.dataframe(spike_view, use_container_width=True, hide_index=True)
