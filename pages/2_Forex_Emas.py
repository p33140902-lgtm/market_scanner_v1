import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

PRESETS = {
    "XAUUSD (emas spot)": "XAUUSD=X",
    "Emas futures (GC=F)": "GC=F",
    "Perak futures (SI=F)": "SI=F",
    "Minyak WTI (CL=F)": "CL=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCAD": "USDCAD=X",
    "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X",
    "GBPJPY": "GBPJPY=X",
    "EURJPY": "EURJPY=X",
    "BBCA (saham)": "BBCA.JK",
    "BBRI (saham)": "BBRI.JK",
    "BMRI (saham)": "BMRI.JK",
    "TLKM (saham)": "TLKM.JK",
}
# label: (interval Yahoo, rentang data, resample)
TIMEFRAMES = {
    "M1": ("1m", "5d", None),
    "M5": ("5m", "30d", None),
    "M15": ("15m", "30d", None),
    "M30": ("30m", "30d", None),
    "H1": ("1h", "90d", None),
    "H4": ("1h", "180d", "4h"),
    "D1": ("1d", "2y", None),
    "W1": ("1wk", "5y", None),
    "Monthly": ("1mo", "10y", None),
}

st.set_page_config(page_title="Forex, Emas, Saham", layout="wide")
st.title("Forex, Emas, Saham")


@st.cache_data(ttl=120, show_spinner=False)
def get_candles(ticker, interval, period, resample):
    raw = yf.download(
        ticker, period=period, interval=interval,
        progress=False, auto_adjust=False,
    )
    if raw is None or raw.empty:
        raise ValueError(f"Tidak ada data untuk {ticker}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    df = raw.reset_index()
    df.columns = [str(c).lower() for c in df.columns]
    df = df.rename(columns={df.columns[0]: "time"})
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    df = df[["time", "open", "high", "low", "close"]].dropna()
    if resample:
        df = (
            df.set_index("time")
            .resample(resample)
            .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
            .dropna()
            .reset_index()
        )
    # Buang candle terakhir karena kemungkinan belum selesai
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
preset = c1.selectbox("Instrumen", list(PRESETS))
tf_label = c2.selectbox("Timeframe", list(TIMEFRAMES), index=5)
custom = st.text_input("Ticker lain (opsional, contoh: EURGBP=X atau ASII.JK)")
ticker = custom.strip() if custom.strip() else PRESETS[preset]

interval, period, resample = TIMEFRAMES[tf_label]
try:
    df = add_indicators(get_candles(ticker, interval, period, resample))
except Exception as exc:
    st.error(f"Gagal mengambil data {ticker}: {exc}")
    st.stop()

if len(df) < 60:
    st.warning("Candle belum cukup (minimal 60) untuk timeframe ini.")
    st.stop()

highs, lows = find_swings(df)
structure = read_structure(highs, lows)
last = df.iloc[-1]

m1, m2 = st.columns(2)
m1.metric("Close terakhir", f"{last['close']:,.5f}")
m2.metric("RSI 14", f"{last['rsi14']:.1f}")
m3, m4 = st.columns(2)
m3.metric("Swing high terakhir", f"{highs[-1][1]:,.5f}" if highs else "-")
m4.metric("Swing low terakhir", f"{lows[-1][1]:,.5f}" if lows else "-")
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
        marker=dict(symbol="triangle-up", size=9),
    )
)
fig.update_layout(
    height=520,
    xaxis_rangeslider_visible=False,
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h"),
)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    f"Sumber: Yahoo Finance via yfinance (tidak resmi, bisa tertunda) | "
    f"Ticker: {ticker} | Candle terakhir selesai: {last['time']} UTC | "
    "Harga bisa berbeda dari broker (misalnya HFM). Untuk edukasi, bukan sinyal trading."
  )
