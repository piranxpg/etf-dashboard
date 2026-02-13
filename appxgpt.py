import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import timedelta, date

# =========================
# Page Config
# =========================
st.set_page_config(page_title="나만의 ETF 대시보드", page_icon="📈", layout="wide")

# =========================
# Mobile-first CSS (줄바꿈/폭/버튼/메트릭 안정화)
# =========================
st.markdown(
    """
<style>
/* 여백 최적화 */
.block-container { padding-top: 1rem; padding-bottom: 2rem; }

/* metric 텍스트가 모바일에서 엉키지 않도록 */
[data-testid="stMetricLabel"] { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
[data-testid="stMetricValue"] { white-space: nowrap; }
[data-testid="stMetricDelta"] { white-space: nowrap; }

/* 버튼은 폭 채우되(모바일/PC 둘 다) 컬럼 안에서는 "가로 정렬" 유지 */
.stButton>button { width: 100%; }

/* 모바일에서 좌우 패딩 살짝 축소 */
@media (max-width: 640px) {
  .block-container { padding-left: 0.85rem; padding-right: 0.85rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("📈 국내 ETF 수익률 분석기")
st.caption("※ 모든 데이터는 실시간이 아니며, 투자 참고용입니다. (데이터 오류/지연 가능)")

# =========================
# Data Loaders (Cached)
# =========================
@st.cache_data(ttl=60 * 60 * 6)  # 6 hours
def get_etf_list() -> pd.DataFrame:
    df = fdr.StockListing("ETF/KR")
    for col in ["Symbol", "Name"]:
        if col not in df.columns:
            raise ValueError(f"ETF list missing required column: {col}")
    df["Symbol"] = df["Symbol"].astype(str)
    df["Name"] = df["Name"].astype(str)
    return df

@st.cache_data(ttl=60 * 10)  # 10 minutes
def get_price_data(symbol: str, start: date, end: date) -> pd.DataFrame:
    df = fdr.DataReader(symbol, start, end)
    if df is None or df.empty:
        return pd.DataFrame()
    if "Close" not in df.columns:
        return pd.DataFrame()
    return df.sort_index()

# =========================
# Helpers
# =========================
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

# =========================
# Sidebar - Search & Select
# =========================
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
# Main UI (Mobile-first)
# =========================
st.subheader(f"📊 {name} ({code})")

# ✅ 상단 지표: 4개를 2개씩 두 줄로 (모바일에서 가장 안정적)
row1_a, row1_b = st.columns(2)
row1_a.metric("현재 가격", fmt_won(current_price), delta=f"{diff_pct:.2f}%")
row1_b.metric("최신 거래일", last_dt.strftime("%Y-%m-%d"))

row2_a, row2_b = st.columns(2)
row2_a.metric("데이터 시작", df_price.index.min().strftime("%Y-%m-%d"))
row2_b.metric("데이터 개수", f"{len(df_price):,}")

# ✅ 수익률도 2개씩 두 줄
st.write("#### 📅 기간별 수익률 (거래일 기준)")
r1, r2 = st.columns(2)
r1.metric("1주 수익률", fmt_pct(ret_1w))
r2.metric("1개월 수익률", fmt_pct(ret_1m))
r3, r4 = st.columns(2)
r3.metric("6개월 수익률", fmt_pct(ret_6m))
r4.metric("1년 수익률", fmt_pct(ret_1y))

st.write("#### 📈 최근 1년 주가 흐름(종가)")
df_1y = df_price.loc[df_price.index >= (last_dt - timedelta(days=365))]
st.line_chart(df_1y["Close"])

# =========================
# Dividend Simulation + Investment Buttons (가로 유지)
# =========================
st.divider()
st.subheader("💸 배당금(분배금) 시뮬레이션")

# session_state 초기화
if "investment" not in st.session_state:
    st.session_state.investment = 50_000_000  # 기본 5천만

st.write("#### 🧮 투자금 빠른 입력(누적 버튼)")

# ✅ 요청대로 "가로로" 유지: 4개는 2x2, 마지막 초기화는 아래 풀폭
# (모바일에서도 2열로 접히며 '가로 느낌' 유지, PC에서는 깔끔한 2x2)
b1, b2 = st.columns(2)
with b1:
    if st.button("+100만원", use_container_width=True):
        st.session_state.investment += 1_000_000
with b2:
    if st.button("+500만원", use_container_width=True):
        st.session_state.investment += 5_000_000

b3, b4 = st.columns(2)
with b3:
    if st.button("+1,000만원", use_container_width=True):
        st.session_state.investment += 10_000_000
with b4:
    if st.button("+1억원", use_container_width=True):
        st.session_state.investment += 100_000_000

# 초기화는 가로로 길게(오작동 방지 + 가독성)
if st.button("초기화(0원)", use_container_width=True):
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
    horizontal=False,  # 모바일에서 줄바꿈 안정적
)

estimated_monthly = 0.0

if mode.startswith("연 분배율"):
    annual_yield = st.number_input("예상 연 분배율(%)", min_value=0.0, value=4.32, step=0.1)
    estimated_monthly = investment * (annual_yield / 100.0) / 12.0

    # ✅ 모바일 안정: 2열
    d1, d2 = st.columns(2)
    d1.metric("예상 월 배당금(분배금)", fmt_won(estimated_monthly))
    d2.metric("예상 연 배당금(분배금)", fmt_won(estimated_monthly * 12))

else:
    monthly_div_per_share = st.number_input("월 주당 분배금(원)", min_value=0.0, value=300.0, step=10.0)
    shares = (investment / current_price) if current_price else 0.0
    estimated_monthly = shares * monthly_div_per_share

    # ✅ 모바일 안정: 2열 + 1열
    d1, d2 = st.columns(2)
    d1.metric("예상 보유 주식수(추정)", f"{shares:,.2f}주")
    d2.metric("예상 월 배당금(분배금)", fmt_won(estimated_monthly))
    st.metric("예상 연 배당금(분배금)", fmt_won(estimated_monthly * 12))

st.success(f"투자금 {fmt_won(investment)} → 예상 월 배당금(분배금) {fmt_won(estimated_monthly)}")
st.caption("※ 본 시뮬레이션은 단순 추정치입니다. 실제 분배금은 ETF 공시/운용 결과에 따라 달라질 수 있습니다.")

# =========================
# Raw Data
# =========================
with st.expander("데이터 원본 표 보기(최신순)"):
    st.dataframe(df_price.sort_index(ascending=False))
