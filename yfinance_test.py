import yfinance as yf
import pandas as pd

def check_yfinance_status(ticker_symbol="AAPL"):
    print(f"--- {ticker_symbol} 데이터 호출 테스트 시작 ---")
    ticker = yf.Ticker(ticker_symbol)
    
    try:
        # 1. 주가 내역(History) 호출 테스트 - 가장 가벼운 요청
        print("1. 주가 내역(History) 시도 중...")
        hist = ticker.history(period="1d")
        if not hist.empty:
            print("✅ 주가 내역 호출 성공!")
            print(f"최근 종가: {hist['Close'].iloc[-1]}")
        else:
            print("❌ 주가 데이터가 비어 있습니다.")

        # 2. 기업 정보(Info) 호출 테스트 - 차단 여부 확인의 핵심
        print("\n2. 기업 정보(Info) 시도 중...")
        info = ticker.info
        if info and 'shortName' in info:
            print("✅ 기업 정보 호출 성공!")
            print(f"기업명: {info['shortName']}")
        else:
            print("❌ 기업 정보를 가져올 수 없습니다.")
            
    except Exception as e:
        print(f"\n🚨 에러 발생: {e}")
        if "429" in str(e) or "Too Many Requests" in str(e):
            print("⚠️ 결과: 현재 IP가 야후 파이낸스로부터 'Rate Limit' 차단을 당한 상태입니다.")
        else:
            print(f"⚠️ 결과: 알 수 없는 이유로 연결이 실패했습니다.")

if __name__ == "__main__":
    # 대표적인 우량주들로 테스트
    for t in ["AAPL", "NVDA"]:
        check_yfinance_status(t)
        print("-" * 40)