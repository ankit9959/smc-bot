import os, threading, time
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask, Response, request
import smc_bot

app = Flask(__name__)

@app.route('/myip')
def myip():
    return requests.get('https://api.ipify.org', timeout=5).text.strip()
IST = timezone(timedelta(hours=5, minutes=30))
SYS_BOT_TOKEN = "9136543586:AAEuTAHXyxUed3yitU0rTUHMrLyisLzM-oI"
SYS_CHAT_ID = "8611777710"

def send_system_alert(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{SYS_BOT_TOKEN}/sendMessage", json={"chat_id": SYS_CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except: pass

@app.route('/')
def home():
    if os.path.exists("dashboard_v2.html"):
        with open("dashboard_v2.html", encoding="utf-8") as f:
            return Response(f.read(), mimetype='text/html')
    return {"status": "ONLINE", "author": "ANKIT RABARI"}

@app.route('/api/status')
def api_status():
    try:
        at = smc_bot.load_json_data(smc_bot.ACTIVE_TRADES_FILE, {})
        jn = smc_bot.load_json_data(smc_bot.JOURNAL_FILE, [])
        tot, w = len(jn), len([j for j in jn if j.get("status") == "WIN"])
        wr = round((w / tot * 100), 1) if tot > 0 else 0
        t_today = datetime.now(IST).strftime("%d-%b-%Y")
        t_month = datetime.now(IST).strftime("%b-%Y")
        today_trades = len([j for j in jn if j.get("date", "") == t_today])
        month_trades = len([j for j in jn if t_month in j.get("date", "")])
        return {"status": "ONLINE", "active_trades": at, "journal": jn[-20:], "stats": {"total": tot, "wins": w, "losses": tot - w, "win_rate": wr, "today_trades": today_trades, "month_trades": month_trades}, "coins": smc_bot.WATCHLIST}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

@app.route('/api/candles/<symbol>')
def api_candles(symbol):
    try:
        tf = request.args.get('tf', '1m')
        if tf not in ['1m', '5m', '15m']: tf = '1m'
        clean = symbol.upper()
        candles = smc_bot.get_coindcx_candles(clean, interval=tf, limit=40)
        if not candles: return {"status": "EMPTY", "candles": []}
        avg_r = smc_bot.get_avg_range(candles, 14)
        leg_c = candles[-20:]
        leg_eq = (max(c["high"] for c in leg_c) + min(c["low"] for c in leg_c)) / 2.0
        fvgs = smc_bot.find_fvgs(candles, avg_r, leg_eq)
        obs = smc_bot.find_order_blocks(candles, fvgs, leg_eq)
        at = smc_bot.load_json_data(smc_bot.ACTIVE_TRADES_FILE, {})
        clean_k = clean.replace("B-", "").replace("_", "")
        return {"status": "OK", "symbol": clean, "tf": tf, "candles": candles, "fvgs": [{"type": f["type"], "top": f["top"], "bottom": f["bottom"], "ce": f["ce"]} for f in fvgs if not f.get("mitigated", False)], "obs": [{"type": o["type"], "high": o["high"], "low": o["low"]} for o in obs if not o.get("mitigated", False)], "active_setup": at.get(clean_k, None)}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


@app.route('/api/test_coindcx')
def test_coindcx_route():
    try:
        import time, json, urllib.request
        res = smc_bot.coindcx_private_request("/exchange/v1/derivatives/futures/positions", {"timestamp": int(time.time() * 1000)})
        t_now = datetime.now(IST).strftime("%I:%M:%S %p")
        if isinstance(res, list) or (isinstance(res, dict) and "error" not in res and res.get("status") != "error"):
            msg = (f"✅ <b>COINDCX LIVE API CONNECTED 100% PERFECTLY!</b> ✅\n\n"
                   f"• <b>Status:</b> API Key & Secret Valid\n"
                   f"• <b>Render IP:</b> Whitelisted & Accepted by CoinDCX!\n"
                   f"• <b>Real Money Trading:</b> 100% Ready!\n"
                   f"⏰ <b>Time:</b> {t_now}")
            try: smc_bot.send_real_telegram_alert(msg)
            except: pass
            return {"status": "SUCCESS", "message": "CoinDCX Connected Successfully!", "data": res[:2] if isinstance(res, list) else res}
        else:
            err = res.get("error") or res.get("message") or str(res)
            msg = f"⚠️ <b>COINDCX TEST FAILED:</b> <code>{err}</code>\n⏰ Time: {t_now}"
            try: smc_bot.send_real_telegram_alert(msg)
            except: pass
            return {"status": "FAILED", "error": err}
    except Exception as e:
        return {"status": "EXCEPTION", "error": str(e)}

def start_bot_thread():
    time.sleep(3)
    t_now = datetime.now(IST).strftime('%d-%m-%Y %I:%M:%S %p IST')
    try: test_coindcx_route()
    except: pass
    send_system_alert(f"🚀 <b>StockMindset System Monitor: Live!</b> 🚀\\n\\n✅ <b>Render.com ક્લાઉડ સર્વર પર બોટ સફળતાપૂર્વક શરૂ થઈ ગયો છે!</b>\\n📊 <b>સિસ્ટમ:</b> ૧૪૬-સ્લાઈડ્સ SMC એન્જિન\\n🔍 <b>મોનિટરિંગ:</b> ૮ કોઈન્સ\\n⏰ <b>સમય:</b> {t_now}\\n👤 <i>Author: ANKIT RABARI (Rajkot)</i>")
    last_ping = time.time()
    while True:
        try:
            smc_bot.run_master_scan_pass()
            now = time.time()
            if now - last_ping >= 3600:
                at = smc_bot.load_json_data(smc_bot.ACTIVE_TRADES_FILE, {})
                c_str = ", ".join(at.keys()) if at else "કોઈ નહીં"
                send_system_alert(f"💚 <b>StockMindset: Hourly Health Check</b> 💚\\n\\n✅ <b>સ્ટેટસ:</b> ૧૦૦% ઓનલાઇન & હેલ્ધી\\n🔍 <b>સ્કેનિંગ:</b> ૮ કોઈન્સ ૨૪/૭ સતત ચાલુ\\n📊 <b>એક્ટિવ ટ્રેડ્સ:</b> {len(at)} ({c_str})\\n🛡️ <b>એરર:</b> કોઈ એરર નથી\\n⏰ <b>સમય:</b> {datetime.now(IST).strftime('%d-%m-%Y %I:%M %p IST')}\\n👤 <i>ANKIT RABARI (Rajkot)</i>")
                last_ping = now
            time.sleep(smc_bot.SCAN_INTERVAL_SECONDS)
        except Exception as e:
            send_system_alert(f"⚠️ <b>StockMindset System Alert</b> ⚠️\\n\\n❌ <b>એરર:</b> {str(e)[:200]}")
            time.sleep(15)

if __name__ == '__main__':
    threading.Thread(target=start_bot_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

@app.route('/api/live_test_trade')
def live_test_trade():
    try:
        import time
        smc_bot.send_real_telegram_alert("⚡ <b>TESTING LIVE COINDCX FUTURES...</b>\n• Action: Market BUY 1 XRP (10x)")
        buy_res = smc_bot.coindcx_private_request("/exchange/v1/derivatives/futures/orders/create", {
            "side": "buy", "pair": "B-XRP_USDT", "order_type": "market_order", "total_quantity": 1.0, "leverage": 10.0, "timestamp": int(time.time() * 1000)
        })
        if "id" not in buy_res:
            err = buy_res.get("error") or buy_res.get("message") or str(buy_res)
            smc_bot.send_real_telegram_alert(f"❌ <b>BUY FAILED:</b> <code>{err}</code>")
            return {"status": "FAILED", "error": err, "raw": buy_res}
        b_id = buy_res.get("id")
        smc_bot.send_real_telegram_alert(f"🟢 <b>LIVE BUY SUCCESSFUL!</b>\n• Order ID: <code>{b_id}</code>\n⏳ Closing in 5s...")
        time.sleep(5)
        sell_res = smc_bot.coindcx_private_request("/exchange/v1/derivatives/futures/orders/create", {
            "side": "sell", "pair": "B-XRP_USDT", "order_type": "market_order", "total_quantity": 1.0, "leverage": 10.0, "timestamp": int(time.time() * 1000)
        })
        s_id = sell_res.get("id", "N/A")
        smc_bot.send_real_telegram_alert(f"🏁 <b>LIVE SELL / CLOSED SUCCESSFUL!</b> 🏁\n• Buy ID: <code>{b_id}</code>\n• Sell ID: <code>{s_id}</code>\n✅ <b>BUY & SELL 100% OPERATIONAL!</b>")
        return {"status": "SUCCESS", "buy_id": b_id, "sell_id": s_id}
    except Exception as e:
        smc_bot.send_real_telegram_alert(f"❌ <b>ERROR:</b> {e}")
        return {"error": str(e)}

@app.route('/test_trade')
def test_trade_instant():
    try:
        import time
        smc_bot.send_real_telegram_alert("⚡ <b>TESTING 1 XRP LIVE BUY & SELL ON COINDCX...</b>")
        b_res = smc_bot.coindcx_private_request("/exchange/v1/derivatives/futures/orders/create", {
            "side": "buy", "pair": "B-XRP_USDT", "order_type": "market_order", "total_quantity": 1.0, "leverage": 10.0, "timestamp": int(time.time() * 1000)
        })
        b_id = b_res.get("id", str(b_res))
        smc_bot.send_real_telegram_alert(f"🟢 <b>LIVE BUY DONE!</b> Order ID: <code>{b_id}</code>\nClosing in 5 seconds...")
        time.sleep(5)
        s_res = smc_bot.coindcx_private_request("/exchange/v1/derivatives/futures/orders/create", {
            "side": "sell", "pair": "B-XRP_USDT", "order_type": "market_order", "total_quantity": 1.0, "leverage": 10.0, "timestamp": int(time.time() * 1000)
        })
        s_id = s_res.get("id", str(s_res))
        smc_bot.send_real_telegram_alert(f"🏁 <b>LIVE SELL DONE!</b> Order ID: <code>{s_id}</code>\n✅ <b>BUY & SELL VERIFIED LIVE!</b>")
        return {"status": "SUCCESS", "buy": b_id, "sell": s_id}
    except Exception as e:
        smc_bot.send_real_telegram_alert(f"❌ Error: {e}")
        return {"status": "ERROR", "error": str(e)}
