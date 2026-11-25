from __future__ import annotations

DEFAULT_WATCHLIST: tuple[str, ...] = (
    "SMGR", "BBNI", "UNTR", "ADRO", "PTBA", "INDY", "PGAS", "MEDC",
    "INKP", "TLKM", "EXCL", "ISAT", "ANTM", "BUMI", "ASII", "BMRI",
    "BBRI", "BBCA", "ITMG", "HRUM", "INDF", "ICBP", "KLBF", "CPIN",
    "JPFA", "INTP", "CTRA", "BSDE", "PWON", "SMRA", "AKRA", "ERAA",
)

LIQUIDITY_DAYS_MAP: dict[str, int] = {
    "5d": 5,
    "1mo": 20,
    "3mo": 60,
}

CHART_PERIOD_LABELS: dict[str, str] = {
    "1mo": "1 Bulan",
    "3mo": "3 Bulan",
    "6mo": "6 Bulan",
    "1y": "1 Tahun",
    "2y": "2 Tahun",
}
