import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

# --- 參數設定 ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def get_potential_stocks():
    print("正在執行『長線強勢回檔』潛力股掃描...")
    try:
        # 1. 抓取成交量排行 (前 150 名) 以確保流動性
        url = "https://tw.stock.yahoo.com/ranking/volume?type=tse"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(res.text)[0]
        
        candidate_data = []
        for _, row in df.head(150).iterrows():
            parts = str(row['股票名稱']).split(' ')
            if len(parts) >= 2:
                candidate_data.append({"symbol": f"{parts[0]}.TW", "name": parts[1], "id": parts[0]})

        symbols = [item['symbol'] for item in candidate_data]
        # 抓取 2 年資料分析趨勢即可，不須強求 5 年以維持效率
        data = yf.download(symbols, period="2y", group_by='ticker', progress=False)
        
        potential_picks = []
        for item in candidate_data:
            s = item['symbol']
            if s not in data or data[s].empty: continue
            df_hist = data[s].dropna()
            if len(df_hist) < 200: continue

            curr_price = df_hist['Close'].iloc[-1]
            prev_price = df_hist['Close'].iloc[-2]
            
            # 計算均線指標
            ma200_all = df_hist['Close'].rolling(window=200).mean()
            curr_ma200 = ma200_all.iloc[-1]
            prev_ma200_month = ma200_all.iloc[-20] # 一個月前的年線

            # --- 2026 實戰策略：強勢回測買點 ---
            # A. 長線趨勢向上：年線本身必須是往上走的 (月增幅 > 1%)
            is_uptrend = curr_ma200 > (prev_ma200_month * 1.01)
            
            # B. 精準買點：股價正好回測到年線支撐 (離年線上下 5% 內)
            is_at_support = (curr_price > curr_ma200 * 0.95) and (curr_price < curr_ma200 * 1.05)
            
            # C. 乖離限制：排除近期噴發過頭的 (距離 1 年高點不超過 30%)
            year_high = df_hist['Close'].iloc[-250:].max()
            is_not_overheated = curr_price < (year_high * 0.95)

            if is_uptrend and is_at_support and is_not_overheated:
                potential_picks.append({
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "change": round(((curr_price - prev_price) / prev_price) * 100, 2),
                    "reason": "🛡️ 強勢股回測年線 (長線支撐點)"
                })
        return potential_picks
    except Exception as e:
        print(f"掃描失敗: {e}")
        return []

def get_stock_news(cname):
    try:
        url = f"https://news.google.com/rss/search?q={cname}+訂單+OR+營收+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        return "\n".join([f"• {i.title.text}" for i in items]) if items else "• 暫無近期產業關鍵報導"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    picks = get_potential_stocks()
    if not picks:
        msg = "💡 目前盤勢位階高，多數強勢股尚未回測支撐，建議保留現金等待回調。"
    else:
        msg = "🎯 **【長線佈局計畫】績優強勢股回測掃描**\n"
        msg += "----------------------------\n"
        for s in picks:
            news = get_stock_news(s['name'])
            msg += f"🔥 **{s['name']} ({s['id']})**\n"
            msg += f"現價：{s['price']} ({s['change']:+}%)\n"
            msg += f"訊號：{s['reason']}\n"
            msg += f"【近期關鍵訊息】\n{news}\n"
            msg += f"🔗 [查看長線圖表](https://tw.stock.yahoo.com/quote/{s['id']})\n"
            msg += "----------------------------\n"
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})

if __name__ == "__main__":
    run_analysis()
