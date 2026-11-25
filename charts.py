from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_candlestick_figure(
    ticker: str,
    df_tech: pd.DataFrame,
    supports: list[float],
    resistances: list[float],
    show_sr: bool = True,
    show_spikes: bool = True,
    show_breakouts: bool = True,
) -> go.Figure:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.56, 0.22, 0.22],
    )

    fig.add_trace(
        go.Candlestick(
            x=df_tech.index,
            open=df_tech["Open"],
            high=df_tech["High"],
            low=df_tech["Low"],
            close=df_tech["Close"],
            name=ticker,
            increasing_line_color="#16a34a",
            increasing_fillcolor="#16a34a",
            decreasing_line_color="#dc2626",
            decreasing_fillcolor="#dc2626",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=df_tech.index,
            y=df_tech["ma20"],
            mode="lines",
            name="MA 20",
            line=dict(color="#2563eb", width=1.4),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df_tech.index,
            y=df_tech["ma50"],
            mode="lines",
            name="MA 50",
            line=dict(color="#f59e0b", width=1.4),
        ),
        row=1,
        col=1,
    )

    if show_sr:
        for idx_s, s_lvl in enumerate(supports, start=1):
            fig.add_hline(
                y=s_lvl,
                line_dash="dash",
                line_color="#10b981",
                line_width=1.3,
                annotation_text=f"S{idx_s}: Rp{int(s_lvl):,}",
                annotation_position="bottom left",
                annotation_font=dict(color="#059669", size=10),
                row=1,
                col=1,
            )
        for idx_r, r_lvl in enumerate(resistances, start=1):
            fig.add_hline(
                y=r_lvl,
                line_dash="dot",
                line_color="#ef4444",
                line_width=1.3,
                annotation_text=f"R{idx_r}: Rp{int(r_lvl):,}",
                annotation_position="top left",
                annotation_font=dict(color="#dc2626", size=10),
                row=1,
                col=1,
            )

    if show_breakouts:
        bo_df = df_tech[df_tech["is_breakout_spike"]]
        if not bo_df.empty:
            bo_labels = [
                f"BO {r_val:.1f}x ({chg:+.1f}%)" if pd.notna(chg) else f"BO {r_val:.1f}x"
                for r_val, chg in zip(bo_df["vol_ratio"], bo_df["pct_change"])
            ]
            fig.add_trace(
                go.Scatter(
                    x=bo_df.index,
                    y=bo_df["High"] * 1.012,
                    mode="markers+text",
                    name="Breakout + Spike",
                    text=bo_labels,
                    textposition="top center",
                    textfont=dict(size=10, color="#7c3aed"),
                    marker=dict(
                        symbol="star",
                        size=11,
                        color="#8b5cf6",
                        line=dict(color="#4c1d95", width=1),
                    ),
                ),
                row=1,
                col=1,
            )

    vol_lot = df_tech["Volume"] / 100.0
    vol_ma_lot = df_tech["vol_ma"] / 100.0
    bar_colors = [
        "#16a34a" if c >= o else "#dc2626"
        for o, c in zip(df_tech["Open"], df_tech["Close"])
    ]

    fig.add_trace(
        go.Bar(
            x=df_tech.index,
            y=vol_lot,
            name="Volume (Lot)",
            marker_color=bar_colors,
            opacity=0.72,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df_tech.index,
            y=vol_ma_lot,
            mode="lines",
            name="Avg Vol MA20",
            line=dict(color="#6366f1", width=1.3, dash="shortdash"),
        ),
        row=2,
        col=1,
    )

    if show_spikes:
        spikes = df_tech[df_tech["is_spike"]]
        if not spikes.empty:
            spike_lot = spikes["Volume"] / 100.0
            spike_labels = [f"{r_val:.1f}x" for r_val in spikes["vol_ratio"]]
            fig.add_trace(
                go.Scatter(
                    x=spikes.index,
                    y=spike_lot,
                    mode="markers+text",
                    name="Volume Spike",
                    text=spike_labels,
                    textposition="top center",
                    textfont=dict(size=9, color="#b45309"),
                    marker=dict(
                        symbol="diamond",
                        size=8,
                        color="#f59e0b",
                        line=dict(color="#78350f", width=1),
                    ),
                ),
                row=2,
                col=1,
            )

    mf_colors = [
        "#10b981" if val >= 0 else "#f43f5e"
        for val in df_tech["money_flow_m"]
    ]
    fig.add_trace(
        go.Bar(
            x=df_tech.index,
            y=df_tech["money_flow_m"],
            name="Est. Money Flow Harian (Rp Jt)",
            marker_color=mf_colors,
            opacity=0.75,
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df_tech.index,
            y=df_tech["cum_money_flow_m"],
            mode="lines",
            name="Kumulatif Money Flow (Rp Jt)",
            line=dict(color="#0ea5e9", width=1.6),
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=f"Analisis Teknikal & Money Flow — {ticker}.JK",
        xaxis_rangeslider_visible=False,
        height=720,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text="Harga (Rp)", row=1, col=1)
    fig.update_yaxes(title_text="Vol (Lot)", row=2, col=1)
    fig.update_yaxes(title_text="Flow (Rp Jt)", row=3, col=1)
    return fig
