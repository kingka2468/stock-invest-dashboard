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
        # ✅ 요청하신 14개 주요 종목 리스트로 기본값 설정
        "tickers_input": "005930, 000660, 005380, 000270, 012330, 035420, 035720, 017670, 207940, 008770, 041510, 122870, 035900, 352820",
        "max_per": 20, "min_up": 70, "min_drop": 30, "min_div": 4.0,
        "df": None, "market": "kr", "saved_portfolio": {}
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- [중략: 뉴스 분석 및 데이터 수집 함수는 v12.3과 동일] ---

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

def get_stock_news(query, market='kr'):
    news_list, total_sentiment = [], 0
    try:
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

# --- [중략: 유틸리티 및 UI 설정] ---

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

st.set_page_config(page_title="주식 투자 판단 대시보드 v12.4", layout="wide")
st.title("📊 주식 투자 판단 대시보드 (v12.4)")

# --- [차트 렌더링 부분] ---
df = st.session_state.df
if df is not None:
    st.subheader("📈 투자 지표 대시보드")
    
    # ✅ 사용자가 제안한 최적의 버블 크기 적용
    size_encoding = alt.Size('배당률 (%)', 
                             scale=alt.Scale(range=[200, 1000]), 
                             legend=alt.Legend(title="배당률 크기")) if enable_div else alt.value(300)
    
    bubble = alt.Chart(df).mark_circle(opacity=0.7, stroke='white', strokeWidth=1).encode(
        x=alt.X('PER', title='PER (주가수익비율)'),
        y=alt.Y('상승여력 (%)', title='상승여력 (고점 대비 %)'),
        color=alt.Color('투자등급', legend=alt.Legend(title="투자 등급")),
        size=size_encoding,
        tooltip=['기업명', '종목', 'PER', '상승여력 (%)', '배당률 (%)', '뉴스감성']
    ).properties(
        height=500, 
        title="PER 대비 상승여력 분석 (14개 주요 종목 비교)"
    ).interactive()
    
    st.altair_chart(bubble, use_container_width=True)
    
    # [이후 생략: 바 차트 및 엑셀 다운로드 로직]