import requests
import json
import streamlit as st

st.title("🧪 네이버 해외주식 API 연결 테스트")

# 테스트할 종목들
test_tickers = ["NVDA.O", "TSLA.O", "AAPL.O"]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://m.stock.naver.com/',
    'Accept': 'application/json, text/plain, */*'
}

for ticker in test_tickers:
    url = f"https://m.stock.naver.com/worldstock/api/stock/{ticker}/integration"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        st.subheader(f"🔍 종목: {ticker}")
        st.write(f"**상태 코드:** {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # 데이터 중 핵심 정보만 추출해서 출력
            name = data.get('stockName')
            price = data.get('closePrice')
            high52 = data.get('high52Weeks')
            
            if name:
                st.success(f"✅ 연결 성공! | 기업명: {name} | 현재가: {price} | 52주 고점: {high52}")
                # 전체 데이터를 확인하고 싶다면 아래 주석 해제
                # st.json(data)
            else:
                st.error("❌ 연결은 되었으나 데이터 구조가 다릅니다.")
                st.json(data) # 어떤 데이터가 왔는지 확인
        else:
            st.error(f"❌ 서버 응답 실패 (코드: {response.status_code})")
            
    except Exception as e:
        st.error(f"⚠️ 오류 발생: {str(e)}")