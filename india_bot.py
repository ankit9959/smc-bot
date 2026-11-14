import os, time, requests
from datetime import datetime, timezone, timedelta
import smc_bot

IST = timezone(timedelta(hours=5, minutes=30))
HDR = {"User-Agent": "Mozilla/5.0"}
DEFAULT_INDIA_TOKEN = "9172379674:AAG_8SVUycnOtWkDTNYnPt9-BQBSy1HXaOY"

INDICES = [
    ("NIFTY 50", "%5ENSEI", 65, 50),
    ("FINNIFTY", "NIFTY_FIN_SERVICE.NS", 60, 50),
]

_last_candle_ts = {}
_daily_date = None
_daily_count = 0

def send_india_telegram(msg):
    tok = os.environ.get("INDIA_TELEGRAM_TOKEN", "").strip() or DEFAULT_INDIA_TOKEN
    cid = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or getattr(smc_bot, "TELEGRAM_CHAT_ID", "")
    if not tok or not cid:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print("India TG err:", e)

def _ema(vals, n):
    out = [vals[0]] * len(vals); k = 2 / (n + 1)
    for i in range(1, len(vals)): out[i] = vals[i] * k + out[i-1] * (1 - k)
    return out

def scan_india_5m_ema():
    global _daily_date, _daily_count
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return
    today = now.date()
    if _daily_date != today:
        _daily_date = today
        _daily_count = 0
    if _daily_count >= 1:
        return
    mins = now.hour * 60 + now.minute
    if mins < 9*60 + 20 or mins > 15*60 + 25:
        return

    for name, sym, lot, step in INDICES:
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=5m", headers=HDR, timeout=10).json()["chart"]["result"][0]
            q, ts = r["indicators"]["quote"][0], r["timestamp"]
            cd = [{"t":ts[k],"h":float(q["high"][k]),"l":float(q["low"][k]),"c":float(q["close"][k])} for k in range(len(ts)) if q["open"][k] and q["close"][k]]
            if len(cd) < 210: continue
            cd = cd[:-1]
            cl = [x["c"] for x in cd]; e9 = _ema(cl,9); e21 = _ema(cl,21); e200 = _ema(cl,200)
            i = len(cd) - 1
            if _last_candle_ts.get(name) == cd[i]["t"]:
                continue
            opt_type = None
            if e9[i] > e21[i] and e9[i-1] <= e21[i-1] and cl[i] > e200[i]:
                opt_type = "CE"; sl = min(x["l"] for x in cd[i-5:i+1])
            elif e9[i] < e21[i] and e9[i-1] >= e21[i-1] and cl[i] < e200[i]:
                opt_type = "PE"; sl = max(x["h"] for x in cd[i-5:i+1])
            if opt_type:
                _last_candle_ts[name] = cd[i]["t"]
                entry = cl[i]; risk = abs(entry - sl)
                if risk <= 0 or risk / entry < 0.0005 or risk / entry > 0.01:
                    continue
                _daily_count += 1
                be = entry + risk if opt_type == "CE" else entry - risk
                tp = entry + 2*risk if opt_type == "CE" else entry - 2*risk
                atm = round(entry / step) * step
                otm = (atm + step) if opt_type == "CE" else (atm - step)
                msg = (
                    f"<b>INDIA 5M EMA (1/1 DAILY): {name} {opt_type}</b>\n"
                    f"Spot Entry: {entry:.2f}\n"
                    f"Strike (1-OTM): {otm} {opt_type} (Lot {lot})\n"
                    f"Index SL: {sl:.2f}\n"
                    f"1:1 Cost-to-Cost: {be:.2f}\n"
                    f"1:2 Target: {tp:.2f}\n"
                    f"Time: {now.strftime('%H:%M:%S')} IST"
                )
                send_india_telegram(msg)
                break
        except Exception as e:
            print(f"India scan err {name}:", e)

def run_india_loop():
    send_india_telegram("<b>INDIA 5M EMA BOT ONLINE</b>\nIndices: NIFTY 50 & FINNIFTY\nLimit: 1 Trade/Day | Time: 09:20-15:25 IST")
    while True:
        try:
            scan_india_5m_ema()
        except Exception as e:
            print("India loop err:", e)
        time.sleep(60)
