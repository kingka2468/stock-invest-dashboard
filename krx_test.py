import pandas as pd
from pykrx import stock

# 테스트를 위해 2025년 12월 23일(평일)로 강제 설정
target_str = "20251223" 
temp_df = stock.get_market_fundamental(target_str, market="ALL")
print(temp_df.head())