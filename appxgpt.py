import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import timedelta, date

st.set_page_config(page_title="국내 ETF 수익률", page_icon="📈", layout="wide")

st.markdown(
    """
<style>
/* ✅ 상단 Streamlit 바(Deploy/Rerun) 겹침 방지: 컨텐츠를 더 아래로 */
.block-container { padding-top: 4.2rem; padding-bottom: 2rem; }

.etf-title {
  font-size: 1.45rem;
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

@media (max-width: 640px) {
  .block-container { padding-top: 5.0rem; padding-left: 0.85rem; padding-right: 0.85rem; }
  .etf-title { font-size: 1.25rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="etf-title">📈 국내 ETF 수익률</div>', unsafe_allow_html=True)
st.caption("※ 모든 데이터는 실시간이 아니며, 투자 참고용입니다. (데이터 오류/지연 가능)")

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

def fmt_pct(x):
    return "-" if x is None else f"{x:.2f}%"

def fmt_won(x: float) -> str:
    return f"{x:,.0f}원"

def get_return_by_trading_days(df_price: pd.DataFrame, current_price: float, n: int):
    if len(df_price) <= n:
        return None
    past_price = float(df_price["Close"].iloc[-(n + 1)])
    if past_price == 0:
        return None
    return (current_price / past_price - 1) * 100

st.sidebar.header("🔍 검색 옵션")

with st.spinner("국내 모든 ETF 정보를 가져오는 중입니다..."):
    etf_list = get_etf_list()

search_keyword = st.sidebar.text_input("ETF 검색 (코드/이름)", value="")

filtered = etf_list
if search_keyword.strip():
    kw = search_keyword.strip().lower()
    filtered = filtered[
        filtered["Symbol"].str.lower().str.contains(kw, na=False)
        | filtered["Name"].str.lower().str.contains(kw, na=False)
    ]

MAX_OPTIONS = 800
if len(filtered) > MAX_OPTIONS and not search_keyword.strip():
    st.sidebar.warning(f"ETF가 너무 많아 상위 {MAX_OPTIONS}개만 표시합니다. 검색어를 입력해 좁혀보세요.")
    filtered = filtered.head(MAX_OPTIONS)

if filtered.empty:
    st.warning("검색 결과가 없습니다. 다른 키워드로 검색해보세요.")
    st.stop()

options = (filtered["Symbol"] + " | " + filtered["Name"]).tolist()
selected_option = st.sidebar.selectbox("분석할 ETF를 선택하세요:", options, index=0)

code, name = selected_option.split(" | ", 1)

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

ret_1w = get_return_by_trading_days(df_price, current_price, 5)
ret_1m = get_return_by_trading_days(df_price, current_price, 21)
ret_6m = get_return_by_trading_days(df_price, current_price, 126)
ret_1y = get_return_by_trading_days(df_price, current_price, 252)

st.subheader(f"📊 {name} ({code})")

m1, m2 = st.columns([1.2, 1.8])
with m1:
    st.metric("현재 가격", fmt_won(current_price), delta=f"{diff_pct:.2f}%")
with m2:
    a, b, c = st.columns(3)
    a.metric("최신 거래일", last_dt.strftime("%Y-%m-%d"))
    b.metric("데이터 시작", df_price.index.min().strftime("%Y-%m-%d"))
    c.metric("데이터 개수", f"{len(df_price):,}")

st.write("#### 📅 기간별 수익률 (거래일 기준)")
rr1, rr2, rr3, rr4 = st.columns(4)
rr1.metric("1주", fmt_pct(ret_1w))
rr2.metric("1개월", fmt_pct(ret_1m))
rr3.metric("6개월", fmt_pct(ret_6m))
rr4.metric("1년", fmt_pct(ret_1y))

st.write("#### 📈 최근 1년 주가 흐름(종가)")
df_1y = df_price.loc[df_price.index >= (last_dt - timedelta(days=365))]
st.line_chart(df_1y["Close"])

st.divider()
st.subheader("💸 배당금(분배금) 시뮬레이션")

if "investment" not in st.session_state:
    st.session_state.investment = 50_000_000

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

mode = st.radio(
    "계산 방식",
    ["연 분배율(%)로 계산 (간편/추천)", "월 주당 분배금(원)으로 계산 (더 직접적)"],
    horizontal=True,
)

estimated_monthly = 0.0

if mode.startswith("연 분배율"):
    annual_yield = st.number_input("예상 연 분배율(%)", min_value=0.0, value=4.32, step=0.1)
    estimated_monthly = investment * (annual_yield / 100.0) / 12.0

    d1, d2 = st.columns(2)
    d1.metric("예상 월 배당금(분배금)", fmt_won(estimated_monthly))
    d2.metric("예상 연 배당금(분배금)", fmt_won(estimated_monthly * 12))
else:
    monthly_div_per_share = st.number_input("월 주당 분배금(원)", min_value=0.0, value=300.0, step=10.0)
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
