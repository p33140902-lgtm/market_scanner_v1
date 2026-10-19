import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
import streamlit as st

APP_TITLE = "Market Scanner — v1"
BINANCE_BASE = "https://data-api.binance.vision"
CRYPTO_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "TRXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "LTCUSDT",
]
INTERVALS = {"M15": "15m", "H1": "1h", "H4": "4h", "D1": "1d"}


@st.cache_data(ttl=60, show_spinner=False)
def get_klines(symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
    """Fetch public Binance Spot candles; no API key is required for public market data."""
    response = requests.get(
        f"{BINANCE_BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=15,
    )
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"No candle data returned for {symbol}")

    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(raw, columns=columns)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_numeric(df["close_time"], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close", "volume", "close_time"])

    # Exclude an unfinished candle so rankings use completed candles only.
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    if len(df) and int(df.iloc[-1]["close_time"]) > now_ms:
        df = df.iloc[:-1]
    return df.reset_index(drop=True)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()

    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi14"] = 100 - (100 / (1 + rs))

    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    df["atr14_pct"] = true_range.rolling(14).mean() / df["close"] * 100
    df["vol_avg20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_avg20"].replace(0, np.nan)
    return df


def analyze_symbol(symbol: str, interval: str) -> dict:
    df = add_indicators(get_klines(symbol, interval))
    if len(df) < 60:
        raise ValueError("Belum cukup candle selesai (minimal 60)")
    last, prev = df.iloc[-1], df.iloc[-2]
    score, reasons = 0, []

    checks = [
        (last["close"] > last["ema20"], "Harga di atas EMA20"),
        (last["ema20"] > last["ema50"], "EMA20 di atas EMA50"),
        (50 <= last["rsi14"] <= 68, "RSI berada di 50–68"),
        (pd.notna(last["vol_ratio"]) and last["vol_ratio"] >= 1.2, "Volume ≥ 1,2× rata-rata"),
        (last["close"] > prev["close"], "Close lebih tinggi dari candle sebelumnya"),
    ]
    for passed, reason in checks:
        if passed:
            score += 1
            reasons.append(reason)

    return {
        "Simbol": symbol,
        "Close": float(last["close"]),
        "Perubahan %": float((last["close"] / prev["close"] - 1) * 100),
        "RSI 14": round(float(last["rsi14"]), 2) if pd.notna(last["rsi14"]) else None,
        "ATR %": round(float(last["atr14_pct"]), 3) if pd.notna(last["atr14_pct"]) else None,
        "Volume × rata-rata": round(float(last["vol_ratio"]), 2) if pd.notna(last["vol_ratio"]) else None,
        "Skor / 5": score,
        "Alasan": "; ".join(reasons) if reasons else "Belum memenuhi kondisi contoh",
        "Candle terakhir (UTC)": last["open_time"].strftime("%Y-%m-%d %H:%M"),
    }


st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title("🔎 Market Scanner — v1")
st.caption("Prototype edukasi • Candle publik Binance Spot • Bukan rekomendasi transaksi")

with st.sidebar:
    st.header("Pengaturan scan")
    timeframe_label = st.selectbox("Timeframe", list(INTERVALS.keys()), index=0)
    selected_symbols = st.multiselect(
        "Pasangan crypto USDT",
        CRYPTO_SYMBOLS,
        default=CRYPTO_SYMBOLS[:5],
    )
    st.caption(
        "Versi awal hanya menguji mesin scan crypto. Adapter forex, XAUUSD, dan saham BEI "
        "belum aktif karena sumber data dan batas gratisnya harus divalidasi terpisah."
    )
    run_scan = st.button("Jalankan scan", type="primary", use_container_width=True)

st.markdown(
    "**Kriteria contoh:** harga di atas EMA20, EMA20 di atas EMA50, RSI 50–68, "
    "volume meningkat, dan candle terakhir naik. Skor hanya untuk mengurutkan kandidat."
)

if run_scan:
    if not selected_symbols:
        st.warning("Pilih setidaknya satu simbol.")
    else:
        rows, errors = [], []
        progress = st.progress(0)
        status = st.empty()
        for i, symbol in enumerate(selected_symbols, start=1):
            status.write(f"Mengambil data {symbol}…")
            try:
                rows.append(analyze_symbol(symbol, INTERVALS[timeframe_label]))
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")
            progress.progress(i / len(selected_symbols))
            time.sleep(0.12)
        status.empty()
        progress.empty()

        if rows:
            result = pd.DataFrame(rows).sort_values(
                ["Skor / 5", "Perubahan %"], ascending=[False, False]
            )
            st.subheader(f"Hasil scan — {timeframe_label}")
            st.dataframe(result, use_container_width=True, hide_index=True)
            st.download_button(
                "Unduh hasil CSV",
                data=result.to_csv(index=False).encode("utf-8"),
                file_name=f"scan_{timeframe_label.lower()}.csv",
                mime="text/csv",
            )
            st.caption(
                "Waktu eksekusi: "
                + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            )
        if errors:
            with st.expander(f"{len(errors)} simbol gagal dipindai"):
                st.write("\n".join(errors))
else:
    st.info("Pilih timeframe dan aset, lalu tekan **Jalankan scan**.")
