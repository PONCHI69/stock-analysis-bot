import yfinance as yf
import pandas as pd
import requests
import os
from bs4 import BeautifulSoup
import time

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def get_potential_stocks():
    """從 Yahoo 抓取熱門股清單並篩選具備潛力的個股"""
    print("正在掃描市場潛力標的...")
    # 這裡我們抓取「成交量排行」作為掃描池，因為有量才有潛力
    try:
        url = "https://tw.stock.yahoo.com/ranking/volume?type=tse"
        df = pd.read_html(url)[0]
        # 取前 30 檔熱門股進行深度掃描
        candidate_list = df.head(30)
        
        potential_matches = []
        for _, row in candidate_list.iterrows():
            raw_text = str(row['股票名稱']).split(' ')
            symbol, name = raw_text[0], raw_text[1]
            full_symbol = f"{symbol}.TW"
            
            # 獲取技術面數據
            stock = yf.Ticker(full_symbol)
            df_hist = stock.history(period="40d")
            if len(df_hist) < 25: continue

            # --- 計算指標 ---
            # 1. 量能：今日成交量 vs 5日均量
            current_vol = df_hist['Volume'].iloc[-1]
            avg_vol_5d = df_hist['Volume'].iloc[-6:-1].mean()
            vol_ratio = current_vol / avg_vol_5d

            # 2. 均線：計算 MA20
            ma20 = df_hist['Close'].rolling(window=20).mean()
            curr_price = df_hist['Close'].iloc[-1]
            prev_price = df_hist['Close'].iloc[-2]
            curr_ma20 = ma20.iloc[-1]
            prev_ma20 = ma20.iloc[-2]

            # --- 潛力股條件 ---
            # 條件 A: 帶量 (比均量大 1.5 倍)
            # 條件 B: 突破 (昨天在月線下，今天在月線上)
            # 條件 C: 趨勢 (月線趨勢向上)
            is_vol_spike = vol_ratio > 1.5
            is_breakthrough = (prev_price <= prev_ma20) and (curr_price > curr_ma20)
            is_ma_up = curr_ma20 >= prev_ma20

            if is_breakthrough and is_ma_up:
                potential_matches.append({
                    "symbol": full_symbol,
                    "name": name,
                    "price": curr_price,
                    "vol_ratio": vol_ratio,
                    "reason": "帶量突破月線" if is_vol_spike else "均線扣抵轉強"
                })
        return potential_matches
    except Exception as e:
        print(f"掃描失敗: {e}")
        return []

def get_stock_news(cname):
    try:
        url = f"https://news.google.com/rss/search?q={cname}+展望+OR+亮點+when:24h&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2]
        return "\n".join([f"• {i.title.text}" for i in items]) if items else "• 暫無相關產業亮點報導"
    except:
        return "• 新聞讀取失敗"

def run_analysis():
    potentials = get_potential_stocks()
    
    if not potentials:
        msg = "💡 今日盤中暫無符合「帶量突破」條件的潛力股。"
    else:
        msg = "🌟 **【潛力飆股預警】技術面突破掃描**\n"
        msg += "----------------------------\n"
        for s in potentials:
            news = get_stock_news(s['name'])
            msg += f"🎯 **{s['name']} ({s
