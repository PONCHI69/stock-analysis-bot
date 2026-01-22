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

def get_potential_stocks():
    print("正在掃描市場潛力標的...")
    try:
        # 1. 獲取成交量排行
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
        
        # 2. 批次抓取數據
        data = yf.download(symbols, period="40d", group_by='ticker', progress=False)
        
        potential_matches = []
        for item in candidate_data:
            s = item['symbol']
            if s not in data or data[s].empty: continue
            
            df_hist = data[s].dropna()
            if len(df_hist) < MA_WINDOW + 1: continue

            curr_price = df_hist['Close'].iloc[-1]
            prev_price = df_hist['Close'].iloc[-2]
            change_percent = ((curr_price - prev_price) / prev_price) * 100
            
            current_vol = df_hist['Volume'].iloc[-1]
            avg_vol_5d = df_hist['Volume'].iloc[-6:-1].mean()
            vol_ratio = current_vol / avg_vol_5d

            ma20 = df_hist['Close'].rolling(window=MA_WINDOW).mean()
            curr_ma20 = ma20.iloc[-1]
            prev_ma20 = ma20.iloc[-2]
            
            bias = ((curr_price - curr_ma20) / curr_ma20) * 100

            # 判斷條件
            is_breakthrough = (prev_price <= prev_ma20) and (curr_price > curr_ma20)
            is_ma_up = curr_ma20 >= prev_ma20
            is_strong = change_percent >= MIN_CHANGE_PERCENT and bias < BIAS_LIMIT

            if is_breakthrough and is_ma_up and is_strong:
                potential_matches.append({
                    "symbol": s,
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "change": round(change_percent, 2),
                    "vol_ratio": round(vol_ratio, 2),
                    "reason": "🔥 爆量強攻" if vol_ratio >= VOL_RATIO_THRESHOLD else "📈 技術轉強"
                })
        return potential_matches
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
