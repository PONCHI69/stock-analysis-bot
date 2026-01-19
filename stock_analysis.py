import requests
import yfinance as yf
import os
from bs4 import BeautifulSoup

# 設定您的 Discord Webhook
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK")

def get_stock_news(cname):
    """針對個股抓取最新產業新聞摘要"""
    try:
        # 搜尋個股名稱 + 產業展望
        url = f"https://news.google.com/rss/search?q={cname}+產業+展望+when:24h&hl=zh-TW&gl=TW&ceid=TW:zh-tw"
        res = requests.get(url)
        soup = BeautifulSoup(res.content, features="xml")
        item = soup.find('item')
        if item:
            return f"📰 產業分析：{item.title.text[:40]}..."
        return "📰 產業分析：暫無今日即時報導"
    except:
        return "📰 產業分析：讀取失敗"

def get_stock_analysis():
    target_stocks = {
        "2317.TW": "鴻海",
        "2330.TW": "台積電",
        "2454.TW": "聯發科",
        "NVDA": "輝達",
        "AAPL": "蘋果"
    }
    
    report_content = "📈 **每日股市籌碼+技術面分析報報**\n"
    report_content += "----------------------------\n"

    for symbol, cname in target_stocks.items():
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1mo")
            if hist.empty: continue

            current_price = hist['Close'].iloc[-1]
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            
            change_percent = ((current_price - prev_price) / prev_price) * 100
            
            # --- 新增邏輯開始 ---
            # 1. 🔥 漲幅警示：超過 5% 就加火
            fire_prefix = "🔥 " if change_percent >= 5 else ""
            
            # 2. 漲跌圖示
            trend_emoji = "🔴" if change_percent < 0 else "🟢"
            
            # 3. 獲取產業新聞
            news_summary = get_stock_news(cname)
            
            # 4. 籌碼模擬 (因 yfinance 無台股籌碼，此處預留欄位，建議下午 3 點後參考盤後資訊)
            chip_info = "籌碼：盤後結算中" # 未來可串接證交所 API
            # --- 新增邏輯結束 ---

            ma_status = "站上月線" if current_price > ma20 else "跌破月線"
            ma_emoji = "✅" if current_price > ma20 else "⚠️"

            # 組合訊息內容 (加入 fire_prefix)
            report_content += f"{fire_prefix}**{cname} ({symbol})**\n"
            report_content += f"現價：{current_price:.2f} ({trend_emoji} {change_percent:+.2f}%)\n"
            report_content += f"技術：{ma_emoji} {ma_status}\n"
            report_content += f"{chip_info}\n"
            report_content += f"{news_summary}\n"
            report_content += f"建議：{'觀望' if current_price < ma20 else '強勢持股'}\n"
            report_content += "----------------------------\n"

        except Exception as e:
            print(f"處理 {symbol} 時出錯: {e}")

    # 發送到 Discord
    payload = {"content": report_content}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    get_stock_analysis()
