import os
import threading
import time
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask
import smc_bot

app = Flask(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

SYS_BOT_TOKEN = "9136543586:AAEuTAHXyxUed3yitU0rTUHMrLyisLzM-oI"
SYS_CHAT_ID = "8611777710"

def send_system_alert(message):
    try:
        url = f"https://api.telegram.org/bot{SYS_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": SYS_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"System alert send error: {e}")

@app.route('/')
def home():
    return {
        "status": "ONLINE",
        "system": "StockMindset SMC 146-Slide Institutional Engine",
        "author": "ANKIT RABARI (Rajkot, Gujarat)",
        "message": "Bot is actively scanning 24/7 on Render Cloud!"
    }

def start_bot_thread():
    print("Starting SMC Bot Background Worker Thread on Cloud...")
    try:
        time.sleep(3)
        t_now = datetime.now(IST).strftime('%d-%m-%Y %I:%M:%S %p IST')
        startup_msg = (
            f"🚀 <b>StockMindset System Monitor: Live!</b> 🚀\n\n"
            f"✅ <b>Render.com ક્લાઉડ સર્વર પર બોટ સફળતાપૂર્વક શરૂ થઈ ગયો છે!</b>\n\n"
            f"📊 <b>સિસ્ટમ:</b> ૧૪૬-સ્લાઈડ્સ SMC એન્જિન (Trade With Ani)\n"
            f"🔍 <b>મોનિટરિંગ:</b> ૮ કોઈન્સ (BTC, ETH, SOL, XRP, BNB, DOGE, AVAX, NEAR)\n"
            f"🛡️ <b>ફિલ્ટર્સ:</b> Fresh POI, IDM Sweep, Market Structure, 1.0 ATR Safe SL\n"
            f"⚡ <b>સર્વર:</b> 24/7 Cloud (Render + Keep-Alive)\n"
            f"⏰ <b>સમય:</b> {t_now}\n\n"
            f"👤 <b>Author:</b> ANKIT RABARI (Rajkot, Gujarat)\n"
            f"📱 <b>Mo:</b> 7697667767\n"
            f"💡 <i>આ બોટ ફક્ત સર્વર સ્ટેટસ, હેલ્થ ચેક અને એરર એલર્ટ માટે છે. મુખ્ય ચાર્ટ્સ મેઈન બોટમાં જ આવશે.</i>"
        )
        send_system_alert(startup_msg)
        print("--> Startup alert sent to System Bot successfully!")
    except Exception as e:
        print(f"Startup System Alert Error: {e}")

    last_hourly_ping = time.time()
    while True:
        try:
            smc_bot.run_master_scan_pass()
            now_ts = time.time()
            if now_ts - last_hourly_ping >= 3600:
                try:
                    t_h = datetime.now(IST).strftime('%d-%m-%Y %I:%M %p IST')
                    active_trades_data = smc_bot.load_json_data(smc_bot.ACTIVE_TRADES_FILE, {})
                    active_cnt = len(active_trades_data)
                    active_coins = ", ".join(active_trades_data.keys()) if active_cnt > 0 else "કોઈ નહીં"
                    hourly_msg = (
                        f"💚 <b>StockMindset: Hourly Health Check</b> 💚\n\n"
                        f"✅ <b>સ્ટેટસ:</b> ૧૦૦% ઓનલાઇન & હેલ્ધી\n"
                        f"🔍 <b>સ્કેનિંગ:</b> ૮ કોઈન્સ ૨૪/૭ સતત ચાલુ\n"
                        f"📊 <b>એક્ટિવ ટ્રેડ્સ:</b> {active_cnt} ({active_coins})\n"
                        f"🛡️ <b>એરર:</b> કોઈ એરર નથી (All Systems Normal)\n"
                        f"⏰ <b>સમય:</b> {t_h}\n\n"
                        f"👤 <i>ANKIT RABARI (Rajkot)</i>"
                    )
                    send_system_alert(hourly_msg)
                    last_hourly_ping = now_ts
                except Exception as h_err:
                    print(f"Hourly ping error: {h_err}")
            time.sleep(smc_bot.SCAN_INTERVAL_SECONDS)
        except Exception as e:
            err_str = str(e)
            print(f"Scan pass error: {err_str}")
            try:
                t_err = datetime.now(IST).strftime('%I:%M:%S %p IST')
                err_msg = (
                    f"⚠️ <b>StockMindset System Alert</b> ⚠️\n\n"
                    f"❌ <b>એરર:</b> {err_str[:250]}\n"
                    f"⏰ <b>સમય:</b> {t_err}\n"
                    f"🔄 બોટ આપોઆપ રિકવરી કરી રહ્યો છે..."
                )
                send_system_alert(err_msg)
            except:
                pass
            time.sleep(15)

if __name__ == '__main__':
    t = threading.Thread(target=start_bot_thread, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
