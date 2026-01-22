import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

# --- 參數設定 ---
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}

def get_all_tw_stock_codes():
    """從證交所網站抓取所有上市櫃股票代碼"""
    print("正在獲取所有上市櫃股票代碼...")
    # 上市股票 URL
    twse_url = 'https://isin.twse.com.tw'
    # 上櫃股票 URL
    tpex_url = 'https://isin.twse.com.tw'
    
    codes = []
    for url in [twse_url, tpex_url]:
        try:
            # 使用 pandas 讀取網頁表格
            tables = pd.read_html(url, encoding='big5', header=0)
            df = tables[0]
            # 選取代碼、名稱、市場別欄位
            df = df.iloc[:, [0, 1, 4]]
            df.columns = ['CodeName', 'ISIN', 'Market']
            # 過濾掉非股票項目，並提取代碼
            for row in df.itertuples():
                code_parts = row.CodeName.split('　') # 全形空格
                if len(code_parts) > 1 and len(code_parts[0]) == 4:
                    code = code_parts[0]
                    name = code_parts[1]
                    if code.isdigit(): # 確保是四位數的數字代碼
                        codes.append({"symbol": f"{code}.TW", "name": name, "id": code})
        except Exception as e:
            print(f"抓取 {url} 失敗: {e}")
            continue
    print(f"共找到 {len(codes)} 檔股票代碼。")
    return codes

def get_potential_stocks():
    print("正在掃描具備『5 年 3 倍』潛力的超長線標的...")
    candidate_data = get_all_tw_stock_codes()
    symbols = [item['symbol'] for item in candidate_data]
    
    # 抓取 5 年的資料 (所有股票需要較長時間下載)
    # yfinance download 批次處理有上限，可能會在這裡失敗，若失敗需改為迴圈逐一抓取
    try:
        data = yf.download(symbols, period="5y", group_by='ticker', progress=True)
    except Exception as e:
        print(f"批次下載失敗，改為逐一抓取: {e}")
        data = {} # 重置 data
        for item in candidate_data:
            try:
                df = yf.Ticker(item['symbol']).history(period="5y")
                if not df.empty:
                    data[item['symbol']] = df
                time.sleep(0.5) # 避免過快請求被 ban
            except:
                continue
    
    ultra_long_picks = []
    for item in candidate_data:
        s = item['symbol']
        
        # --- 獲取基本面資料 ---
        is_financially_sound = False
        try:
            # 這裡需要單獨 Ticker 呼叫 info (速度較慢)
            stock_info = yf.Ticker(s).info
            total_debt = stock_info.get('totalDebt', 0)
            total_cash = stock_info.get('totalCash', 0)
            is_financially_sound = total_cash > total_debt if total_debt > 0 else True 
        except:
            pass # 如果抓不到資料就當作不符合，跳過

        if s not in data or data.get(s, {}).empty or not is_financially_sound: continue
        
        df_hist = data[s].dropna()
        if len(df_hist) < 500: continue # 確保有足夠的歷史數據

        curr_price = df_hist['Close'].iloc[-1]
        five_year_high = df_hist['Close'].max()
        five_year_low = df_hist['Close'].min()
        ma200 = df_hist['Close'].rolling(window=200).mean().iloc[-1]
        
        # --- 5 年 3 倍篩選邏輯 ---
        # A: 位階相對低 - 股價距離 5 年高點仍有 40% 以上空間 
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

# ... get_stock_news, run_analysis 函式保持不變 ...
def get_stock_news(cname):
    # ... (保持不變)
    try:
        url = f"https://news.google.com{cname}+研發+OR+市佔+OR+全球+when:7d&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        return "\n".join() if items else "• 暫無長線產業布局訊息"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    # ... (保持不變)
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
