import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
import json
import os

SAVE_FILE = "portfolio_settings.json"

# ---- 초기 세션 상태 설정 ----
def init_session_state():
    defaults = {
        "tickers_input": "NVDA, GOOGL, AMZN, MSFT,  AAPL, IONQ, TSLA, CRM, V, BRK-B, NKE, SBUX, WELL, MAIN, LMT, PG, UNH, META",
        "max_per": 20,
        "min_up": 70,
        "min_drop": 30,
        "min_div": 4.0,
        "df": None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ---- 포트폴리오 저장 및 불러오기 ----
def save_portfolio(tickers, max_per, min_up, min_drop, min_div):
    data = {
        "tickers": tickers,
        "max_per": max_per,
        "min_up": min_up,
        "min_drop": min_drop,
        "min_div": min_div
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_portfolio():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# ---- UI ----
st.set_page_config(page_title="미국 주식 대시보드", layout="wide")
st.title("📊 미국 주식 투자 판단 대시보드")

max_per = st.sidebar.slider("PER 최대값", 0, 50, st.session_state.max_per)
min_up = st.sidebar.slider("최소 상승여력 (%)", 0, 100, st.session_state.min_up)
min_drop = st.sidebar.slider("최소 하락률 (고점대비 %)", 0, 100, st.session_state.min_drop)
min_div = st.sidebar.slider("최소 배당률 (%)", 0.0, 10.0, st.session_state.min_div)

# ---- 차트 시각화 설정 ----
st.sidebar.markdown("🧩 차트 옵션 설정")
enable_div = st.sidebar.checkbox("배당률로 크기 표현", value=True)

# ---- 종목 입력 ----
tickers_input = st.text_input("✅ 종목 코드를 입력하세요", st.session_state.tickers_input)
tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# ---- 포트폴리오 저장/불러오기 버튼 ----
if st.sidebar.button("💾 포트폴리오 저장"):
    save_portfolio(tickers, max_per, min_up, min_drop, min_div)
    st.sidebar.success("✅ 포트폴리오가 저장되었습니다.")

if st.sidebar.button("📂 포트폴리오 불러오기"):
    portfolio = load_portfolio()
    if portfolio:
        st.session_state["tickers_input"] = ", ".join(portfolio["tickers"])
        st.session_state["max_per"] = portfolio["max_per"]
        st.session_state["min_up"] = portfolio["min_up"]
        st.session_state["min_drop"] = portfolio["min_drop"]
        st.session_state["min_div"] = portfolio["min_div"]
        st.rerun()
    else:
        st.sidebar.warning("❗ 저장된 포트폴리오가 없습니다.")

# ---- 투자 등급 분류 ----
def classify(row):
    score = 0
    if row['고점대비 (%)'] <= -min_drop: score += 1
    if row['상승여력 (%)'] >= min_up: score += 1
    if row['PER'] <= max_per: score += 1
    if row['배당률 (%)'] >= min_div: score += 1
    if score >= 3:
        return '🔥🔥🔥 초적극 매수'
    elif score == 2:
        return '🔥🔥 적극 매수'
    elif score == 1:
        return '🔥 매수'
    else:
        return '👀 관망'

# ---- 투자 요약 ----
def generate_summary(row):
    summary = f"📌 **{row['종목']}** | 현재가: ${row['현재가']}, 고점대비: {row['고점대비 (%)']}%, 상승여력: {row['상승여력 (%)']}%, PER: {row['PER']}, 배당률: {row['배당률 (%)']}%\n"
    if '🔥🔥🔥' in row['투자등급']:
        summary += "👉 **초적극 매수** 추천. 가격 매력과 성장성이 매우 우수합니다."
    elif '🔥🔥' in row['투자등급']:
        summary += "✅ **적극 매수** 구간입니다. 기준 대부분 충족."
    elif '🔥' in row['투자등급']:
        summary += "👌 **매수 고려** 가능. 일부 지표는 기준 미달."
    else:
        summary += "⚠️ **관망 추천**. 현재 매수에는 신중해야 합니다."
    return summary

# ---- 색상 강조 ----
def color_by_grade(val):
    if '🔥🔥🔥' in val: return 'background-color: red; color: white'
    if '🔥🔥' in val: return 'background-color: green; color: white'
    if '🔥' in val: return 'background-color: yellow; color: black'
    if '👀' in val: return 'background-color: gray; color: white'
    return ''

def highlight_per(s): return ['background-color: #d1f7d6' if v <= max_per else '' for v in s]
def highlight_drop(s): return ['background-color: #d1e0f7' if v <= -min_drop else '' for v in s]
def highlight_up(s): return ['background-color: #fff0b3' if v >= min_up else '' for v in s]
def highlight_div(s): return ['background-color: #fde2e2' if v >= min_div else '' for v in s]

# ---- 분석 시작 ----
data = []
if st.button("📊 분석 시작"):
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get("currentPrice", 0)
            high = info.get("fiftyTwoWeekHigh", 1)
            low = info.get("fiftyTwoWeekLow", 1)
            per = info.get("trailingPE", 999)
            pbr = info.get("priceToBook", 0)
            dividend = info.get("dividendRate", 0)
            고점대비 = ((price / high) - 1) * 100
            상승여력 = ((high - price) / (high - low)) * 100 if high != low else 0
            배당률 = (dividend / price) * 100 if price > 0 else 0
            data.append({
                '종목': ticker,
                '현재가': price,
                '52주 고점': high,
                '52주 저점': low,
                'PER': per,
                'PBR': pbr,
                '배당금': dividend,
                '고점대비 (%)': round(고점대비, 2),
                '상승여력 (%)': round(상승여력, 2),
                '배당률 (%)': round(배당률, 2),
            })
        except Exception as e:
            st.error(f"{ticker} 정보 수집 실패: {e}")

    df = pd.DataFrame(data)
    df['투자등급'] = df.apply(classify, axis=1)
    st.session_state.df = df

# ---- 결과 출력 ----
df = st.session_state.df
if df is not None:
    styled_df = df.style.applymap(color_by_grade, subset=['투자등급'])
    styled_df = styled_df.apply(highlight_per, subset=['PER'])
    styled_df = styled_df.apply(highlight_drop, subset=['고점대비 (%)'])
    styled_df = styled_df.apply(highlight_up, subset=['상승여력 (%)'])
    styled_df = styled_df.apply(highlight_div, subset=['배당률 (%)'])
    st.dataframe(styled_df, use_container_width=True)

    st.subheader("🧠 AI 투자 요약")
    grade_order = {'🔥🔥🔥 초적극 매수': 0, '🔥🔥 적극 매수': 1, '🔥 매수': 2, '👀 관망': 3}
    df['등급순서'] = df['투자등급'].map(grade_order)
    sorted_df = df.sort_values(by='등급순서')
    for i in range(len(sorted_df)):
        st.markdown(generate_summary(sorted_df.iloc[i]))

    st.subheader("📈 투자 지표 대시보드")
    col1, col2, col3 = st.columns(3)

    with col1:
        grade_colors = alt.Scale(
            domain=['🔥🔥🔥 초적극 매수', '🔥🔥 적극 매수', '🔥 매수', '👀 관망'],
            range=['salmon', 'LightPink', 'LightSkyBlue', 'dodgerBlue']
        )
        chart = alt.Chart(df).mark_bar().encode(
            x='투자등급', y='count()', color=alt.Color('투자등급', scale=grade_colors)
        ).properties(title="투자등급 분포", height=300)
        st.altair_chart(chart, use_container_width=True)

    with col2:
        size_encoding = alt.Size('배당률 (%)', scale=alt.Scale(type='sqrt', range=[30, 200]), legend=alt.Legend(title='배당률 (%)')) if enable_div else alt.value(100)
        color_encoding = alt.Color('투자등급', scale=grade_colors)

        chart2 = alt.Chart(df).mark_circle().encode(
            x=alt.X('PER', scale=alt.Scale(zero=False), title="PER (낮을수록 저평가)"),
            y=alt.Y('상승여력 (%)', title="상승여력 (%) (높을수록 좋음)"),
            size=size_encoding,
            color=color_encoding,
            tooltip=['종목', 'PER', '상승여력 (%)', '고점대비 (%)', '배당률 (%)', '투자등급']
        ).interactive().properties(title="💡 PER vs 상승여력 vs 배당률", height=300)

        st.altair_chart(chart2, use_container_width=True)

    with col3:
        heatmap = alt.Chart(df).mark_bar().encode(
            x=alt.X('고점대비 (%)', title='고점대비 하락률 (%)'),
            y=alt.Y('종목', sort='x'),
            color=alt.Color('고점대비 (%)', scale=alt.Scale(scheme='redyellowblue', reverse=True), legend=alt.Legend(title='고점대비 (%)')),
            tooltip=['종목', '고점대비 (%)']
        ).properties(title='📉 고점대비 하락률', height=300)

        st.altair_chart(heatmap, use_container_width=True)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 분석 결과 다운로드", csv, "investment_analysis.csv", "text/csv")
