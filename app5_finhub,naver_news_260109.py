import streamlit as st
import pandas as pd
import altair as alt
import json
import os
import requests
import re
from datetime import datetime, timedelta
from pykrx import stock
from io import BytesIO

# --- 1. 설정 및 환경 초기화 ---
NAVER_CLIENT_ID = "UtJVnNmIIhf5KLF4Wssx"
NAVER_CLIENT_SECRET = "RWqDMr5avj"
FINNHUB_API_KEY = "d5ghto1r01ql4f48gcrgd5ghto1r01ql4f48gcs0"
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

def init_session_state():
    defaults = {
        "tickers_input": "005930, 000660, 005380, 000270, 012330, 035420, 035720, 017670, 207940, 008770, 041510, 122870, 035900, 352820",
        "max_per": 20, "min_up": 70, "min_drop": 30, "min_div": 4.0,
        "df": None, "market": "kr", "saved_portfolio": {}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- 2. 뉴스 감성 분석 로직 (네이버 API 적용) ---
def get_sentiment_score(text):
    pos_words = ['상승', '돌파', '수익', '호재', '성장', '매수', '긍정', '신고가', '최고', '증가', '성공', '반등', '실적개선']
    neg_words = ['하락', '감소', '악재', '손실', '우려', '매도', '부정', '급락', '쇼크', '폭락', '실패', '약세']
    score = 0
    text_lower = text.lower()
    for word in pos_words:
        if word in text_lower: score += 1
    for word in neg_words:
        if word in text_lower: score -= 1
    return score

def get_stock_news(query, market='us'):
    news_list, total_sentiment = [], 0
    try:
        if market == 'us':
            url = f"https://finnhub.io/api/v1/company-news?symbol={query}&from={(datetime.now()-timedelta(days=3)).strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}&token={FINNHUB_API_KEY}"
            res = requests.get(url, timeout=5).json()[:3]
            for item in res:
                title = item.get('headline', '')
                news_list.append(title); total_sentiment += get_sentiment_score(title)
        else:
            url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=3&sort=sim"
            headers = {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
            res = requests.get(url, headers=headers, timeout=5).json()
            for item in res.get('items', []):
                clean_title = re.sub(r'<[^>]*>', '', item['title'])
                news_list.append(clean_title)
                total_sentiment += get_sentiment_score(clean_title + item['description'])
    except: pass
    label = "🙂 긍정" if total_sentiment > 0 else "😟 부정" if total_sentiment < 0 else "🧐 중립"
    return news_list, label, total_sentiment

# --- 3. 유틸리티 함수 ---
def get_save_file(): return f"portfolio_{st.session_state.market}.json"

def get_safe_trading_day():
    for i in range(10):
        target_day = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        df = stock.get_market_ohlcv_by_date(target_day, target_day, "005930")
        if not df.empty: return target_day
    return datetime.now().strftime("%Y%m%d")

def get_kr_indicators(ticker):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).text
        per = re.search(r'id="_per">([\d,.]+)<', res)
        pbr = re.search(r'id="_pbr">([\d,.]+)<', res)
        div = re.search(r'배당수익률.*?<em.*?>(.*?)</em>', res, re.DOTALL)
        def clean(m): return float(m.group(1).replace(',', '')) if m else 0.0
        return clean(per), clean(pbr), clean(div)
    except: return 0.0, 0.0, 0.0

# --- 4. UI 및 메인 로직 ---
st.set_page_config(page_title="주식 투자 판단 대시보드 v12.3", layout="wide")
st.title("📊 주식 투자 판단 대시보드 (v12.3)")

market_choice = st.radio("📌 시장 선택", ["한국", "미국"], horizontal=True)
st.session_state.market = 'kr' if market_choice == "한국" else 'us'

st.sidebar.header("🎯 필터 기준")
max_per = st.sidebar.slider("PER 최대값", 0, 50, st.session_state.max_per)
min_up = st.sidebar.slider("최소 상승여력 (%)", 0, 100, st.session_state.min_up)
min_drop = st.sidebar.slider("최소 하락률 (%)", 0, 100, st.session_state.min_drop)
min_div = st.sidebar.slider("최소 배당률 (%)", 0.0, 10.0, st.session_state.min_div)
enable_div = st.sidebar.checkbox("배당률로 크기 표현", value=True)

if st.sidebar.button("💾 포트폴리오 저장"):
    data = {"tickers": st.session_state.tickers_input, "max_per": max_per, "min_up": min_up, "min_drop": min_drop, "min_div": min_div}
    with open(get_save_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    st.sidebar.success("✅ 저장 완료")

if st.sidebar.button("📂 포트폴리오 불러오기"):
    if os.path.exists(get_save_file()):
        with open(get_save_file(), "r", encoding="utf-8") as f:
            p = json.load(f)
            st.session_state.tickers_input = p["tickers"]
            st.session_state.max_per, st.session_state.min_up = p["max_per"], p["min_up"]
            st.session_state.min_drop, st.session_state.min_div = p["min_drop"], p["min_div"]
            st.rerun()

tickers_input = st.text_input("✅ 종목 코드를 입력하세요", st.session_state.tickers_input)
st.session_state.tickers_input = tickers_input
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# --- 5. 분석 시작 ---
if st.button("📊 분석 시작"):
    data = []
    latest_day = get_safe_trading_day()
    one_year_ago = (datetime.strptime(latest_day, "%Y%m%d") - timedelta(days=365)).strftime("%Y%m%d")
    
    for ticker in tickers:
        with st.spinner(f'{ticker} 분석 중...'):
            try:
                if st.session_state.market == 'us':
                    params = {'token': FINNHUB_API_KEY, 'symbol': ticker}
                    q = requests.get("https://finnhub.io/api/v1/quote", params=params).json()
                    p = requests.get("https://finnhub.io/api/v1/stock/profile2", params=params).json()
                    f = requests.get("https://finnhub.io/api/v1/stock/metric", params={**params, 'metric': 'all'}).json()
                    if 'c' not in q or q['c'] == 0: continue
                    name, price = p.get('name', ticker), q['c']
                    high, low = f['metric'].get('52WeekHigh', 0), f['metric'].get('52WeekLow', 0)
                    per, pbr, div = f['metric'].get('peBasicExclExtraTTM', 0), f['metric'].get('pbAnnual', 0), f['metric'].get('dividendYieldIndicatedAnnual', 0)
                    news_titles, sentiment_label, s_score = get_stock_news(ticker, 'us')
                else:
                    name = stock.get_market_ticker_name(ticker)
                    if not name: continue
                    df_p = stock.get_market_ohlcv_by_date(latest_day, latest_day, ticker)
                    price = int(df_p['종가'].iloc[0])
                    hist = stock.get_market_ohlcv_by_date(one_year_ago, latest_day, ticker)
                    high, low = hist['고가'].max(), hist['저가'].min()
                    per, pbr, div = get_kr_indicators(ticker)
                    news_titles, sentiment_label, s_score = get_stock_news(name, 'kr')
                
                data.append({
                    '종목': ticker, '기업명': name, '현재가': price, '52주 고점': float(high or price),
                    'PER': round(float(per), 2), 'PBR': round(float(pbr), 2), '배당률 (%)': round(float(div), 2),
                    '고점대비 (%)': round(((price / high) - 1) * 100, 2) if high != 0 else 0, 
                    '상승여력 (%)': round(((high - price) / (high - low) * 100) if high != low else 0, 2),
                    '뉴스감성': sentiment_label, '감성점수': s_score, 
                    '최근뉴스': news_titles[0] if news_titles else "최근 뉴스 없음"
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
            if row['감성점수'] > 0: score += 0.5
            return {4:'🔥🔥🔥🔥 초초적극 매수', 3:'🔥🔥🔥 초적극 매수', 2:'🔥🔥 적극 매수', 1:'🔥 매수', 0:'👀 관망'}.get(int(score), '👀 관망')
        
        df['투자등급'] = df.apply(classify, axis=1)
        st.session_state.df = df

# --- 6. 결과 출력 ---
df = st.session_state.df
if df is not None:
    def get_color_code(val):
        if '🔥🔥🔥🔥' in val: return 'darkred', 'white'
        if '🔥🔥🔥' in val: return '#ff4b4b', 'white'
        if '🔥🔥' in val: return 'green', 'white'
        if '🔥' in val: return '#DAA520', 'black'
        return '#f0f2f6', 'black'

    st.subheader("📋 종합 투자 분석 표")
    styled_df = df.drop(columns=['감성점수', '최근뉴스']).style.apply(lambda x: [f"background-color: {get_color_code(v)[0]}; color: {get_color_code(v)[1]}" for v in x], subset=['투자등급'])\
        .apply(lambda s: ['background-color: #d1f7d6' if 0 < v <= max_per else '' for v in s], subset=['PER'])\
        .apply(lambda s: ['background-color: #d1e0f7' if v <= -min_drop else '' for v in s], subset=['고점대비 (%)'])\
        .apply(lambda s: ['background-color: #fff0b3' if v >= min_up else '' for v in s], subset=['상승여력 (%)'])\
        .apply(lambda s: ['background-color: #fde2e2' if v >= min_div else '' for v in s], subset=['배당률 (%)'])
    st.dataframe(styled_df, use_container_width=True)

    st.subheader("🧠 AI 투자 요약")
    for _, row in df.sort_values(by='투자등급', ascending=False).iterrows():
        bg, txt = get_color_code(row['투자등급'])
        st.markdown(f"""
        <div style="background-color: {bg}; color: {txt}; padding: 15px; border-radius: 10px; margin-bottom: 12px; border: 1px solid #ddd;">
            📌 <b>{row['기업명']}</b> ({row['종목']}) | {row['뉴스감성']}<br>
            <div style="margin: 5px 0; font-size: 0.85em; opacity: 0.8;">📰 {row['최근뉴스']}</div>
            <b>현재가:</b> {row['현재가']} | <b>상승여력:</b> {row['상승여력 (%)']}% | <b>등급:</b> {row['투자등급']}
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📈 투자 지표 대시보드")
    
    # ✅ 버블 차트 크기 및 시인성 개선
    size_encoding = alt.Size('배당률 (%)', scale=alt.Scale(range=[200, 1000]), legend=alt.Legend(title="배당률 크기")) if enable_div else alt.value(300)
    
    bubble = alt.Chart(df).mark_circle(opacity=0.7, stroke='white', strokeWidth=1).encode(
        x=alt.X('PER', title='PER (주가수익비율)'),
        y=alt.Y('상승여력 (%)', title='상승여력 (고점 대비 %)'),
        color=alt.Color('투자등급', legend=alt.Legend(title="투자 등급")),
        size=size_encoding,
        tooltip=['기업명', '종목', 'PER', '상승여력 (%)', '배당률 (%)', '뉴스감성']
    ).properties(
        height=500, 
        title="PER 대비 상승여력 분석 (버블 크기: 배당률)"
    ).interactive()
    
    st.altair_chart(bubble, use_container_width=True)

    # 2. 바 차트
    bar = alt.Chart(df).mark_bar().encode(
        x=alt.X('고점대비 (%)', title='고점 대비 하락률 (%)'),
        y=alt.Y('기업명', sort='x', title='종목명'),
        color=alt.Color('고점대비 (%)', scale=alt.Scale(scheme='redblue'), legend=None),
        tooltip=['기업명', '고점대비 (%)']
    ).properties(height=400, title="종목별 고점 대비 하락폭")
    st.altair_chart(bar, use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Result')
    st.download_button("📥 엑셀 다운로드", data=output.getvalue(), file_name="stock_analysis.xlsx")