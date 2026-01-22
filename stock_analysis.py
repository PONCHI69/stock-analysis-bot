import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

# --- 參數設定 ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
VOL_RATIO_THRESHOLD = 2.0  # 成交量翻倍
MIN_CHANGE_PERCENT = 2.0   # 漲幅門檻
BIAS_LIMIT = 8.0           # 乖離率限制
MA_WINDOW = 20

def get_growth_stocks():
    print("正在掃描具備『翻倍潛力』的長線標的...")
    try:
        # 1. 抓取熱門股作為初始池 (或可自行更換為 0050 成分股)
        url = "https://tw.stock.yahoo.com"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df = pd.read_html(res.text)[0]
        
        candidate_data = []
        for _, row in df.head(50).iterrows():
            raw_text = str(row['股票名稱']).split(' ')
            if len(raw_text) >= 2:
                candidate_data.append({"symbol": f"{raw_text[0]}.TW", "name": raw_text[1], "id": raw_text[0]})

        symbols = [item['symbol'] for item in candidate_data]
        # 抓取 2 年的資料以確保 MA200 計算準確
        data = yf.download(symbols, period="2y", group_by='ticker', progress=False)
        
        long_term_picks = []
        for item in candidate_data:
            s = item['symbol']
            if s not in data or data[s].empty: continue
            df_hist = data[s].dropna()
            
            # 確保資料量足夠計算 MA200
            if len(df_hist) < 200: continue

            # --- [核心計算區] ---
            curr_price = df_hist['Close'].iloc[-1]
            two_year_high = df_hist['Close'].max()
            
            # 1. 長線均線指標 (MA200)
            ma200_all = df_hist['Close'].rolling(window=200).mean()
            curr_ma200 = ma200_all.iloc[-1]
            prev_ma200 = ma200_all.iloc[-20] # 20天前(約一個月)的年線

            # 2. 底部溫量指標
            avg_vol_short = df_hist['Volume'].iloc[-10:].mean()  # 近10日均量
            avg_vol_long = df_hist['Volume'].iloc[-120:].mean()  # 近半年均量

            # --- [強化版篩選條件] ---
            
            # 條件 A: 價格剛站上年線且乖離不大 (安全區)
            is_base_breakout = (curr_price > curr_ma200) and (curr_price < curr_ma200 * 1.2)
            
            # 條件 B: 年線趨勢走平或轉強 (避開下墜中的年線)
            # 2026 策略：年線下滑斜率不可超過 1%
            is_ma200_stable = curr_ma200 >= prev_ma200 * 0.99 
            
            # 條件 C: 底部溫量 (代表法人/大戶開始低檔佈局)
            is_volume_building = avg_vol_short > avg_vol_long
            
            # 條件 D: 歷史位階 (距離高點仍有空間)
            has_room = curr_price < (two_year_high * 0.8)

            # 條件 E: 獲利過濾 (選配)
            # 註：yf.Ticker 請求較慢，建議掃描量大時慎用
            # stock_info = yf.Ticker(s).info
            # is_profitable = stock_info.get('forwardEps', 0) > 0

            # --- [最終判定] ---
            if is_base_breakout and is_ma200_stable and is_volume_building and has_room:
                long_term_picks.append({
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "dist_to_high": round(((two_year_high - curr_price) / curr_price) * 100, 1)
                })
        
        return long_term_picks

    except Exception as e:
        print(f"掃描失敗: {e}")
        return []

def get_stock_news(cname):
    try:
        url = f"https://news.google.com/rss/search?q={cname}+股票+OR+營收+when:24h&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        return "\n".join([f"• {i.title.text}" for i in items]) if items else "• 暫無今日即時訊息"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    potentials = get_potential_stocks()
    
    if not potentials:
        msg = "💡 今日暫未掃描到符合條件之起漲點強勢股。"
    else:
        msg = "🌟 **【起漲潛力股掃描】量價齊揚預警**\n"
        msg += "----------------------------\n"
        for s in potentials:
            news = get_stock_news(s['name'])
            yahoo_link = f"https://tw.stock.yahoo.com/quote/{s['id']}"
            msg += f"🎯 **{s['name']} ({s['id']})**\n"
            msg += f"現價：{s['price']} ({s['change']:+}%)\n"
            msg += f"訊號：{s['reason']} (量比:{s['vol_ratio']}x)\n"
            msg += f"{news}\n"
            msg += f"🔗 [查看圖表]({yahoo_link})\n"
            msg += "----------------------------\n"

    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    else:
        print(msg)

if __name__ == "__main__":
    run_analysis()
