import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
import json
import os
import requests
import re
import time
from datetime import datetime, timedelta
from pykrx import stock
from io import BytesIO

# --- 설정 및 초기화 로직 (기존과 동일) ---
SAVE_FILE = "portfolio_settings.json"
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

def get_naver_indicators(ticker):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        html = response.text
        per_m = re.search(r'id="_per">([\d,.]+)<', html)
        pbr_m = re.search(r'id="_pbr">([\d,.]+)<', html)
        div_m = re.search(r'배당수익률.*?<em.*?>(.*?)%?</em>', html, re.DOTALL)
        if not div_m: div_m = re.search(r'id="_dvr">([\d,.]+)<', html)
        def parse(match):
            if not match: return 0.0
            val = re.sub(r'[^\d.]', '', match.group(1))
            try: return float(val) if val else 0.0
            except: return 0.0
        return parse(per_m), parse(pbr_m), parse(div_m)
    except: return 0.0, 0.0, 0.0

if "df" not in st.session_state: st.session_state.df = None
if "market" not in st.session_state: st.session_state.market = "us"
if "tickers_input" not in st.session_state: st.session_state.tickers_input = "NVDA, GOOGL, AMZN, MSFT, AAPL, TSLA, META"
if "max_per" not in st.session_state: st.session_state.max_per = 20
if "min_up" not in st.session_state: st.session_state.min_up = 70
if "min_drop" not in st.session_state: st.session_state.min_drop = 30
if "min_div" not in st.session_state: st.session_state.min_div = 4.0

# --- 날짜 함수 ---
def get_latest_trading_day():
    today = datetime.today()
    for i in range(7):
        day = today - timedelta(days=i)
        date_str = day.strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(date_str, date_str, "005930")
        if not df.empty: return date_str
    return today.strftime("%Y%m%d")

def get_52weeks_ago_day():
    latest_trading_day = datetime.strptime(get_latest_trading_day(), "%Y%m%d")
    return (latest_trading_day - timedelta(weeks=52)).strftime("%Y%m%d")

# --- UI 설정 ---
st.set_page_config(page_title="주식 투자 판단 대시보드", layout="wide")
st.title("📊 주식 투자 판단 대시보드")

market_choice = st.radio("📌 시장 선택", ["미국", "한국"], index=0 if st.session_state.market == 'us' else 1)
st.session_state.market = 'us' if market_choice == "미국" else 'kr'

max_per = st.sidebar.slider("PER 최대값", 0, 50, st.session_state.max_per)
min_up = st.sidebar.slider("최소 상승여력 (%)", 0, 100, st.session_state.min_up)
min_drop = st.sidebar.slider("최소 하락률 (고점대비 %)", 0, 100, st.session_state.min_drop)
min_div = st.sidebar.slider("최소 배당률 (%)", 0.0, 10.0, st.session_state.min_div)
enable_div = st.sidebar.checkbox("배당률로 크기 표현", value=True)

tickers_input = st.text_input("✅ 종목 코드를 입력하세요", st.session_state.tickers_input)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# --- 등급 분류 함수 ---
def classify(row):
    score = 0
    if row['고점대비 (%)'] <= -min_drop: score += 1
    if row['상승여력 (%)'] >= min_up: score += 1
    if 0 < row['PER'] <= max_per: score += 1
    if row['배당률 (%)'] >= min_div: score += 1
    grades = {4: '🔥🔥🔥🔥 초초적극 매수', 3: '🔥🔥🔥 초적극 매수', 2: '🔥🔥 적극 매수', 1: '🔥 매수', 0: '👀 관망'}
    return grades.get(score, '👀 관망')

def generate_summary(row):
    summary = f"📌 **{row['기업명']}** ({row['종목']}) | 현재가: {row['현재가']}, 고점대비: {row['고점대비 (%)']}%, 상승여력: {row['상승여력 (%)']}%, PER: {row['PER']}, 배당률: {row['배당률 (%)']}%\n"
    grade_key = row['투자등급'][:4] # 이모지 4개 추출
    grade_msgs = {'🔥🔥🔥🔥': "🚀 **초초적극 매수** 구간입니다.", '🔥🔥🔥': "👉 **초적극 매수** 추천.", '🔥🔥': "✅ **적극 매수** 구간.", '🔥': "👌 **매수 고려** 가능.", '👀': "⚠️ **관망 추천**."}
    summary += grade_msgs.get(grade_key, "⚠️ 분석 필요")
    return summary

def color_by_grade(val):
    colors = {'🔥🔥🔥🔥': 'darkred', '🔥🔥🔥': 'red', '🔥🔥': 'green', '🔥': '#DAA520', '👀': 'gray'}
    for key, color in colors.items():
        if key in val: return f'background-color: {color}; color: white'
    return ''

# --- 핵심 분석 로직 (에러 수정됨) ---
if st.button("📊 분석 시작"):
    data = []
    latest_day = get_latest_trading_day()
    one_year_ago = get_52weeks_ago_day()
    
    for ticker in tickers:
        try:
            with st.spinner(f'{ticker} 분석 중...'):
                if st.session_state.market == 'us':
                    # --- 미국 시장 ---
                    stock_obj = yf.Ticker(ticker)
                    hist = stock_obj.history(period="1y")
                    if hist.empty: continue
                    
                    price = round(hist['Close'].iloc[-1], 2)
                    high = hist['High'].max()
                    low = hist['Low'].min()
                    
                    # .info는 최소한으로 사용 (변수명 dividend_yield로 통일)
                    info = stock_obj.info
                    name = info.get("shortName", ticker)
                    per = info.get("trailingPE", 0)
                    pbr = info.get("priceToBook", 0)
                    dividend_val = info.get("dividendRate", 0)
                    dividend_yield = (dividend_val / price * 100) if price > 0 and dividend_val else 0
                    
                    time.sleep(1.5) # 차단 방지를 위해 1.5초 휴식
                else:
                    # --- 한국 시장 ---
                    name = stock.get_market_ticker_name(ticker)
                    if not name: continue
                    df_p = stock.get_market_ohlcv_by_date(latest_day, latest_day, ticker)
                    if df_p.empty: continue
                    price = int(df_p['종가'].iloc[0])
                    hist_df = stock.get_market_ohlcv_by_date(one_year_ago, latest_day, ticker)
                    high, low = hist_df['고가'].max(), hist_df['저가'].min()
                    per, pbr, dividend_yield = get_naver_indicators(ticker)

                # 공통 계산
                drop_rate = ((price / high) - 1) * 100
                upside = ((high - price) / (high - low)) * 100 if high != low else 0

                data.append({
                    '종목': ticker, '기업명': name, '현재가': price, '52주 고점': round(high, 2), '52주 저점': round(low, 2),
                    'PER': round(per, 2), 'PBR': round(pbr, 2), '배당률 (%)': round(dividend_yield, 2),
                    '고점대비 (%)': round(drop_rate, 2), '상승여력 (%)': round(upside, 2),
                })
        except Exception as e:
            st.error(f"{ticker} 정보 수집 실패: {e}")

    if data:
        df_res = pd.DataFrame(data)
        df_res['투자등급'] = df_res.apply(classify, axis=1)
        # 컬럼 순서 조정
        cols = df_res.columns.tolist()
        cols.insert(cols.index('기업명'), cols.pop(cols.index('투자등급')))
        st.session_state.df = df_res[cols]

# --- 결과 출력 및 시각화 ---
df = st.session_state.df
if df is not None:
    st.dataframe(df.style.applymap(color_by_grade, subset=['투자등급']), use_container_width=True)
    
    st.subheader("🧠 AI 투자 요약")
    sorted_df = df.sort_values(by='투자등급', ascending=False)
    for i in range(len(sorted_df)):
        st.markdown(generate_summary(sorted_df.iloc[i]))
        if i < len(sorted_df)-1: st.markdown('<hr style="margin: 6px 0;">', unsafe_allow_html=True)

    st.subheader("📈 투자 지표 대시보드")
    c2 = alt.Chart(df).mark_circle().encode(
        x=alt.X('PER', title="PER"),
        y=alt.Y('상승여력 (%)', title="상승여력 (%)"),
        size=alt.Size('배당률 (%)') if enable_div else alt.value(100),
        color='투자등급',
        tooltip=['기업명', 'PER', '상승여력 (%)', '배당률 (%)']
    ).interactive()
    st.altair_chart(c2, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='분석결과')
    st.download_button("📥 엑셀 다운로드", data=output.getvalue(), file_name="invest_analysis.xlsx")