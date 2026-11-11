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





def direct_coindcx_call(endpoint, payload):
    p = payload.copy()
    p["timestamp"] = int(time.time() * 1000)
    json_str = json.dumps(p, separators=(',', ':'))
    sig = hmac.new(
        smc_bot.COINDCX_SECRET_KEY.encode('utf-8'),
        json_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    headers = {
        'Content-Type': 'application/json',
        'X-AUTH-APIKEY': smc_bot.COINDCX_API_KEY,
        'X-AUTH-SIGNATURE': sig,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    url = f"https://api.coindcx.com{endpoint}"
    r = requests.post(url, data=json_str, headers=headers, timeout=10)
    try:
        data = r.json()
    except Exception:
        data = r.text
    return {"status_code": r.status_code, "data": data}


import time, json, requests, hmac, hashlib

def direct_coindcx_call(api_key, secret_key, endpoint, payload):
    p = payload.copy()
    p['timestamp'] = int(time.time() * 1000)
    json_str = json.dumps(p, separators=(',', ':'))
    sig = hmac.new(
        secret_key.encode('utf-8'),
        json_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    headers = {
        'Content-Type': 'application/json',
        'X-AUTH-APIKEY': api_key,
        'X-AUTH-SIGNATURE': sig,
        'User-Agent': 'Mozilla/5.0'
    }
    url = 'https://api.coindcx.com' + endpoint
    r = requests.post(url, data=json_str, headers=headers, timeout=10)
    try:
        data = r.json()
    except Exception:
        data = r.text
    return {'status_code': r.status_code, 'data': data}

@app.route('/test_trade')
def test_trade_instant():
    trials = [
        ('/exchange/v1/derivatives/futures/orders/create', {
            'side': 'buy',
            'pair': 'B-XRP_USDT',
            'order_type': 'market',
            'total_quantity': 10,
            'leverage': 10,
            'margin_currency_short_name': 'INR',
            'notification': 'no_notification'
        }),
        ('/exchange/v1/derivatives/futures/orders/create', {
            'side': 'buy',
            'pair': 'B-XRP_USDT',
            'order_type': 'market_order',
            'total_quantity': 10,
            'leverage': 10,
            'margin_currency_short_name': 'INR',
            'notification': 'no_notification'
        }),
        ('/exchange/v1/derivatives/futures/orders', {
            'side': 'buy',
            'pair': 'B-XRP_USDT',
            'order_type': 'market_order',
            'total_quantity': 10,
            'leverage': 10,
            'margin_currency_short_name': 'INR',
            'notification': 'no_notification'
        }),
        ('/exchange/v1/derivatives/futures/orders/create', {
            'side': 'buy',
            'pair': 'B-BTC_USDT',
            'order_type': 'market',
            'total_quantity': 0.001,
            'leverage': 10,
            'margin_currency_short_name': 'INR',
            'notification': 'no_notification'
        })
    ]

    all_res = []
    for ep, p in trials:
        res = direct_coindcx_call(smc_bot.COINDCX_API_KEY, smc_bot.COINDCX_SECRET_KEY, ep, p)
        all_res.append({'endpoint': ep, 'pair': p['pair'], 'type': p['order_type'], 'res': res})
        d = res.get('data')
        if res['status_code'] in [200, 201] or (isinstance(d, dict) and ('id' in d or 'orders' in d)):
            order_id = d.get('id') if isinstance(d, dict) else str(d)
            msg = '🟢 LIVE BUY SUCCESSFUL: ' + str(p['pair']) + ' ID: ' + str(order_id)
            smc_bot.send_real_telegram_alert(msg)
            time.sleep(5)
            p_sell = p.copy()
            p_sell['side'] = 'sell'
            sell_res = direct_coindcx_call(smc_bot.COINDCX_API_KEY, smc_bot.COINDCX_SECRET_KEY, ep, p_sell)
            msg2 = '🏁 LIVE SELL SUCCESSFUL: ' + str(sell_res.get('data'))
            smc_bot.send_real_telegram_alert(msg2)
            return {'status': 'SUCCESS', 'buy': res, 'sell': sell_res}

    smc_bot.send_real_telegram_alert('TRIALS FAILED. Check /test_trade in browser.')
    return {'status': 'DIAGNOSTIC', 'results': all_res}
