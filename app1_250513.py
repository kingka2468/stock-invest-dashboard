import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
import json
import os
import requests
import re
from datetime import datetime, timedelta
from pykrx import stock
from io import BytesIO

SAVE_FILE = "portfolio_settings.json"
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# ---- [추가된 부분] 네이버 금융 지표 파싱 함수 ----
def get_naver_indicators(ticker):
    """네이버 금융에서 PER, PBR, 배당수익률을 직접 추출 (N/A 대응 로직)"""
    url = f"https://finance.naver.com/item/main.naver?code={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        html = response.text
        
        per_m = re.search(r'id="_per">([\d,.]+)<', html)
        pbr_m = re.search(r'id="_pbr">([\d,.]+)<', html)
        div_m = re.search(r'배당수익률.*?<em.*?>(.*?)%?</em>', html, re.DOTALL)
        if not div_m:
            div_m = re.search(r'id="_dvr">([\d,.]+)<', html)

        def parse(match):
            if not match: return 0.0
            val = re.sub(r'[^\d.]', '', match.group(1))
            try: return float(val) if val else 0.0
            except: return 0.0

        return parse(per_m), parse(pbr_m), parse(div_m)
    except:
        return 0.0, 0.0, 0.0

# ---- 초기 세션 상태 설정 ----
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

# ---- 포트폴리오 저장 및 불러오기 (기존 유지) ----
def get_save_file():
    return "portfolio_us.json" if st.session_state.market == "us" else "portfolio_kr.json"

def save_portfolio(tickers, max_per, min_up, min_drop, min_div):
    data = {"tickers": tickers, "max_per": max_per, "min_up": min_up, "min_drop": min_drop, "min_div": min_div}
    st.session_state.saved_portfolio[st.session_state.market] = data
    with open(get_save_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_portfolio():
    market_key = st.session_state.market
    if market_key in st.session_state.saved_portfolio: return st.session_state.saved_portfolio[market_key]
    file = get_save_file()
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            st.session_state.saved_portfolio[market_key] = data
            return data
    return None

# ---- 영업일 계산 로직 (기존 유지) ----
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
    one_year_ago = latest_trading_day - timedelta(weeks=52)
    return one_year_ago.strftime("%Y%m%d")

# ---- UI (기존 유지) ----
st.set_page_config(page_title="주식 투자 판단 대시보드", layout="wide")
st.title("📊 주식 투자 판단 대시보드")

market = st.radio("📌 시장 선택", ["미국", "한국"], index=0 if st.session_state.market == 'us' else 1)
st.session_state.market = 'us' if market == "미국" else 'kr'

max_per = st.sidebar.slider("PER 최대값", 0, 50, st.session_state.max_per)
min_up = st.sidebar.slider("최소 상승여력 (%)", 0, 100, st.session_state.min_up)
min_drop = st.sidebar.slider("최소 하락률 (고점대비 %)", 0, 100, st.session_state.min_drop)
min_div = st.sidebar.slider("최소 배당률 (%)", 0.0, 10.0, st.session_state.min_div)
st.sidebar.markdown("🧩 차트 옵션 설정")
enable_div = st.sidebar.checkbox("배당률로 크기 표현", value=True)

st.markdown("✅ 종목 코드를 입력하세요")
tickers_input = st.text_input("", st.session_state.tickers_input)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# ---- 포트폴리오 버튼 (기존 유지) ----
if st.sidebar.button("💾 포트폴리오 저장"):
    save_portfolio(tickers, max_per, min_up, min_drop, min_div)
    st.sidebar.success("✅ 포트폴리오가 저장되었습니다.")

if st.sidebar.button("📂 포트폴리오 불러오기"):
    portfolio = load_portfolio()
    if portfolio:
        st.session_state.update({"tickers_input": ", ".join(portfolio["tickers"]), "max_per": portfolio["max_per"], "min_up": portfolio["min_up"], "min_drop": portfolio["min_drop"], "min_div": portfolio["min_div"]})
        st.rerun()

# ---- 투자 등급 분류 및 요약 (기존 유지) ----
def classify(row):
    score = 0
    if row['고점대비 (%)'] <= -min_drop: score += 1
    if row['상승여력 (%)'] >= min_up: score += 1
    if 0 < row['PER'] <= max_per: score += 1
    if row['배당률 (%)'] >= min_div: score += 1
    grades = {4: '🔥🔥🔥🔥 초초적극 매수', 3: '🔥🔥🔥 초적극 매수', 2: '🔥🔥 적극 매수', 1: '🔥 매수', 0: '👀 관망'}
    return grades.get(score, '👀 관망')

def generate_summary(row):
    price_prefix = "$" if st.session_state.market == 'us' else ""
    summary = f"📌 **{row['기업명']}** ({row['종목']}) | 현재가: {price_prefix}{row['현재가']}, 고점대비: {row['고점대비 (%)']}%, 상승여력: {row['상승여력 (%)']}%, PER: {row['PER']}, 배당률: {row['배당률 (%)']}%\n"
    if '🔥🔥🔥🔥' in row['투자등급']: summary += "🚀 **초초적극 매수** 구간입니다. 4개 지표 모두 탁월하게 충족!"
    elif '🔥🔥🔥' in row['투자등급']: summary += "👉 **초적극 매수** 추천. 가격 매력과 성장성이 매우 우수합니다."
    elif '🔥🔥' in row['투자등급']: summary += "✅ **적극 매수** 구간입니다. 기준 대부분 충족."
    elif '🔥' in row['투자등급']: summary += "👌 **매수 고려** 가능. 일부 지표는 기준 미달."
    else: summary += "⚠️ **관망 추천**. 현재 매수에는 신중해야 합니다."
    return summary

# ---- 스타일링 함수 (기존 유지) ----
def color_by_grade(val):
    if '🔥🔥🔥🔥' in val: return 'background-color: darkred; color: white'
    if '🔥🔥🔥' in val: return 'background-color: red; color: white'
    if '🔥🔥' in val: return 'background-color: green; color: white'
    if '🔥' in val: return 'background-color: yellow; color: black'
    if '👀' in val: return 'background-color: gray; color: white'
    return ''

def highlight_per(s): return ['background-color: #d1f7d6' if v <= max_per else '' for v in s]
def highlight_drop(s): return ['background-color: #d1e0f7' if v <= -min_drop else '' for v in s]
def highlight_up(s): return ['background-color: #fff0b3' if v >= min_up else '' for v in s]
def highlight_div(s): return ['background-color: #fde2e2' if v >= min_div else '' for v in s]

# ---- [수정된 부분] 분석 시작 엔진 ----
if st.button("📊 분석 시작"):
    data = []
    latest_day = get_latest_trading_day()
    one_year_ago = get_52weeks_ago_day()
    
    for ticker in tickers:
        try:
            if st.session_state.market == 'us':
                stock_data = yf.Ticker(ticker)
                info = stock_data.info
                if not info or 'currentPrice' not in info: continue
                name, price = info.get("shortName", ticker), info.get("currentPrice", 0)
                high, low = info.get("fiftyTwoWeekHigh", 1), info.get("fiftyTwoWeekLow", 1)
                per, pbr = info.get("trailingPE", 0), info.get("priceToBook", 0)
                div_yield = (info.get("dividendRate", 0) / price * 100) if price > 0 else 0
            else:
                # 해결한 한국 주식 하이브리드 로직 적용
                name = stock.get_market_ticker_name(ticker)
                if not name: continue
                df_p = stock.get_market_ohlcv_by_date(latest_day, latest_day, ticker)
                if df_p.empty: continue
                price = int(df_p['종가'].iloc[0])
                hist_df = stock.get_market_ohlcv_by_date(one_year_ago, latest_day, ticker)
                high, low = hist_df['고가'].max(), hist_df['저가'].min()
                per, pbr, div_yield = get_naver_indicators(ticker)

            고점대비 = ((price / high) - 1) * 100
            상승여력 = ((high - price) / (high - low)) * 100 if high != low else 0

            data.append({
                '종목': ticker, '기업명': name, '현재가': price, '52주 고점': high, '52주 저점': low,
                'PER': round(per, 2), 'PBR': round(pbr, 2), '배당률 (%)': round(div_yield, 2),
                '고점대비 (%)': round(고점대비, 2), '상승여력 (%)': round(상승여력, 2)
            })
        except Exception as e:
            st.error(f"{ticker} 정보 수집 실패: {e}")

    df_res = pd.DataFrame(data)
    if not df_res.empty:
        df_res['투자등급'] = df_res.apply(classify, axis=1)
        cols = df_res.columns.tolist()
        cols.insert(cols.index('기업명'), cols.pop(cols.index('투자등급')))
        st.session_state.df = df_res[cols]

# ---- 결과 출력 영역 (기존 코드와 100% 동일하게 유지) ----
df = st.session_state.df
if df is not None:
    styled_df = df.style.applymap(color_by_grade, subset=['투자등급'])
    styled_df = styled_df.apply(highlight_per, subset=['PER'])
    styled_df = styled_df.apply(highlight_drop, subset=['고점대비 (%)'])
    styled_df = styled_df.apply(highlight_up, subset=['상승여력 (%)'])
    styled_df = styled_df.apply(highlight_div, subset=['배당률 (%)'])
    st.dataframe(styled_df, use_container_width=True)

    st.subheader("🧠 AI 투자 요약")
    grade_order = {'🔥🔥🔥🔥 초초적극 매수': 0, '🔥🔥🔥 초적극 매수': 1, '🔥🔥 적극 매수': 2, '🔥 매수': 3, '👀 관망': 4}
    df_plot = df.copy()
    df_plot['등급순서'] = df_plot['투자등급'].map(grade_order)
    sorted_df = df_plot.sort_values(by='등급순서')
    last_grade = None
    for i in range(len(sorted_df)):
        current_grade = sorted_df.iloc[i]['투자등급']
        if last_grade is not None and current_grade != last_grade:
            st.markdown('<hr style="margin: 6px 0;">', unsafe_allow_html=True)
        st.markdown(generate_summary(sorted_df.iloc[i]))
        last_grade = current_grade

    st.subheader("📈 투자 지표 대시보드")
    for section in [
        ("투자등급 분포", alt.Chart(df).mark_bar().encode(
            x='투자등급', y='count()', color=alt.Color('투자등급', scale=alt.Scale(
                domain=['🔥🔥🔥🔥 초초적극 매수', '🔥🔥🔥 초적극 매수', '🔥🔥 적극 매수', '🔥 매수', '👀 관망'],
                range=['darkred', 'salmon', 'LightPink', 'LightSkyBlue', 'dodgerBlue']
            ))
        )),
        ("PER vs 상승여력 vs 배당률", alt.Chart(df).mark_circle().encode(
            x=alt.X('PER', scale=alt.Scale(zero=False, padding=10), title="PER (낮을수록 저평가)"),
            y=alt.Y('상승여력 (%)', scale=alt.Scale(padding=10), title="상승여력 (%) (높을수록 좋음)"),
            size=alt.Size('배당률 (%)', scale=alt.Scale(type='sqrt', range=[30, 300]), legend=alt.Legend(title='배당률 (%)')) if enable_div else alt.value(100),
            color=alt.Color('투자등급', scale=alt.Scale(
                domain=['🔥🔥🔥🔥 초초적극 매수', '🔥🔥🔥 초적극 매수', '🔥🔥 적극 매수', '🔥 매수', '👀 관망'],
                range=['darkred', 'salmon', 'LightPink', 'LightSkyBlue', 'dodgerBlue']
            )),
            tooltip=['종목', '기업명', 'PER', '상승여력 (%)', '고점대비 (%)', '배당률 (%)', '투자등급']
        ).interactive()),
        ("고점대비 하락률", alt.Chart(df).mark_bar().encode(
            y=alt.Y('기업명', sort='-x'),
            x=alt.X('고점대비 (%)', title='고점대비 하락률 (%)'),
            color=alt.Color('고점대비 (%)', scale=alt.Scale(scheme='redblue'), legend=None),
            tooltip=['종목', '기업명', '고점대비 (%)']
        ).properties(height=40 * len(df)))
    ]:
        st.markdown(f"#### {section[0]}")
        st.altair_chart(section[1], use_container_width=True)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='분석결과')
    st.download_button("📥 분석 결과 다운로드 (Excel)", data=output.getvalue(), file_name="investment_analysis.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")