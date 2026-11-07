import os, threading, time
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask, Response
import smc_bot

app = Flask(__name__)
IST = timezone(timedelta(hours=5, minutes=30))
SYS_BOT_TOKEN = "9136543586:AAEuTAHXyxUed3yitU0rTUHMrLyisLzM-oI"
SYS_CHAT_ID = "8611777710"

def send_system_alert(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{SYS_BOT_TOKEN}/sendMessage", json={"chat_id": SYS_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

@app.route('/')
def home():
    if os.path.exists("dashboard.html"):
        with open("dashboard.html", encoding="utf-8") as f:
            return Response(f.read(), mimetype='text/html')
    return {"status": "ONLINE", "author": "ANKIT RABARI"}

@app.route('/api/status')
def api_status():
    try:
        at = smc_bot.load_json_data(smc_bot.ACTIVE_TRADES_FILE, {})
        jn = smc_bot.load_json_data(smc_bot.JOURNAL_FILE, [])
        tot, w = len(jn), len([j for j in jn if j.get("status") == "WIN"])
        wr = round((w / tot * 100), 1) if tot > 0 else 0
        return {"status": "ONLINE", "active_trades": at, "journal": jn[-20:], "stats": {"total": tot, "wins": w, "losses": tot - w, "win_rate": wr}, "coins": smc_bot.WATCHLIST}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def start_bot_thread():
    time.sleep(3)
    t_now = datetime.now(IST).strftime('%d-%m-%Y %I:%M:%S %p IST')
    send_system_alert(f"🚀 <b>StockMindset System Monitor: Live!</b> 🚀\n\n✅ <b>Render.com ક્લાઉડ સર્વર પર બોટ સફળતાપૂર્વક શરૂ થઈ ગયો છે!</b>\n📊 <b>સિસ્ટમ:</b> ૧૪૬-સ્લાઈડ્સ SMC એન્જિન\n🔍 <b>મોનિટરિંગ:</b> ૮ કોઈન્સ\n⏰ <b>સમય:</b> {t_now}\n👤 <i>Author: ANKIT RABARI (Rajkot)</i>")
    last_ping = time.time()
    while True:
        try:
            smc_bot.run_master_scan_pass()
            now = time.time()
            if now - last_ping >= 3600:
                at = smc_bot.load_json_data(smc_bot.ACTIVE_TRADES_FILE, {})
                c_str = ", ".join(at.keys()) if at else "કોઈ નહીં"
                send_system_alert(f"💚 <b>StockMindset: Hourly Health Check</b> 💚\n\n✅ <b>સ્ટેટસ:</b> ૧૦૦% ઓનલાઇન & હેલ્ધી\n🔍 <b>સ્કેનિંગ:</b> ૮ કોઈન્સ ૨૪/૭ સતત ચાલુ\n📊 <b>એક્ટિવ ટ્રેડ્સ:</b> {len(at)} ({c_str})\n🛡️ <b>એરર:</b> કોઈ એરર નથી\n⏰ <b>સમય:</b> {datetime.now(IST).strftime('%d-%m-%Y %I:%M %p IST')}\n👤 <i>ANKIT RABARI (Rajkot)</i>")
                last_ping = now
            time.sleep(smc_bot.SCAN_INTERVAL_SECONDS)
        except Exception as e:
            send_system_alert(f"⚠️ <b>StockMindset System Alert</b> ⚠️\n\n❌ <b>એરર:</b> {str(e)[:200]}")
            time.sleep(15)

if __name__ == '__main__':
    threading.Thread(target=start_bot_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
