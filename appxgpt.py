import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import timedelta, date
import json
from urllib.parse import quote_plus
from streamlit_local_storage import LocalStorage
import textwrap

# =========================
# Page Config
# =========================
st.set_page_config(page_title="국내 ETF 수익률/배당금 분석기", page_icon="📈", layout="wide")

# =========================
# CSS
# =========================
st.markdown(
    """
<style>
.block-container { padding-top: 4.2rem; padding-bottom: 2rem; }
.etf-title{
  font-size: 1.85rem;
  font-weight: 800;
  margin: 0 0 0.25rem 0;
  line-height: 1.15;
  word-break: keep-all;
  overflow-wrap: normal;
}

[data-testid="stMetricLabel"] { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
[data-testid="stMetricValue"] { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
[data-testid="stMetricDelta"] { white-space: nowrap; }

.stButton>button { width: 100%; }

/* KPI Grid */
.kpi-grid{
  display: grid;
  gap: 0.5rem;
}
.kpi-card{
  border: 1px solid rgba(49, 51, 63, 0.12);
  border-radius: 0.75rem;
  padding: 0.6rem 0.7rem;
  background: rgba(255,255,255,0.02);
}
.kpi-label{
  font-size: 0.78rem;
  opacity: 0.75;
  line-height: 1.1;
  margin-bottom: 0.15rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kpi-value{
  font-size: 1.05rem;
  font-weight: 750;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.kpi-delta{
  font-size: 0.8rem;
  margin-top: 0.15rem;
  white-space: nowrap;
}

.idx-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.sum-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.ret-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }

@media (max-width: 640px) {
  .block-container { padding-top: 5.0rem; padding-left: 0.85rem; padding-right: 0.85rem; }
  .etf-title { font-size: 1.75rem; }

  .idx-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .sum-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .ret-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }

  .kpi-card{ padding: 0.55rem 0.6rem; }
  .kpi-value{ font-size: 0.95rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Title
# =========================
st.markdown('<div class="etf-title">📈 국내 ETF 수익률/배당금 분석기</div>', unsafe_allow_html=True)
st.caption("※ 모든 데이터는 실시간이 아니며, 투자 참고용입니다. (데이터 오류/지연 가능)")

# =========================
# LocalStorage (favorites)
# =========================
localS = LocalStorage()
LS_FAV_KEY = "etf_dashboard_favorites_symbol_v1"

def _safe_parse_symbols(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, str)]
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return [x for x in data if isinstance(x, str)]
        except Exception:
            return [raw]
    return []

def load_favorites_symbols() -> list[str]:
    try:
        raw = localS.getItem(LS_FAV_KEY)
    except Exception:
        raw = None
    return _safe_parse_symbols(raw)

def save_favorites_symbols(symbols: list[str]) -> None:
    try:
        localS.setItem(LS_FAV_KEY, json.dumps(symbols, ensure_ascii=False))
    except Exception:
        pass

# =========================
# Data Loaders
# =========================
@st.cache_data(ttl=60 * 60 * 6)
def get_etf_list() -> pd.DataFrame:
    df = fdr.StockListing("ETF/KR")
    for col in ["Symbol", "Name"]:
        if col not in df.columns:
            raise ValueError(f"ETF list missing required column: {col}")
    df["Symbol"] = df["Symbol"].astype(str)
    df["Name"] = df["Name"].astype(str)
    return df

@st.cache_data(ttl=60 * 10)
def get_price_data(symbol: str, start: date, end: date) -> pd.DataFrame:
    df = fdr.DataReader(symbol, start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    if "Close" not in df.columns:
        return pd.DataFrame()
    return df.sort_index()

@st.cache_data(ttl=60 * 5)
def get_index_snapshot_yahoo(ticker: str, days: int = 30) -> dict:
    try:
        df = fdr.DataReader(ticker, date.today() - timedelta(days=days), date.today())
        if df is None or df.empty or "Close" not in df.columns:
            return {"value": None, "pct": None}
        df = df.sort_index()
        if len(df) < 2:
            v = float(df["Close"].iloc[-1])
            return {"value": v, "pct": None}
        v_today = float(df["Close"].iloc[-1])
        v_prev = float(df["Close"].iloc[-2])
        pct = ((v_today - v_prev) / v_prev) * 100 if v_prev else None
        return {"value": v_today, "pct": pct}
    except Exception:
        return {"value": None, "pct": None}

# =========================
# Helpers
# =========================
def fmt_pct(x):
    return "-" if x is None else f"{x:.2f}%"

def fmt_won(x: float) -> str:
    return f"{x:,.0f}원"

def fmt_num(x: float) -> str:
    return "-" if x is None else f"{x:,.2f}"

def get_return_by_trading_days(df_price: pd.DataFrame, current_price: float, n: int):
    if len(df_price) <= n:
        return None
    past_price = float(df_price["Close"].iloc[-(n + 1)])
    if past_price == 0:
        return None
    return (current_price / past_price - 1) * 100

def make_search_links(etf_name: str, etf_code: str) -> dict:
    q_main = quote_plus(f"{etf_name} 분배금")
    q_pay  = quote_plus(f"{etf_name} 분배금 지급일")
    q_disc = quote_plus(f"{etf_name} 분배금 공시")
    return {
        "google_div": f"https://www.google.com/search?q={q_main}",
        "google_pay": f"https://www.google.com/search?q={q_pay}",
        "naver_div":  f"https://search.naver.com/search.naver?query={q_main}",
        "naver_disc": f"https://search.naver.com/search.naver?query={q_disc}",
    }

def render_search_buttons(etf_name: str, etf_code: str):
    links = make_search_links(etf_name, etf_code)
    st.write("#### 🔎 분배금/배당 정보 빠른 검색")
    st.caption("※ 자동 수집 대신, 공식/포털 검색으로 빠르게 확인할 수 있게 연결합니다.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.link_button("구글: 분배금", links["google_div"], use_container_width=True)
    with c2:
        st.link_button("구글: 지급일", links["google_pay"], use_container_width=True)
    with c3:
        st.link_button("네이버: 분배금", links["naver_div"], use_container_width=True)
    with c4:
        st.link_button("네이버: 공시", links["naver_disc"], use_container_width=True)

# ✅ 핵심: 앞 공백 제거(dedent) + strip
def kpi_card(label: str, value: str, delta: str | None = None) -> str:
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta is not None else ""
    html = f"""
<div class="kpi-card">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value">{value}</div>
  {delta_html}
</div>
"""
    return textwrap.dedent(html).strip()

def render_kpi_grid(grid_class: str, items: list[dict]):
    cards = [kpi_card(it["label"], it["value"], it.get("delta")) for it in items]
    html = f'<div class="kpi-grid {grid_class}">' + "".join(cards) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

# =========================
# Index Snapshot (Title 아래)
# =========================
idx_map = [
    ("KOSPI", "^KS11"),
    ("KOSDAQ", "^KQ11"),
    ("S&P 500", "^GSPC"),
    ("NASDAQ", "^IXIC"),
]
idx_items = []
for label, ticker in idx_map:
    snap = get_index_snapshot_yahoo(ticker)
    value = fmt_num(snap["value"])
    delta = None
    if snap["pct"] is not None:
        sign = "+" if snap["pct"] >= 0 else ""
        delta = f"{sign}{snap['pct']:.2f}%"
    idx_items.append({"label": label, "value": value, "delta": delta})

render_kpi_grid("idx-grid", idx_items)
st.write("")

# =========================
# Sidebar - Search & Select
# =========================
st.sidebar.header("🔍 검색 옵션")

with st.spinner("국내 모든 ETF 정보를 가져오는 중입니다..."):
    etf_list = get_etf_list()

symbol_to_name = dict(zip(etf_list["Symbol"], etf_list["Name"]))

def label_symbol(sym: str) -> str:
    return f"{sym} | {symbol_to_name.get(sym, '')}"

if "favorite_symbols" not in st.session_state:
    st.session_state.favorite_symbols = load_favorites_symbols()

if "pending_symbol" not in st.session_state:
    st.session_state.pending_symbol = None
if "pending_search_keyword" not in st.session_state:
    st.session_state.pending_search_keyword = None

if st.session_state.pending_search_keyword is not None:
    st.session_state.search_keyword = st.session_state.pending_search_keyword
    st.session_state.pending_search_keyword = None

search_keyword = st.sidebar.text_input(
    "ETF 검색 (코드/이름)",
    value=st.session_state.get("search_keyword", ""),
    key="search_keyword",
)

filtered_df = etf_list
if search_keyword.strip():
    kw = search_keyword.strip().lower()
    filtered_df = filtered_df[
        filtered_df["Symbol"].str.lower().str.contains(kw, na=False)
        | filtered_df["Name"].str.lower().str.contains(kw, na=False)
    ]

MAX_OPTIONS = 800
if len(filtered_df) > MAX_OPTIONS and not search_keyword.strip():
    st.sidebar.warning(f"ETF가 너무 많아 상위 {MAX_OPTIONS}개만 표시합니다. 검색어를 입력해 좁혀보세요.")
    filtered_df = filtered_df.head(MAX_OPTIONS)

if filtered_df.empty:
    st.warning("검색 결과가 없습니다. 다른 키워드로 검색해보세요.")
    st.stop()

symbols = filtered_df["Symbol"].tolist()

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = symbols[0]

if st.session_state.pending_symbol is not None:
    st.session_state.selected_symbol = st.session_state.pending_symbol
    st.session_state.pending_symbol = None

if st.session_state.selected_symbol not in symbols:
    symbols = [st.session_state.selected_symbol] + symbols

selected_symbol = st.sidebar.selectbox(
    "분석할 ETF를 선택하세요:",
    symbols,
    format_func=label_symbol,
    key="selected_symbol",
)

code = selected_symbol
name = symbol_to_name.get(code, "")

# =========================
# ETF 변경 시: 분배율/분배금만 0 리셋 (모드 유지)
# =========================
if "last_symbol" not in st.session_state:
    st.session_state.last_symbol = code

if "annual_yield" not in st.session_state:
    st.session_state.annual_yield = 0.0
if "monthly_div_per_share" not in st.session_state:
    st.session_state.monthly_div_per_share = 0.0

MONTHLY_MODE = "월 주당 분배금(원)으로 계산 (더 직관적)"
ANNUAL_MODE  = "연 분배율(%)로 계산 (간편)"

if "calc_mode" not in st.session_state:
    st.session_state.calc_mode = MONTHLY_MODE

if st.session_state.last_symbol != code:
    st.session_state.last_symbol = code
    st.session_state.annual_yield = 0.0
    st.session_state.monthly_div_per_share = 0.0

# =========================
# Sidebar - Favorites
# =========================
st.sidebar.divider()
st.sidebar.subheader("⭐ 즐겨찾기 ETF")

MAX_FAVORITES = 10
c1, c2 = st.sidebar.columns(2)

with c1:
    if st.button("추가", key="add_fav", use_container_width=True):
        if code in st.session_state.favorite_symbols:
            st.sidebar.info("이미 즐겨찾기에 등록된 ETF입니다.")
        elif len(st.session_state.favorite_symbols) >= MAX_FAVORITES:
            st.sidebar.warning(f"즐겨찾기는 최대 {MAX_FAVORITES}개까지 등록할 수 있습니다.")
        else:
            st.session_state.favorite_symbols.append(code)
            save_favorites_symbols(st.session_state.favorite_symbols)
            st.sidebar.success("즐겨찾기에 추가했습니다.")

with c2:
    if st.button("해제", key="remove_fav", use_container_width=True):
        if code in st.session_state.favorite_symbols:
            st.session_state.favorite_symbols.remove(code)
            save_favorites_symbols(st.session_state.favorite_symbols)
            st.sidebar.success("즐겨찾기에서 해제했습니다.")
        else:
            st.sidebar.info("현재 ETF는 즐겨찾기에 없습니다.")

st.sidebar.caption(f"등록된 즐겨찾기: {len(st.session_state.favorite_symbols)}/{MAX_FAVORITES}")

if st.session_state.favorite_symbols:
    fav_choice = st.sidebar.radio(
        "내 즐겨찾기 목록",
        st.session_state.favorite_symbols,
        format_func=label_symbol,
        key="fav_choice",
    )
    if st.sidebar.button("선택한 ETF 보기", key="load_fav", use_container_width=True):
        st.session_state.pending_search_keyword = ""
        st.session_state.pending_symbol = fav_choice
        st.rerun()
else:
    st.sidebar.caption("즐겨찾기 ETF를 등록하면 여기서 빠르게 불러올 수 있습니다.")

# =========================
# Load Price Data
# =========================
end_date = date.today()
start_date = end_date - timedelta(days=365 * 2)

with st.spinner(f"{name}({code}) 가격 데이터를 불러오는 중입니다..."):
    df_price = get_price_data(code, start_date, end_date)

if df_price.empty or len(df_price) < 2:
    st.error("가격 데이터를 가져오지 못했거나 데이터가 부족합니다. (신규 상장/휴장/데이터 지연 가능)")
    st.stop()

last_dt = df_price.index.max()
current_price = float(df_price.loc[last_dt, "Close"])
yesterday_price = float(df_price["Close"].iloc[-2]) if len(df_price) >= 2 else current_price
diff_pct = ((current_price / yesterday_price) - 1) * 100 if yesterday_price else 0.0

# =========================
# Returns
# =========================
ret_1w = get_return_by_trading_days(df_price, current_price, 5)
ret_1m = get_return_by_trading_days(df_price, current_price, 21)
ret_6m = get_return_by_trading_days(df_price, current_price, 126)
ret_1y = get_return_by_trading_days(df_price, current_price, 252)

# =========================
# Main UI
# =========================
st.subheader(f"📊 {name} ({code})")
st.metric("현재 가격", fmt_won(current_price), delta=f"{diff_pct:.2f}%")

sum_items = [
    {"label": "최신 거래일", "value": last_dt.strftime("%Y-%m-%d")},
    {"label": "데이터 시작", "value": df_price.index.min().strftime("%Y-%m-%d")},
    {"label": "데이터 개수", "value": f"{len(df_price):,}"},
]
render_kpi_grid("sum-grid", sum_items)

st.write("#### 📅 기간별 수익률 (거래일 기준)")
ret_items = [
    {"label": "1주", "value": fmt_pct(ret_1w)},
    {"label": "1개월", "value": fmt_pct(ret_1m)},
    {"label": "6개월", "value": fmt_pct(ret_6m)},
    {"label": "1년", "value": fmt_pct(ret_1y)},
]
render_kpi_grid("ret-grid", ret_items)

st.write("#### 📈 최근 1년 주가 흐름(종가)")
df_1y = df_price.loc[df_price.index >= (last_dt - timedelta(days=365))]
st.line_chart(df_1y["Close"])

# =========================
# Dividend Simulation
# =========================
st.divider()
st.subheader("💸 배당금(분배금) 시뮬레이션")
render_search_buttons(name, code)

if "investment" not in st.session_state:
    st.session_state.investment = 0

st.write("#### 🧮 투자금 빠른 입력(누적 버튼)")
b1, b2, b3, b4, b5 = st.columns(5)
with b1:
    if st.button("+100만원", use_container_width=True):
        st.session_state.investment += 1_000_000
with b2:
    if st.button("+500만원", use_container_width=True):
        st.session_state.investment += 5_000_000
with b3:
    if st.button("+1,000만원", use_container_width=True):
        st.session_state.investment += 10_000_000
with b4:
    if st.button("+1억원", use_container_width=True):
        st.session_state.investment += 100_000_000
with b5:
    if st.button("초기화", use_container_width=True):
        st.session_state.investment = 0

investment = st.number_input(
    "투자금(원) (버튼으로 누적 입력 가능)",
    min_value=0,
    value=int(st.session_state.investment),
    step=1_000_000,
    format="%d",
)
st.session_state.investment = int(investment)

if investment == 0:
    st.info("투자금을 입력해주세요.")

mode = st.radio(
    "계산 방식",
    [MONTHLY_MODE, ANNUAL_MODE],
    key="calc_mode",
    horizontal=True,
)

estimated_monthly = 0.0

if mode == ANNUAL_MODE:
    annual_yield = st.number_input(
        "예상 연 분배율(%)",
        min_value=0.0,
        step=0.1,
        key="annual_yield",
    )
    if annual_yield == 0.0:
        st.info("연 분배율(%)을 입력하면 예상 월/연 분배금이 계산됩니다.")
    estimated_monthly = investment * (annual_yield / 100.0) / 12.0
    d1, d2 = st.columns(2)
    d1.metric("예상 월 배당금(분배금)", fmt_won(estimated_monthly))
    d2.metric("예상 연 배당금(분배금)", fmt_won(estimated_monthly * 12))
else:
    monthly_div_per_share = st.number_input(
        "월 주당 분배금(원)",
        min_value=0.0,
        step=10.0,
        key="monthly_div_per_share",
    )
    if monthly_div_per_share == 0.0:
        st.info("월 주당 분배금(원)을 입력하면 예상 월/연 분배금이 계산됩니다.")
    shares = (investment / current_price) if current_price else 0.0
    estimated_monthly = shares * monthly_div_per_share
    d1, d2, d3 = st.columns(3)
    d1.metric("예상 보유 주식수", f"{shares:,.2f}주")
    d2.metric("예상 월 배당금", fmt_won(estimated_monthly))
    d3.metric("예상 연 배당금", fmt_won(estimated_monthly * 12))

st.success(f"투자금 {fmt_won(investment)} → 예상 월 배당금(분배금) {fmt_won(estimated_monthly)}")
st.caption("※ 본 시뮬레이션은 단순 추정치입니다. 실제 분배금은 ETF 공시/운용 결과에 따라 달라질 수 있습니다.")

with st.expander("데이터 원본 표 보기(최신순)"):
    st.dataframe(df_price.sort_index(ascending=False))
