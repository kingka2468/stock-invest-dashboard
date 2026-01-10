import streamlit as st
import pandas as pd
import altair as alt
import json
import os
import requests
import re
import time
from datetime import datetime, timedelta
from pykrx import stock
from io import BytesIO

# --- 1. 설정 및 환경 초기화 ---
FINNHUB_API_KEY = "d5ghto1r01ql4f48gcrgd5ghto1r01ql4f48gcs0"
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

def init_session_state():
    defaults = {
        "tickers_input": "NVDA, GOOGL, AMZN, MSFT, AAPL, TSLA, META",
        "max_per": 20, "min_up": 70, "min_drop": 30, "min_div": 4.0,
        "df": None, "market": "us", "saved_portfolio": {}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- 2. 안정적인 영업일 조회 함수 ---
def get_safe_trading_day():
    for i in range(10):
        target_day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(target_day, target_day, "005930")
        if not df.empty:
            return target_day
    return datetime.now().strftime("%Y%m%d")

# --- 3. 데이터 수집 함수 ---
def get_us_stock_data(ticker):
    base_url = "https://finnhub.io/api/v1"
    params = {'token': FINNHUB_API_KEY, 'symbol': ticker.strip().upper()}
    try:
        q = requests.get(f"{base_url}/quote", params=params, timeout=10).json()
        p = requests.get(f"{base_url}/stock/profile2", params=params, timeout=10).json()
        f = requests.get(f"{base_url}/stock/metric", params={**params, 'metric': 'all'}, timeout=10).json()
        if 'c' not in q or q['c'] == 0: return None
        m = f.get('metric', {})
        return {
            'name': p.get('name', ticker), 'price': q.get('c'),
            'high52': m.get('52WeekHigh', q.get('h', 0)), 'low52': m.get('52WeekLow', q.get('l', 0)),
            'per': m.get('peBasicExclExtraTTM'), 'pbr': m.get('pbAnnual'), 'div_yield': m.get('dividendYieldIndicatedAnnual')
        }
    except: return None

def get_kr_indicators(ticker):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5).text
        per = re.search(r'id="_per">([\d,.]+)<', res)
        pbr = re.search(r'id="_pbr">([\d,.]+)<', res)
        div = re.search(r'배당수익률.*?<em.*?>(.*?)%?</em>', res, re.DOTALL)
        def clean(m): return float(re.sub(r'[^\d.]', '', m.group(1))) if m else 0.0
        return clean(per), clean(pbr), clean(div)
    except: return 0.0, 0.0, 0.0

# --- 4. 포트폴리오 관리 ---
def get_save_file(): return f"portfolio_{st.session_state.market}.json"

def save_portfolio(tickers, max_per, min_up, min_drop, min_div):
    data = {"tickers": tickers, "max_per": max_per, "min_up": min_up, "min_drop": min_drop, "min_div": min_div}
    with open(get_save_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_portfolio():
    if os.path.exists(get_save_file()):
        with open(get_save_file(), "r", encoding="utf-8") as f: return json.load(f)
    return None

# --- 5. UI 설정 ---
st.set_page_config(page_title="주식 투자 판단 대시보드", layout="wide")
st.title("📊 주식 투자 판단 대시보드 (v10.4)")

market_choice = st.radio("📌 시장 선택", ["미국", "한국"], horizontal=True)
st.session_state.market = 'us' if market_choice == "미국" else 'kr'

st.sidebar.header("🎯 필터 기준")
max_per = st.sidebar.slider("PER 최대값", 0, 50, st.session_state.max_per)
min_up = st.sidebar.slider("최소 상승여력 (%)", 0, 100, st.session_state.min_up)
min_drop = st.sidebar.slider("최소 하락률 (%)", 0, 100, st.session_state.min_drop)
min_div = st.sidebar.slider("최소 배당률 (%)", 0.0, 10.0, st.session_state.min_div)
enable_div = st.sidebar.checkbox("배당률로 크기 표현", value=True)

if st.sidebar.button("💾 포트폴리오 저장"):
    save_portfolio(st.session_state.tickers_input.split(","), max_per, min_up, min_drop, min_div)
    st.sidebar.success("✅ 저장 완료")

if st.sidebar.button("📂 포트폴리오 불러오기"):
    p = load_portfolio()
    if p:
        st.session_state.tickers_input, st.session_state.max_per = ", ".join(p["tickers"]), p["max_per"]
        st.session_state.min_up, st.session_state.min_drop, st.session_state.min_div = p["min_up"], p["min_drop"], p["min_div"]
        st.rerun()

tickers_input = st.text_input("✅ 종목 코드를 입력하세요", st.session_state.tickers_input)
st.session_state.tickers_input = tickers_input
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# --- 6. 분석 시작 ---
if st.button("📊 분석 시작"):
    data = []
    latest_day = get_safe_trading_day()
    one_year_ago = (datetime.strptime(latest_day, "%Y%m%d") - timedelta(days=365)).strftime("%Y%m%d")
    
    for ticker in tickers:
        with st.spinner(f'{ticker} 분석 중...'):
            try:
                if st.session_state.market == 'us':
                    d = get_us_stock_data(ticker)
                    if not d: continue
                    name, price, high, low, per, pbr, div = d['name'], d['price'], d['high52'], d['low52'], d['per'], d['pbr'], d['div_yield']
                    time.sleep(1.0)
                else:
                    name = stock.get_market_ticker_name(ticker)
                    if not name: continue
                    df_p = stock.get_market_ohlcv_by_date(latest_day, latest_day, ticker)
                    if df_p.empty: continue
                    price = int(df_p['종가'].iloc[0])
                    hist = stock.get_market_ohlcv_by_date(one_year_ago, latest_day, ticker)
                    high, low = hist['고가'].max(), hist['저가'].min()
                    per, pbr, div = get_kr_indicators(ticker)
                
                high, low = float(high or price), float(low or price)
                data.append({
                    '종목': ticker, '기업명': name, '현재가': price, '52주 고점': round(high, 2), '52주 저점': round(low, 2),
                    'PER': round(float(per or 0), 2), 'PBR': round(float(pbr or 0), 2), '배당률 (%)': round(float(div or 0), 2),
                    '고점대비 (%)': round(((price / high) - 1) * 100, 2), '상승여력 (%)': round(((high - price) / (high - low) * 100) if high != low else 0, 2)
                })
            except Exception as e: st.error(f"{ticker} 실패: {e}")
    if data:
        df = pd.DataFrame(data)
        def classify(row):
            score = 0
            if row['고점대비 (%)'] <= -min_drop: score += 1
            if row['상승여력 (%)'] >= min_up: score += 1
            if 0 < row['PER'] <= max_per: score += 1
            if row['배당률 (%)'] >= min_div: score += 1
            return {4:'🔥🔥🔥🔥 초초적극 매수', 3:'🔥🔥🔥 초적극 매수', 2:'🔥🔥 적극 매수', 1:'🔥 매수', 0:'👀 관망'}.get(score, '👀 관망')
        
        df['투자등급'] = df.apply(classify, axis=1)
        cols = df.columns.tolist()
        cols.insert(1, cols.pop(cols.index('투자등급')))
        st.session_state.df = df[cols]

# --- 7. 결과 출력 ---
df = st.session_state.df
if df is not None:
    st.subheader("📋 실시간 투자 분석 표")
    def get_color_code(val):
        if '🔥🔥🔥🔥' in val: return 'darkred', 'white'
        if '🔥🔥🔥' in val: return '#ff4b4b', 'white' # Light red
        if '🔥🔥' in val: return 'green', 'white'
        if '🔥' in val: return '#DAA520', 'black' # Gold
        return '#f0f2f6', 'black' # Gray

    st.dataframe(df.style.apply(lambda x: [f"background-color: {get_color_code(v)[0]}; color: {get_color_code(v)[1]}" for v in x], subset=['투자등급'])
                 .apply(lambda s: ['background-color: #d1f7d6' if 0 < v <= max_per else '' for v in s], subset=['PER'])
                 .apply(lambda s: ['background-color: #d1e0f7' if v <= -min_drop else '' for v in s], subset=['고점대비 (%)'])
                 .apply(lambda s: ['background-color: #fff0b3' if v >= min_up else '' for v in s], subset=['상승여력 (%)'])
                 .apply(lambda s: ['background-color: #fde2e2' if v >= min_div else '' for v in s], subset=['배당률 (%)']),
                 use_container_width=True)

    # 🧠 AI 요약 등급별 음영 박스 (수정본)
    st.subheader("🧠 AI 투자 요약")
    sorted_df = df.sort_values(by='투자등급', ascending=False)
    
    # 전체를 감싸는 하나의 문자열 생성
    summary_elements = []
    for _, row in sorted_df.iterrows():
        bg_color, text_color = get_color_code(row['투자등급'])
        
        # f-string 안에서 중괄호를 안전하게 사용하기 위해 분리
        element = f"""
        <div style="background-color: {bg_color}; color: {text_color}; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #ddd; line-height: 1.5;">
            <span style="font-size: 1.1em;">📌 <b>{row['기업명']}</b> ({row['종목']})</span><br>
            현재가: {row['현재가']} | 상승여력: <b>{row['상승여력 (%)']}%</b> | 등급: <b>{row['투자등급']}</b>
        </div>
        """
        summary_elements.append(element)
    
    # join으로 합쳐서 한 번에 출력
    full_summary_html = "".join(summary_elements)
    st.markdown(full_summary_html, unsafe_allow_html=True)

    st.subheader("📈 투자 지표 대시보드")
    bubble_chart = alt.Chart(df).mark_circle(size=250).encode(
        x=alt.X('PER', title='PER'), y=alt.Y('상승여력 (%)', title='상승여력 (%)'),
        color='투자등급', size='배당률 (%)' if enable_div else alt.value(150),
        tooltip=['기업명', 'PER', '상승여력 (%)', '배당률 (%)']
    ).properties(height=500).interactive()
    st.altair_chart(bubble_chart, use_container_width=True)

    bar_chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('고점대비 (%)', title='하락률 (%)'), y=alt.Y('기업명', sort='x'),
        color=alt.Color('고점대비 (%)', scale=alt.Scale(scheme='redblue'), legend=None),
        tooltip=['기업명', '고점대비 (%)']
    ).properties(height=400)
    st.altair_chart(bar_chart, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Result')
    st.download_button("📥 엑셀 다운로드", data=output.getvalue(), file_name="stock_analysis.xlsx")