import os, time, requests
from datetime import datetime, timezone, timedelta
import smc_bot

IST = timezone(timedelta(hours=5, minutes=30))
HDR = {"User-Agent": "Mozilla/5.0"}

INDICES = [
    ("BANKNIFTY", "%5ENSEBANK", 30, 100),
    ("FINNIFTY", "NIFTY_FIN_SERVICE.NS", 60, 50),
    ("NIFTY 50", "%5ENSEI", 65, 50),
]

_last_candle_ts = {}
_daily_date = None
_daily_count = 0
_active_india = {}
_done_today = set()

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

def _check_active_trades(name, live_price, now):
    tr = _active_india.get(name)
    if not tr: return
    mins = now.hour * 60 + now.minute
    if mins >= 15*60 + 20:
        send_india_telegram(f"<b>EOD EXIT (03:20 PM): {name} {tr['type']}</b>\nSpot: {live_price:.2f}\nClose Intraday Trade (No Overnight!)")
        _active_india.pop(name, None); return
    hit_sl = (live_price <= tr["sl"]) if tr["type"] == "CE" else (live_price >= tr["sl"])
    if hit_sl:
        st = tr["step"]
        msg = "SL Hit" if st == 0 else ("1:1 Cost-to-Cost BE Exit" if st == 1 else f"Trailing SL Hit (Locked 1:{st-1} Profit!)")
        send_india_telegram(f"<b>{msg}: {name} {tr['type']}</b>\nSpot: {live_price:.2f}")
        _active_india.pop(name, None); return
    r_now = ((live_price - tr["entry"]) if tr["type"] == "CE" else (tr["entry"] - live_price)) / tr["risk"]
    if r_now >= 1.0 and int(r_now) > tr["step"]:
        ns = int(r_now); tr["step"] = ns
        tr["sl"] = tr["entry"] + (ns - 1) * tr["risk"] if tr["type"] == "CE" else tr["entry"] - (ns - 1) * tr["risk"]
        lbl = "Move SL to Cost" if ns == 1 else f"Trail SL to 1:{ns-1}"
        send_india_telegram(f"<b>1:{ns} REACHED ({lbl}): {name} {tr['type']}</b>\nSpot: {live_price:.2f} | New SL: {tr['sl']:.2f}")

def scan_india_5m_ema():
    global _daily_date, _daily_count
    now = datetime.now(IST)
    if now.weekday() not in (1, 2, 4): return
    today = now.date()
    if _daily_date != today:
        _daily_date = today; _daily_count = 0; _active_india.clear(); _done_today.clear()
    mins = now.hour * 60 + now.minute
    if mins < 9*60 + 20 or mins > 15*60 + 25: return
    for name, sym, lot, step in INDICES:
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=5m", headers=HDR, timeout=10).json()["chart"]["result"][0]
            q, ts = r["indicators"]["quote"][0], r["timestamp"]
            cd = [{"t":ts[k],"h":float(q["high"][k]),"l":float(q["low"][k]),"c":float(q["close"][k])} for k in range(len(ts)) if q["open"][k] and q["close"][k]]
            if len(cd) < 210: continue
            _check_active_trades(name, cd[-1]["c"], now)
            in_win = (9*60+20 <= mins < 10*60+30) or (13*60+30 <= mins < 15*60+15)
            if name in _active_india or name in _done_today or _daily_count >= 3 or not in_win: continue
            cd = cd[:-1]; cl = [x["c"] for x in cd]
            e9, e21, e200 = _ema(cl, 9), _ema(cl, 21), _ema(cl, 200)
            i = len(cd) - 1
            if _last_candle_ts.get(name) == cd[i]["t"]: continue
            opt_type = None
            if e9[i] > e21[i] and e9[i-1] <= e21[i-1] and cl[i] > e200[i]:
                opt_type = "CE"; sl = min(x["l"] for x in cd[i-5:i+1])
            elif e9[i] < e21[i] and e9[i-1] >= e21[i-1] and cl[i] < e200[i]:
                opt_type = "PE"; sl = max(x["h"] for x in cd[i-5:i+1])
            if opt_type:
                _last_candle_ts[name] = cd[i]["t"]
                entry = cl[i]; risk = abs(entry - sl)
                if risk <= 0 or risk / entry < 0.0005 or risk / entry > 0.01: continue
                _daily_count += 1; _done_today.add(name)
                be = entry + risk if opt_type == "CE" else entry - risk
                atm = round(entry / step) * step
                otm = (atm + step) if opt_type == "CE" else (atm - step)
                _active_india[name] = {"type": opt_type, "entry": entry, "risk": risk, "sl": sl, "step": 0}
                send_india_telegram(f"<b>INDIA 5M EMA ({_daily_count}/3): {name} {opt_type}</b>\nSpot Entry: {entry:.2f}\nStrike (1-OTM): {otm} {opt_type} (Lot {lot})\nIndex SL: {sl:.2f}\n1:1 Cost-to-Cost: {be:.2f}\nTrail: Full Step till 3:20 PM\nTime: {now.strftime('%H:%M:%S')} IST")
        except Exception as e:
            print(f"India scan err {name}:", e)

def run_india_loop():
    send_india_telegram("<b>INDIA 5M EMA BOT ONLINE (PRO)</b>\nIndices: BANKNIFTY, FINNIFTY, NIFTY 50\nDays: Tue / Wed / Fri Only (No Mon/Thu)\n09:20-10:30 & 13:30-15:15 | Full Trail + 3:20 PM EOD")
    while True:
        try: scan_india_5m_ema()
        except Exception as e: print("India loop err:", e)
        time.sleep(30)
