import yfinance as yf
import pandas as pd
import os
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def send_to_discord(msg):
    payload = {"content": f"📈 **股市分析報報**\n{msg}"}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def analyze_stock(stock_id):
    # 抓取最近 60 天的資料以確保計算 MA20 與 MA60 準確
    df = yf.download(stock_id, period="60d")
    
    if df.empty:
        return f"找不到股票 {stock_id} 的資料"
    
    # 計算 20日線(月線) 與 60日線(季線)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    price = float(df['Close'].iloc[-1])
    ma20 = float(df['MA20'].iloc[-1])
    
    # 簡單分析邏輯：站上月線
    status = "🔴 偏弱"
    if price > ma20:
        status = "🟢 偏強 (站在月線上方)"
    
    return f"**{stock_id}**\n當前股價：{price:.2f}\n20日均線：{ma20:.2f}\n目前狀態：{status}"

if __name__ == "__main__":
    # 加入鴻海的代號 2317.TW
    target_stocks = ["2317.TW", "2330.TW", "0050.TW", "NVDA"]
    for s in target_stocks:
        analyze_stock(s)
    
    report = ""
    for s in mystocks:
        result = analyze_stock(s)
        report += result + "\n" + "-"*20 + "\n"
    
    send_to_discord(report)
