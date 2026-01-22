import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

# --- 參數設定 ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def get_potential_stocks():
    print("正在從熱門池掃描具備『5 年 3 倍』潛力的標的...")
    try:
        # 改抓成交量前 150 名，這包含了所有具備流動性的中小型成長股
        url = "https://tw.stock.yahoo.com/ranking/volume?type=tse"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers)
        df = pd.read_html(res.text)[0]
        
        candidate_data = []
        for _, row in df.head(150).iterrows(): # 擴大池子
            raw_text = str(row['股票名稱']).split(' ')
            if len(raw_text) >= 2:
                candidate_data.append({"symbol": f"{raw_text[0]}.TW", "name": raw_text[1], "id": raw_text[0]})

        symbols = [item['symbol'] for item in candidate_data]
        # 批次下載數據，提升速度
        data = yf.download(symbols, period="5y", group_by='ticker', progress=False)
        
        ultra_long_picks = []
        for item in candidate_data:
            s = item['symbol']
            if s not in data or data[s].empty: continue
            df_hist = data[s].dropna()
            if len(df_hist) < 400: continue # 確保有足夠數據

            curr_price = df_hist['Close'].iloc[-1]
            five_yr_high = df_hist['Close'].max()
            five_yr_low = df_hist['Close'].min()
            ma200 = df_hist['Close'].rolling(window=200).mean().iloc[-1]
            
            # --- 5 年 3 倍策略優化 ---
            # A. 位階空間：距離 5 年高點仍有 35% 以上空間 (低位階)
            is_deep_value = curr_price < (five_yr_high * 0.65)
            # B. 底部保護：相對於 5 年低點，漲幅不超過 100% (避免已漲過頭)
            is_not_sky_high = curr_price < (five_yr_low * 2.0)
            # C. 趨勢轉強：股價在年線 (MA200) 的 10% 範圍內 (代表築底完成準備轉強)
            is_near_ma200 = curr_price > (ma200 * 0.9)
            
            if is_deep_value and is_not_sky_high and is_near_ma200:
                ultra_long_picks.append({
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "dist_to_high": round(((five_yr_high - curr_price) / curr_price) * 100, 1)
                })
        return ultra_long_picks
    except Exception as e:
        print(f"掃描失敗: {e}")
        return []

def get_stock_news(cname):
    try:
        url = f"https://news.google.com/rss/search?q={cname}+研發+OR+市佔+OR+全球+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        # 修正原本 "\n".join() 的空參數錯誤
        return "\n".join([f"• {i.title.text}" for i in items]) if items else "• 暫無長線產業布局訊息"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    potentials = get_potential_stocks()
    if not potentials:
        msg = "💡 盤勢位階偏高，目前暫無符合『超長線 5 年倍增』低位階標的。"
    else:
        msg = "🏛️ **【長線價值佈局】5 年 3 倍潛力股掃描**\n"
        msg += "----------------------------\n"
        for s in potentials:
            news = get_stock_news(s['name'])
            yahoo_link = f"https://tw.stock.yahoo.com/quote/{s['id']}" # 修正連結
            msg += f"🎯 **{s['name']} ({s['id']})**\n"
            msg += f"現價：{s['price']} | 距 5 年高點仍有：{s['dist_to_high']}% 空間\n"
            msg += f"狀態：✅ 歷史低位築底完成\n"
            msg += f"{news}\n"
            msg += f"🔗 [查看 5 年大週期圖表]({yahoo_link})\n"
            msg += "----------------------------\n"
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})

if __name__ == "__main__":
    run_analysis()
