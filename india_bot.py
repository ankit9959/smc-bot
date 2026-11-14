import os, time, requests
from datetime import datetime, timezone, timedelta
import smc_bot

IST = timezone(timedelta(hours=5, minutes=30))
HDR = {"User-Agent": "Mozilla/5.0"}
DEFAULT_INDIA_TOKEN = "9172379674:AAG_8SVUycnOtWkDTNYnPt9-BQBSy1HXaOY"

INDICES = [
    ("BANKNIFTY", "%5ENSEBANK", 30, 100),
    ("FINNIFTY", "NIFTY_FIN_SERVICE.NS", 60, 50),
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
    if not tr:
        return
    mins = now.hour * 60 + now.minute
    if mins >= 15*60 + 20:
        send_india_telegram(f"<b>EOD EXIT (03:20 PM): {name} {tr['type']}</b>\nSpot: {live_price:.2f}\nClose Intraday Trade (No Overnight!)")
        _active_india.pop(name, None)
        return
    if tr["type"] == "CE":
        if live_price <= tr["sl"]:
            msg = "1:1 Cost-to-Cost BE Exit" if tr["be_done"] else "SL Hit"
            send_india_telegram(f"<b>{msg}: {name} CE</b>\nSpot: {live_price:.2f}")
            _active_india.pop(name, None)
        elif not tr["be_done"] and live_price >= tr["be"]:
            tr["be_done"] = True; tr["sl"] = tr["entry"]
            send_india_telegram(f"<b>1:1 REACHED (Move SL to Cost): {name} CE</b>\nSpot: {live_price:.2f} | New SL: {tr['entry']:.2f}")
        elif live_price >= tr["tp"]:
            send_india_telegram(f"<b>1:2 TARGET HIT: {name} CE</b>\nSpot: {live_price:.2f} | Book Full Profit!")
            _active_india.pop(name, None)
    else:
        if live_price >= tr["sl"]:
            msg = "1:1 Cost-to-Cost BE Exit" if tr["be_done"] else "SL Hit"
            send_india_telegram(f"<b>{msg}: {name} PE</b>\nSpot: {live_price:.2f}")
            _active_india.pop(name, None)
        elif not tr["be_done"] and live_price <= tr["be"]:
            tr["be_done"] = True; tr["sl"] = tr["entry"]
            send_india_telegram(f"<b>1:1 REACHED (Move SL to Cost): {name} PE</b>\nSpot: {live_price:.2f} | New SL: {tr['entry']:.2f}")
        elif live_price <= tr["tp"]:
            send_india_telegram(f"<b>1:2 TARGET HIT: {name} PE</b>\nSpot: {live_price:.2f} | Book Full Profit!")
            _active_india.pop(name, None)

def scan_india_5m_ema():
    global _daily_date, _daily_count
    now = datetime.now(IST)
    if now.weekday() >= 5:
        return
    today = now.date()
    if _daily_date != today:
        _daily_date = today; _daily_count = 0; _active_india.clear(); _done_today.clear()
    mins = now.hour * 60 + now.minute
    if mins < 9*60 + 20 or mins > 15*60 + 25:
        return

    for name, sym, lot, step in INDICES:
        try:
            r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=5m", headers=HDR, timeout=10).json()["chart"]["result"][0]
            q, ts = r["indicators"]["quote"][0], r["timestamp"]
            cd = [{"t":ts[k],"h":float(q["high"][k]),"l":float(q["low"][k]),"c":float(q["close"][k])} for k in range(len(ts)) if q["open"][k] and q["close"][k]]
            if len(cd) < 210: continue
            _check_active_trades(name, cd[-1]["c"], now)
            if name in _active_india or name in _done_today or _daily_count >= 2 or mins > 15*60 + 15:
                continue
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
                _daily_count += 1; _done_today.add(name)
                be = entry + risk if opt_type == "CE" else entry - risk
                tp = entry + 2*risk if opt_type == "CE" else entry - 2*risk
                atm = round(entry / step) * step
                otm = (atm + step) if opt_type == "CE" else (atm - step)
                _active_india[name] = {"type": opt_type, "entry": entry, "sl": sl, "be": be, "tp": tp, "be_done": False}
                msg = (
                    f"<b>INDIA 5M EMA ({_daily_count}/2): {name} {opt_type}</b>\n"
                    f"Spot Entry: {entry:.2f}\n"
                    f"Strike (1-OTM): {otm} {opt_type} (Lot {lot})\n"
                    f"Index SL: {sl:.2f}\n"
                    f"1:1 Cost-to-Cost: {be:.2f}\n"
                    f"1:2 Target: {tp:.2f}\n"
                    f"Time: {now.strftime('%H:%M:%S')} IST"
                )
                send_india_telegram(msg)
        except Exception as e:
            print(f"India scan err {name}:", e)

def run_india_loop():
    send_india_telegram("<b>INDIA 5M EMA BOT ONLINE (PRO)</b>\nIndices: BANKNIFTY & FINNIFTY\nMax 1 Each/Day (2/Day) | Live BE/TP/EOD 3:20 PM Alerts")
    while True:
        try:
            scan_india_5m_ema()
        except Exception as e:
            print("India loop err:", e)
        time.sleep(30)
