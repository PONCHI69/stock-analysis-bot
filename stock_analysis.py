import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

# --- 參數設定 ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
VOL_RATIO_THRESHOLD = 2.0  # 成交量是 5 日均量的 2 倍以上
MIN_CHANGE_PERCENT = 2.0   # 今日漲幅至少要 2% 才有攻擊力
BIAS_LIMIT = 8.0           # 乖離率限制，避免追高
MA_WINDOW = 20

def get_potential_stocks():
    print("正在掃描市場潛力標的...")
    try:
        # 1. 獲取成交量排行 (台股上市)
        url = "https://tw.stock.yahoo.com/ranking/volume?type=tse"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df = pd.read_html(res.text)[0]
        
        candidate_data = []
        for _, row in df.head(30).iterrows():
            raw_text = str(row['股票名稱']).split(' ')
            if len(raw_text) >= 2:
                candidate_data.append({"symbol": f"{raw_text[0]}.TW", "name": raw_text[1], "id": raw_text[0]})

        symbols = [item['symbol'] for item in candidate_data]
        
        # 2. 批次抓取歷史數據
        data = yf.download(symbols, period="40d", group_by='ticker', progress=False)
        
        potential_matches = []
        for item in candidate_data:
            s = item['symbol']
            if s not in data or data[s].empty: continue
            
            df_hist = data[s].dropna()
            if len(df_hist) < MA_WINDOW + 1: continue

            # --- 指標計算 ---
            curr_price = df_hist['Close'].iloc[-1]
            prev_price = df_hist['Close'].iloc[-2]
            change_percent = ((curr_price - prev_price) / prev_price) * 100
            
            # 量能：今日量 vs 5日均量
            current_vol = df_hist['Volume'].iloc[-1]
            avg_vol_5d = df_hist['Volume'].iloc[-6:-1].mean()
            vol_ratio = current_vol / avg_vol_5d

            # 均線：MA20
            ma20 = df_hist['Close'].rolling(window=MA_WINDOW).mean()
            curr_ma20 = ma20.iloc[-1]
            prev_ma20 = ma20.iloc[-2]
            
            # 乖離率 (距離月線多遠)
            bias = ((curr_price - curr_ma20) / curr_ma20) * 100

            # --- 篩選條件 ---
            # 1. 起漲突破：昨天在線下，今天收盤在線上
            is_breakthrough = (prev_price <= prev_ma20) and (curr_price > curr_ma20)
            # 2. 趨勢向上：MA20 斜率為正 (或持平)
            is_ma_up = curr_ma20 >= prev_ma20
            # 3. 攻擊力：漲幅超過門檻且沒追高
            is_strong = change_percent >= MIN_CHANGE_PERCENT and bias < BIAS_LIMIT

            if is_breakthrough and is_ma_up and is_strong:
                potential_matches.append({
                    "symbol": s,
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "change": round(change_percent, 2),
                    "vol_ratio": round(vol_ratio, 2),
                    "reason": "🔥 爆量強攻" if vol_ratio >= VOL_RATIO_THRESHOLD
