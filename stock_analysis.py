import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

# --- 參數設定 ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
# 設置 headers 避免被網站阻擋
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}

def get_potential_stocks():
    print("正在掃描具備『5 年 3 倍』潛力的超長線標的...")
    try:
        # 1. 擴大掃描範圍至 100 檔
        url = "https://tw.stock.yahoo.com"
        res = requests.get(url, headers=HEADERS)
        df = pd.read_html(res.text)[0]
        
        candidate_data = []
        for _, row in df.head(100).iterrows():
            raw_text = str(row['股票名稱']).split(' ')
            if len(raw_text) >= 2:
                candidate_data.append({"symbol": f"{raw_text[0]}.TW", "name": raw_text[1], "id": raw_text[0]})

        symbols = [item['symbol'] for item in candidate_data]
        # 2. 時間維度：抓取 5 年資料以分析超長線位階
        data = yf.download(symbols, period="5y", group_by='ticker', progress=False)
        
        ultra_long_picks = []
        for item in candidate_data:
            s = item['symbol']
            
            # --- 獲取基本面資料 ---
            # 這裡需要單獨 Ticker 呼叫 info (速度較慢，但長線策略頻率低可接受)
            try:
                stock_info = yf.Ticker(s).info
                total_debt = stock_info.get('totalDebt', 0)
                total_cash = stock_info.get('totalCash', 0)
                # 條件 D: 財務穩健性 - 現金多於負債
                is_financially_sound = total_cash > total_debt if total_debt > 0 else True 
            except:
                is_financially_sound = False # 如果抓不到資料就跳過

            if s not in data or data[s].empty or not is_financially_sound: continue
            
            df_hist = data[s].dropna()
            # 確保有足夠的歷史數據 (5年約 1200 交易日)
            if len(df_hist) < 500: continue

            curr_price = df_hist['Close'].iloc[-1]
            five_year_high = df_hist['Close'].max()
            five_year_low = df_hist['Close'].min()
            
            # 計算 200 日年線
            ma200 = df_hist['Close'].rolling(window=200).mean().iloc[-1]
            
            # --- 5 年 3 倍篩選邏輯 ---
            # A: 位階相對低 - 股價距離 5 年高點仍有 40% 以上空間 (調整為 40%)
            is_deep_value = curr_price < (five_year_high * 0.6) 
            
            # B: 底部支撐 - 股價目前高於 5 年最低點，但還沒暴漲 (距離低點漲幅小於 50%)
            is_above_floor = curr_price > five_year_low and curr_price < (five_year_low * 1.5)
            
            # C: 趨勢轉正 - 股價站上年線 (MA200)
            is_trend_ready = curr_price > ma200
            
            
            if is_deep_value and is_above_floor and is_trend_ready:
                ultra_long_picks.append({
                    "id": item['id'],
                    "name": item['name'],
                    "price": round(curr_price, 2),
                    "dist_to_high": round(((five_year_high - curr_price) / curr_price) * 100, 1),
                    "reason": "🏛️ 超長線價值區 (5年低位)"
                })
        
        return ultra_long_picks

    except Exception as e:
        print(f"掃描失敗: {e}")
        return []

def get_stock_news(cname):
    try:
        # 加入長線成長關鍵字：研發、市佔、專利
        url = f"https://news.google.com{cname}+研發+OR+市佔+OR+全球+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        return "\n".join() if items else "• 暫無長線產業布局訊息"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    potentials = get_potential_stocks()
    
    if not potentials:
        msg = "💡 目前暫未發現符合『超長線 5 年倍增』潛力之標的。"
    else:
        msg = "🏛️ **【超長線佈局計畫】5 年 3 倍潛力股掃描**\n"
        msg += "----------------------------\n"
        for s in potentials:
            news = get_stock_news(s['name'])
            yahoo_link = f"https://tw.stock.yahoo.com{s['id']}"
            msg += f"🎯 **{s['name']} ({s['id']})**\n"
            msg += f"現價：{s['price']} | 距 5 年高點仍有：{s['dist_to_high']}% 空間\n"
            msg += f"狀態：✅ 歷史低位築底完成\n"
            msg += f"{news}\n"
            msg += f"🔗 [查看 5 年大週期圖表]({yahoo_link})\n"
            msg += "----------------------------\n"

    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg})
    else:
        print(msg)

if __name__ == "__main__":
    run_analysis()
