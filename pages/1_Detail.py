import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

BASE = "https://data-api.binance.vision"
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "TRXUSDT", "DOGEUSDT", "ADAUSDT", "LINKUSDT", "LTCUSDT",
]
INTERVALS = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h",
    "H12": "12h", "D1": "1d", "D3": "3d", "W1": "1w", "Monthly": "1M",
}
COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]

st.set_page_config(page_title="Detail instrumen", layout="wide")
st.title("Detail instrumen")


@st.cache_data(ttl=60, show_spinner=False)
def get_klines(symbol, interval, limit=300):
    r = requests.get(
        f"{BASE}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=15,
    )
    r.raise_for_status()
    raw = r.json()
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Tidak ada data candle untuk {symbol}")
    df = pd.DataFrame(raw, columns=COLUMNS)
    for col in ["open", "high", "low", "close", "volume", "close_time"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["time"] = pd.to_datetime(df["open_time"], unit="ms")
    # Buang candle yang belum selesai supaya hasil tidak berubah-ubah
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    if len(df) and int(df.iloc[-1]["close_time"]) > now_ms:
        df = df.iloc[:-1]
    return df.reset_index(drop=True)


def add_indicators(df):
    df = df.copy()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    df["rsi14"] = 100 - (100 / (1 + rs))
    return df


def find_swings(df, n=5):
    # Swing baru dianggap valid setelah n candle penutup,
    # jadi tidak memakai data masa depan.
    highs, lows = [], []
    for i in range(n, len(df) - n):
        if df["high"].iloc[i] == df["high"].iloc[i - n : i + n + 1].max():
            highs.append((i, float(df["high"].iloc[i])))
        if df["low"].iloc[i] == df["low"].iloc[i - n : i + n + 1].min():
            lows.append((i, float(df["low"].iloc[i])))
    return highs, lows


def read_structure(highs, lows):
    if len(highs) < 2 or len(lows) < 2:
        return "Belum cukup data"
    hh = highs[-1][1] > highs[-2][1]
    hl = lows[-1][1] > lows[-2][1]
    if hh and hl:
        return "Bullish (HH + HL)"
    if (not hh) and (not hl):
        return "Bearish (LH + LL)"
    return "Sideways / transisi"


c1, c2 = st.columns(2)
symbol = c1.selectbox("Instrumen", SYMBOLS)
tf_label = c2.selectbox("Timeframe", list(INTERVALS), index=4)

try:
    df = add_indicators(get_klines(symbol, INTERVALS[tf_label]))
except Exception as exc:
    st.error(f"Gagal mengambil data {symbol}: {exc}")
    st.stop()

if len(df) < 60:
    st.warning("Candle selesai belum cukup (minimal 60) untuk timeframe ini.")
    st.stop()

highs, lows = find_swings(df)
structure = read_structure(highs, lows)
last = df.iloc[-1]

m1, m2 = st.columns(2)
m1.metric("Close terakhir", f"{last['close']:,.4f}")
m2.metric("RSI 14", f"{last['rsi14']:.1f}")
m3, m4 = st.columns(2)
m3.metric("Swing high terakhir", f"{highs[-1][1]:,.4f}" if highs else "-")
m4.metric("Swing low terakhir", f"{lows[-1][1]:,.4f}" if lows else "-")
st.metric("Struktur pasar", structure)

fig = go.Figure()
fig.add_trace(
    go.Candlestick(
        x=df["time"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Harga",
    )
)
fig.add_trace(go.Scatter(x=df["time"], y=df["ema20"], name="EMA20"))
fig.add_trace(go.Scatter(x=df["time"], y=df["ema50"], name="EMA50"))
fig.add_trace(
    go.Scatter(
        x=[df["time"].iloc[i] for i, _ in highs], y=[v for _, v in highs],
        mode="markers", name="Swing High",
        marker=dict(symbol="triangle-down", size=9),
    )
)
fig.add_trace(
    go.Scatter(
        x=[df["time"].iloc[i] for i, _ in lows], y=[v for _, v in lows],
        mode="markers", name="Swing Low",
        marker=dict(symbo
