import requests
import yfinance as yf
import os

# 設定您的 Discord Webhook (記得要在新專案的 Settings > Secrets 裡設定)
DISCORD_WEBHOOK_URL = os.getenv("STOCK_WEBHOOK")

def get_stock_analysis():
    # 1. 定義您要追蹤的股票清單與中文化名稱
    # 格式為 "Yahoo代號": "中文簡稱"
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
            # 抓取最近一個月的歷史資料來計算月線 (20日)
            hist = stock.history(period="1mo")
            if hist.empty: continue

            current_price = hist['Close'].iloc[-1]
            ma20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            
            # 計算漲跌幅
            change_percent = ((current_price - prev_price) / prev_price) * 100
            
            # 漲跌圖示
            trend_emoji = "🔴" if change_percent < 0 else "🟢"
            
            # 技術面判斷 (站上或跌破月線)
            ma_status = "站上月線" if current_price > ma20 else "跌破月線"
            ma_emoji = "✅" if current_price > ma20 else "⚠️"

            # 組合訊息內容
            report_content += f"**{cname} ({symbol})**\n"
            report_content += f"現價：{current_price:.2f} ({trend_emoji} {change_percent:+.2f}%)\n"
            report_content += f"技術：{ma_emoji} {ma_status}\n"
            report_content += f"建議：{'觀望' if current_price < ma20 else '強勢持股'}\n"
            report_content += "----------------------------\n"

        except Exception as e:
            print(f"處理 {symbol} 時出錯: {e}")

    # 4. 發送到 Discord
    payload = {"content": report_content}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

if __name__ == "__main__":
    get_stock_analysis()
