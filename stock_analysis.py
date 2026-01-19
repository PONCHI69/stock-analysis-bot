import yfinance as yf
import pandas as pd
import os
import requests
from FinMind.data import DataLoader
from datetime import datetime, timedelta

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")
dl = DataLoader()

def send_to_discord(msg):
    if not msg.strip(): return
    payload = {"content": f"📈 **股市籌碼+技術面分析報報**\n{msg}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except:
        pass

def analyze_stock(stock_id):
    # 1. 抓取股價與名稱 (yfinance)
    ticker = yf.Ticker(stock_id)
    # 嘗試抓取中文名稱，若無則顯示代號
    stock_name = ticker.info.get('longName', stock_id)
    
    df = ticker.history(period="60d")
    if df.empty: return f"❌ {stock_id} 無法讀取股價"
    
    price = float(df['Close'].iloc[-1])
    ma20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
    
    # 2. 法人籌碼分析 (FinMind)
    sid = stock_id.replace(".TW", "")
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    sitc_buy_2days = False
    try:
        inst_df = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date=start_date)
        sitc = inst_df[inst_df['name'] == 'Investment_Trust'].tail(2)
        sitc_buy_days = (sitc['buy_sell'] > 0).sum()
        if sitc_buy_days >= 2:
            sitc_buy_2days = True
        chip_status = f"投信近2日買超天數: {sitc_buy_days}"
    except:
        chip_status = "⚠️ 暫無籌碼資料"

    # 3. 買入建議邏輯
    # 條件：站上月線 (MA20) 且 投信連買 2 天
    is_above_ma20 = price > ma20
    
    if is_above_ma20 and sitc_buy_2days:
        advice = "💡 **建議：可買入** (技術籌碼雙強)"
    elif is_above_ma20:
        advice = "🤔 **建議：觀望** (技術強但籌碼普通)"
    else:
        advice = "❌ **建議：不可買** (趨勢偏弱)"

    tech_status = "🟢 站上月線" if is_above_ma20 else "🔴 跌破月線"
    return f"**{stock_name} ({stock_id})**\n現價：{price:.2f} ({tech_status})\n籌碼：{chip_status}\n📢 {advice}"

if __name__ == "__main__":
    # 設定清單
    target_stocks = ["2317.TW", "2330.TW", "2454.TW", "NVDA"]
    report = ""
    for s in target_stocks:
        print(f"正在分析 {s}...")
        if ".TW" not in s:
            # 美股簡化處理
            ticker = yf.Ticker(s)
            p = float(ticker.history(period="1d")['Close'].iloc[-1])
            report += f"**{s}**\n現價：{p:.2f} (美股僅供參考)\n"
        else:
            report += analyze_stock(s) + "\n"
        report += "-"*20 + "\n"
    
    send_to_discord(report)
