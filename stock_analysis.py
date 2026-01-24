import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def get_potential_stocks():
    print("正在執行精準化『長線 5 年倍增』掃描...")
    try:
        # 軌道一：抓取熱門成交股 (前 150 檔)
        url = "https://tw.stock.yahoo.com/ranking/volume?type=tse"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        df = pd.read_html(res.text)[0]
        
        candidate_data = []
        for _, row in df.head(150).iterrows():
            parts = str(row['股票名稱']).split(' ')
            if len(parts) >= 2:
                candidate_data.append({"symbol": f"{parts[0]}.TW", "name": parts[1], "id": parts[0]})

        # 軌道二：主動加入長線核心追蹤名單 (可自由增減)
        core_list = [
            {"symbol": "2330.TW", "name": "台積電", "id": "2330"},
            {"symbol": "2317.TW", "name": "鴻海", "id": "2317"},
            {"symbol": "2454.TW", "name": "聯發科", "id": "2454"},
            {"symbol": "2308.TW", "name": "台達電", "id": "2308"}
        ]
        candidate_data.extend(core_list)

        symbols = list(set([item['symbol'] for item in candidate_data]))
        data = yf.download(symbols, period="5y", group_by='ticker', progress=False)
        
        ultra_long_picks = []
        for item in candidate_data:
            s = item['symbol']
            if s not in data or data[s].empty: continue
            df_hist = data[s].dropna()
            if len(df_hist) < 400: continue

            curr_price = df_hist['Close'].iloc[-1]
            five_yr_high = df_hist['Close'].max()
            five_yr_low = df_hist['Close'].min()
            ma200 = df_hist['Close'].rolling(window=200).mean().iloc[-1]
            
            # --- 平衡後的長線策略 ---
            # A. 距離高點仍有 20% 空間即可 (適應目前的強勢盤)
            is_deep_value = curr_price < (five_yr_high * 0.8)
            # B. 趨勢門檻：只要股價接近或高於年線
            is_near_ma200 = curr_price > (ma200 * 0.95)
            # C. 底部保護：相對於 5 年低點漲幅不超過 150%
            is_not_sky_high = curr_price < (five_yr_low * 2.5)
            
            if is_deep_value and is_near_ma200 and is_not_sky_high:
                ultra_long_picks.append({
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "dist_to_high": round(((five_yr_high - curr_price) / curr_price) * 100, 1)
                })
        return ultra_long_picks
    except Exception as e:
        print(f"掃描出錯: {e}")
        return []

# get_stock_news 與 run_analysis 函數維持不變
def get_stock_news(cname):
    try:
        url = f"https://news.google.com/rss/search?q={cname}+研發+OR+市佔+OR+全球+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        return "\n".join([f"• {i.title.text}" for i in items]) if items else "• 暫無長線亮點報導"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    potentials = get_potential_stocks()
    if not potentials:
        msg = "💡 盤勢位階偏高，暫無符合長線佈局條件之標的。"
    else:
        msg = "🏛️ **【優化版長線佈局】5 年 3 倍潛力股掃描**\n"
        msg += "----------------------------\n"
        for s in potentials:
            news = get_stock_news(s['name'])
            msg += f"🎯 **{s['name']} ({s['id']})**\n"
            msg += f"現價：{s['price']} | 距 5 年高點尚有：{s['dist_to_high']}% 空間\n"
            msg += f"【長線動能分析】\n{news}\n"
            msg += f"🔗 [查看圖表](https://tw.stock.yahoo.com/quote/{s['id']})\n"
            msg += "----------------------------\n"
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})

if __name__ == "__main__":
    run_analysis()
