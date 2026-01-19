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
    payload = {"content": f"📈 **股市籌碼+技術面分析**\n{msg}"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except:
        pass

def analyze_stock(stock_id):
    # 1. 技術面分析 (yfinance)
    df = yf.download(stock_id, period="60d", multi_level_index=False)
    if df.empty: return f"❌ {stock_id} 無法讀取股價"
    
    price = float(df['Close'].iloc[-1])
    ma20 = float(df['Close'].rolling(window=20).mean().iloc[-1])
    
    # 2. 法人籌碼分析 (FinMind)
    sid = stock_id.replace(".TW", "")
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    try:
        inst_df = dl.taiwan_stock_institutional_investors(stock_id=sid, start_date=start_date)
        
        # 篩選投信 (Investment_Trust) 買賣超
        sitc = inst_df[inst_df['name'] == 'Investment_Trust'].tail(2)
        # 篩選外資 (Foreign_Investor) 最新一天
        foreign = inst_df[inst_df['name'] == 'Foreign_Investor'].iloc[-1]['buy_sell']
        
        # 核心邏輯：投信連買 2 天
        sitc_buy_days = (sitc['buy_sell'] > 0).sum()
        
        chip_status = "⚪ 籌碼普普通通"
        if sitc_buy_days >= 2:
            chip_status = "🔥 **預警：投信連買 2 天！** (大漲前兆)"
            if foreign > 0:
                chip_status += "\n🌟 **強烈預警：土洋大買！** (內外資看法一致)"
    except:
        chip_status = "⚠️ 無法取得法人資料 (非開盤日或尚未公布)"

    # 3. 彙整結果
    tech_status = "🟢 站在月線上" if price > ma20 else "🔴 跌破月線"
    return f"**{stock_id}**\n現價：{price:.2f} ({tech_status})\n籌碼面：{chip_status}"

if __name__ == "__main__":
    target_stocks = ["2317.TW", "2330.TW", "2454.TW", "NVDA"]
    report = ""
    for s in target_stocks:
        # 美股 NVDA 不支援 FinMind 籌碼分析，僅跑技術面
        if ".TW" not in s:
            df = yf.download(s, period="40d", multi_level_index=False)
            p = float(df['Close'].iloc[-1])
            report += f"**{s}**\n現價：{p:.2f} (美股僅分析技術面)\n"
        else:
            report += analyze_stock(s) + "\n"
        report += "-"*20 + "\n"
    
    send_to_discord(report)
