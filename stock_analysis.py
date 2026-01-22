import requests
import yfinance as yf
import os
import pandas as pd
from bs4 import BeautifulSoup
import time

# 設定您的 Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def get_all_taiwan_stock_symbols():
    """
    抓取台股所有上市櫃股票代碼
    這裡簡化流程，示範抓取上市股票，建議實務上可讀取本地 CSV 檔提升速度
    """
    try:
        # 爬取證交所的公開代碼 (此處為示意，建議預先存好 list 以免被封)
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
        res = requests.get(url)
        df = pd.read_html(res.text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[2:]
        # 分離代碼與名稱 "2330　台積電"
        stocks = df['有價證券代號及名稱'].str.split('　', expand=True)
        # 過濾出純數字代碼 (排除權證、ETF等，視需求調整)
        stocks = stocks[stocks[0].str.len() == 4]
        return dict(zip(stocks[0] + ".TW", stocks[1]))
    except Exception as e:
        print(f"獲取股票清單失敗: {e}")
        return {}

def get_stock_news(cname):
    # (保持原有的 get_stock_news 函數內容)
    try:
        url = f"https://news.google.com/rss/search?q={cname}+產業+OR+展望+when:24h&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        items = soup.find_all('item')[:2] # 縮減為 2 則以縮減訊息長度
        news_list = [f"• {i.title.text}" for i in items]
        return "\n".join(news_list) if news_list else "• 暫無今日即時報導"
    except:
        return "• 新聞讀取失敗"

def get_stock_analysis():
    # 1. 獲取全市場清單
    all_stocks = get_all_taiwan_stock_symbols()
    
    # 如果股票太多，Discord 會有字數限制 (2000字)，建議設定篩選門檻
    report_content = "🚀 **全市場異動股掃描 (漲幅 > 5% 或 站上月線)**\n"
    report_content += "----------------------------\n"
    
    count = 0
    for symbol, cname in all_stocks.items():
        try:
            # 限制分析數量，避免 Discord 爆掉或被 yfinance 封鎖
            if count > 15: break 

            stock = yf.Ticker(symbol)
            # 抓取 1 個月資料來計算 MA
            hist = stock.history(period="1mo")
            if len(hist) < 20: continue

            current_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            change_percent = ((current_price - prev_price) / prev_price) * 100

            # --- 篩選邏輯：只回報「強勢股」或「剛站上月線」的股票 ---
            is_strong = change_percent >= 5
            is_breakthrough = (prev_price < ma20) and (current_price > ma20)

            if is_strong or is_breakthrough:
                news_summary = get_stock_news(cname)
                fire_prefix = "🔥 " if is_strong else "⭐ "
                
                report_content += f"{fire_prefix}**{cname} ({symbol})**\n"
                report_content += f"現價：{current_price:.2f} ({'+' if change_percent > 0 else ''}{change_percent:.2f}%)\n"
                report_content += f"技術：{'✅ 突破月線' if is_breakthrough else '✅ 強勢噴發'}\n"
                report_content += f"{news_summary}\n"
                report_content += "----------------------------\n"
                
                count += 1
                # 稍微延遲避免頻率過快
                time.sleep(0.5)

        except Exception as e:
            continue

    # 5. 發送 (注意 Discord 訊息長度限制)
    if count > 0:
        payload = {"content": report_content}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    else:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": "今日全市場無符合篩選條件之股票。"})

if __name__ == "__main__":
    get_stock_analysis()
