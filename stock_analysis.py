import yfinance as yf
import pandas as pd
import os
import requests

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def send_to_discord(msg):
    # 增加檢查，避免沒內容也發送
    if not msg.strip():
        return
    payload = {"content": f"📈 **股市分析報報**\n{msg}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"發送失敗: {e}")

def analyze_stock(stock_id):
    # 下載最近 60 天的資料，使用 multi_level_index=False 確保欄位名稱簡單好讀
    df = yf.download(stock_id, period="60d", multi_level_index=False)
    
    if df.empty:
        return f"❌ 找不到股票 {stock_id} 的資料"
    
    # 計算 20日線(月線) 與 60日線(季線)
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # 取得最新一筆資料
    price = float(df['Close'].iloc[-1])
    ma20 = float(df['MA20'].iloc[-1])
    
    # 分析邏輯
    status = "🔴 偏弱 (月線下方)"
    if price > ma20:
        status = "🟢 偏強 (站在月線上方)"
    
    return f"**{stock_id}**\n當前股價：{price:.2f}\n20日均線：{ma20:.2f}\n目前狀態：{status}"

if __name__ == "__main__":
    # 統一使用同一個變數名稱
    target_stocks = ["2317.TW", "2330.TW", "0050.TW", "NVDA"]
    
    report = ""
    for s in target_stocks:
        print(f"正在分析 {s}...")
        result = analyze_stock(s)
        report += result + "\n" + "-"*20 + "\n"
    
    # 最終彙整後只發送一則訊息
    send_to_discord(report)
