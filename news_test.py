import streamlit as st
import pandas as pd
import altair as alt
import json
import requests
import re
from datetime import datetime, timedelta
from pykrx import stock
from io import BytesIO

# --- 1. 네이버 및 외부 API 설정 ---
NAVER_CLIENT_ID = "UtJVnNmIIhf5KLF4Wssx"
NAVER_CLIENT_SECRET = "RWqDMr5avj"
FINNHUB_API_KEY = "d5ghto1r01ql4f48gcrgd5ghto1r01ql4f48gcs0"

def init_session_state():
    defaults = {
        "tickers_input": "000270, 005380, 035420, NVDA",
        "max_per": 20, "min_up": 70, "min_drop": 30, "min_div": 4.0,
        "df": None, "market": "kr"
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- 2. 뉴스 수집 및 감성 분석 엔진 (공식 API) ---
def get_sentiment_score(text):
    pos_words = ['상승', '호재', '실적', '수익', '돌파', '성장', '최고', '매수', '긍정', '반등', '강세']
    neg_words = ['하락', '악재', '손실', '우려', '부정', '급락', '쇼크', '폭락', '감소', '약세']
    score = 0
    for word in pos_words:
        if word in text: score += 1
    for word in neg_words:
        if word in text: score -= 1
    return score

def get_stock_news(query, market='kr'):
    news_list, total_sentiment = [], 0
    try:
        if market == 'kr':
            # ✅ 네이버 공식 API 호출 (발급받은 키 사용)
            api_url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display=3&sort=sim"
            headers = {
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
            }
            res = requests.get(api_url, headers=headers, timeout=5).json()
            for item in res.get('items', []):
                clean_title = re.sub(r'<[^>]*>', '', item['title']) # HTML 태그 제거
                news_list.append(clean_title)
                # 제목 + 요약문 합쳐서 감성 분석
                total_sentiment += get_sentiment_score(clean_title + item['description'])
        else:
            # 미국 주식 (Finnhub)
            url = f"https://finnhub.io/api/v1/company-news?symbol={query}&from={(datetime.now()-timedelta(days=3)).strftime('%Y-%m-%d')}&to={datetime.now().strftime('%Y-%m-%d')}&token={FINNHUB_API_KEY}"
            res = requests.get(url, timeout=5).json()[:3]
            for item in res:
                title = item.get('headline', '')
                news_list.append(title); total_sentiment += get_sentiment_score(title)
    except: pass
    
    label = "🙂 긍정" if total_sentiment > 0 else "😟 부정" if total_sentiment < 0 else "🧐 중립"
    return news_list, label, total_sentiment

# --- 3. 주식 지표 수집 함수 ---
def get_kr_indicators(ticker):
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).text
        per = re.search(r'id="_per">([\d,.]+)<', res)
        pbr = re.search(r'id="_pbr">([\d,.]+)<', res)
        div = re.search(r'배당수익률.*?<em.*?>(.*?)</em>', res, re.DOTALL)
        def clean(m): return float(re.sub(r'[^\d.]', '', m.group(1))) if m else 0.0
        return clean(per), clean(pbr), clean(div)
    except: return 0.0, 0.0, 0.0

# --- 4. 메인 대시보드 UI ---
st.set_page_config(page_title="투자 지표 대시보드 v12.1", layout="wide")
st.title("📊 투자 판단 대시보드 (네이버 API 통합)")

market_choice = st.radio("📌 시장 선택", ["한국", "미국"], horizontal=True)
st.session_state.market = 'kr' if market_choice == "한국" else 'us'

st.sidebar.header("🎯 필터 기준")
max_per = st.sidebar.slider("PER 최대값", 0, 50, st.session_state.max_per)
min_up = st.sidebar.slider("최소 상승여력 (%)", 0, 100, st.session_state.min_up)
min_drop = st.sidebar.slider("최소 하락률 (%)", 0, 100, st.session_state.min_drop)
min_div = st.sidebar.slider("최소 배당률 (%)", 0.0, 10.0, st.session_state.min_div)

tickers_input = st.text_input("✅ 종목 코드를 입력하세요", st.session_state.tickers_input)
st.session_state.tickers_input = tickers_input
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# --- 5. 분석 시작 ---
if st.button("📊 분석 시작"):
    data = []
    latest_day = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    for i in range(10):
        target = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        if not stock.get_market_ohlcv_by_date(target, target, "005930").empty:
            latest_day = target; break
            
    for ticker in tickers:
        with st.spinner(f'{ticker} 분석 및 뉴스 수집 중...'):
            try:
                if st.session_state.market == 'kr':
                    name = stock.get_market_ticker_name(ticker)
                    df_p = stock.get_market_ohlcv_by_date(latest_day, latest_day, ticker)
                    price = int(df_p['종가'].iloc[0])
                    hist = stock.get_market_ohlcv_by_date((datetime.strptime(latest_day, "%Y%m%d")-timedelta(days=365)).strftime("%Y%m%d"), latest_day, ticker)
                    high, low = hist['고가'].max(), hist['저가'].min()
                    per, pbr, div = get_kr_indicators(ticker)
                    news_titles, sentiment, s_score = get_stock_news(name, 'kr')
                else:
                    res = requests.get(f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_API_KEY}").json()
                    metric = requests.get(f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}&metric=all&token={FINNHUB_API_KEY}").json().get('metric', {})
                    name, price = ticker, res.get('c', 0)
                    high, low = metric.get('52WeekHigh', 0), metric.get('52WeekLow', 0)
                    per, pbr, div = metric.get('peBasicExclExtraTTM', 0), metric.get('pbAnnual', 0), metric.get('dividendYieldIndicatedAnnual', 0)
                    news_titles, sentiment, s_score = get_stock_news(ticker, 'us')

                data.append({
                    '종목': ticker, '기업명': name, '현재가': price, '52주 고점': float(high or price),
                    'PER': round(float(per), 2), 'PBR': round(float(pbr), 2), '배당률 (%)': round(float(div), 2),
                    '고점대비 (%)': round(((price / high) - 1) * 100, 2) if high != 0 else 0,
                    '상승여력 (%)': round(((high - price) / (high - low) * 100) if high != low else 0, 2),
                    '뉴스감성': sentiment, '감성점수': s_score, 
                    '최근뉴스': news_titles[0] if news_titles else "최근 뉴스 없음"
                })
            except: continue
    
    if data:
        st.session_state.df = pd.DataFrame(data)

# --- 6. 결과 출력 (표/요약/차트) ---
if st.session_state.df is not None:
    df = st.session_state.df
    def classify(row):
        score = 0
        if row['고점대비 (%)'] <= -min_drop: score += 1
        if row['상승여력 (%)'] >= min_up: score += 1
        if 0 < row['PER'] <= max_per: score += 1
        if row['배당률 (%)'] >= min_div: score += 1
        if row['감성점수'] > 0: score += 0.5
        return {4:'🔥🔥🔥🔥 초초적극', 3:'🔥🔥🔥 초적극', 2:'🔥🔥 적극', 1:'🔥 매수', 0:'👀 관망'}.get(int(score), '👀 관망')
    
    df['투자등급'] = df.apply(classify, axis=1)

    st.subheader("📋 종합 투자 분석 표")
    st.dataframe(df.drop(columns=['감성점수', '최근뉴스']), use_container_width=True)

    st.subheader("🧠 AI 투자 요약")
    for _, row in df.sort_values(by='투자등급', ascending=False).iterrows():
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 10px; border-left: 5px solid #ff4b4b;">
            📌 <b>{row['기업명']}</b> ({row['종목']}) | {row['뉴스감성']}<br>
            <span style="color: #666; font-size: 0.9em;">📰 {row['최근뉴스']}</span><br>
            등급: <b>{row['투자등급']}</b> | 상승여력: {row['상승여력 (%)']}%
        </div>
        """, unsafe_allow_html=True)

    st.subheader("📈 투자 지표 대시보드")
    bubble = alt.Chart(df).mark_circle(size=400).encode(
        x='PER', y='상승여력 (%)', color='투자등급', tooltip=['기업명', 'PER', '상승여력 (%)']
    ).properties(height=450).interactive()
    st.altair_chart(bubble, use_container_width=True)

    bar = alt.Chart(df).mark_bar().encode(
        x=alt.X('고점대비 (%)', title='고점 대비 하락률'), y=alt.Y('기업명', sort='x'),
        color=alt.Color('고점대비 (%)', scale=alt.Scale(scheme='redblue'))
    ).properties(height=400)
    st.altair_chart(bar, use_container_width=True)