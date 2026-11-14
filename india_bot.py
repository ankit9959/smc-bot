DEFAULT_INDIA_TOKEN = "9172379674:AAG_8SVUycnOtWkDTNYnPt9-BQBSy1HXaOY"
import os, time, requests, threading
from datetime import datetime, timezone, timedelta
import smc_bot, angel_api

IST = timezone(timedelta(hours=5, minutes=30))
HDR = {"User-Agent": "Mozilla/5.0"}

INDICES = [
    ("BANKNIFTY", "%5ENSEBANK", 30, 100, (250, 300)),
    ("FINNIFTY", "NIFTY_FIN_SERVICE.NS", 60, 50, (125, 150)),
    ("NIFTY 50", "%5ENSEI", 65, 50, (100, 150)),
]

_last_candle_ts = {}
_daily_date = None
_daily_count = 0
_active_india = {}
_done_today = set()
_cap = float(os.environ.get("INDIA_CAPITAL", "16000"))
_upd_off = None

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

def _poll_tg_cmds():
    global _cap, _upd_off
    tok = os.environ.get("INDIA_TELEGRAM_TOKEN", "").strip() or DEFAULT_INDIA_TOKEN
    cid = str(os.environ.get("TELEGRAM_CHAT_ID", "").strip() or getattr(smc_bot, "TELEGRAM_CHAT_ID", ""))
    if not tok or not cid: return
    try:
        prm = {"timeout": 1} if _upd_off is None else {"offset": _upd_off, "timeout": 1}
        res = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", params=prm, timeout=5).json().get("result", [])
        if _upd_off is None:
            _upd_off = (res[-1]["update_id"] + 1) if res else 0; return
        for u in res:
            _upd_off = u["update_id"] + 1
            m = u.get("message", {})
            if str(m.get("chat", {}).get("id", "")) != cid: continue
            txt = m.get("text", "").strip().lower()
            if txt in ("/on", "on"):
                angel_api._auto_trade = True
                send_india_telegram("<b>AUTO-TRADE: ON 🟢</b>\nReal Angel One Orders Active!")
            elif txt in ("/off", "off"):
                angel_api._auto_trade = False
                send_india_telegram("<b>AUTO-TRADE: OFF 🔴</b>\nPaper Mode Active")
            elif txt in ("/bt1y", "bt1y"):
                send_india_telegram("Running 1-Year Angel Backtest (~20s)...")
                threading.Thread(target=lambda: send_india_telegram(angel_api.run_1y_backtest()), daemon=True).start()
            elif txt in ("/test", "test"):
                out = ["<b>ANGEL CONTRACT TEST:</b>"]
                for nm, sym, lot, step, pr in INDICES:
                    try:
                        cd_t, src_t = _get_candles(nm, sym)
                        spot = cd_t[-1]["c"]
                        atm = round(spot / step) * step
                        osym, otok, rlot, ltp = angel_api.find_option_by_price(nm, atm, step, "CE", pr[0], pr[1])
                        out.append(f"{nm} ({src_t}): {osym} | Lot {rlot} | LTP ₹{ltp}")
                    except Exception as ex:
                        out.append(f"{nm}: ERR {ex}")
                send_india_telegram("\n".join(out))
            elif txt in ("/status", "status"):
                b = angel_api.get_balance()
                m = "ON 🟢" if angel_api._auto_trade else "OFF 🔴 (Paper)"
                send_india_telegram(f"<b>STATUS:</b> {m}\nBalance: ₹{b:,.2f}" if b is not None else f"<b>STATUS:</b> {m}")
            elif txt.startswith("/bal") or txt.startswith("bal"):
                parts = txt.replace("/bal", "").replace("bal", "").strip().split()
                if parts and parts[0].replace(".", "", 1).isdigit(): _cap = float(parts[0])
                real_b = angel_api.get_balance()
                b = real_b if real_b is not None else _cap
                send_india_telegram(f"<b>Wallet Balance: ₹{b:,.2f}</b>")
    except Exception: pass

def _close_trade(name, tr, live_price, title):
    global _cap
    qty = tr["lots"] * tr["lot"]
    ord_note = ""
    if tr.get("opt_sym") and tr.get("opt_tok"):
        ok, res = angel_api.place_order(tr["opt_sym"], tr["opt_tok"], qty, "SELL")
        ord_note = f"\nOrder SELL: {'ID ' + str(res) if ok else res}"
    res_r = ((live_price - tr["entry"]) if tr["type"] == "CE" else (tr["entry"] - live_price)) / tr["risk"]
    mins_held = max(5.0, (time.time() - tr["entry_ts"]) / 60.0)
    net = (res_r * tr["risk"] * 0.35 * qty) - ((mins_held / 5.0) * 0.15 * qty) - (55.0 + 10.0 * (tr["lots"] - 1))
    _cap += net
    real_b = angel_api.get_balance()
    bal_str = f"₹{real_b:,.2f}" if real_b is not None else f"₹{_cap:,.0f}"
    send_india_telegram(f"<b>{title}: {name} {tr['type']} ({tr['lots']}L)</b>\nSpot: {live_price:.2f} | Wallet: {bal_str}{ord_note}")
    _active_india.pop(name, None)

def _get_candles(name, sym):
    cd = angel_api.get_5m_candles(name)
    if cd and len(cd) >= 210: return cd, "Angel"
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=5d&interval=5m", headers=HDR, timeout=10).json()["chart"]["result"][0]
    q, ts = r["indicators"]["quote"][0], r["timestamp"]
    return [{"t":ts[k],"h":float(q["high"][k]),"l":float(q["low"][k]),"c":float(q["close"][k])} for k in range(len(ts)) if q["open"][k] and q["close"][k]], "Yahoo"

def _check_active_trades(name, live_price, now):
    tr = _active_india.get(name)
    if not tr: return
    mins = now.hour * 60 + now.minute
    if mins >= 15*60 + 20:
        _close_trade(name, tr, live_price, "EOD EXIT (03:20 PM)"); return
    hit_sl = (live_price <= tr["sl"]) if tr["type"] == "CE" else (live_price >= tr["sl"])
    if hit_sl:
        st = tr["step"]
        msg = "SL Hit" if st == 0 else ("1:1 Cost-to-Cost BE Exit" if st == 1 else f"Trailing SL Hit (Locked 1:{st-1} Profit!)")
        _close_trade(name, tr, live_price, msg); return
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
    for name, sym, lot, step, pr in INDICES:
        try:
            cd, _ = _get_candles(name, sym)
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
                real_b = angel_api.get_balance()
                bal = real_b if real_b is not None else _cap
                atm = round(entry / step) * step
                opt_sym, opt_tok, real_lot, opt_ltp = angel_api.find_option_by_price(name, atm, step, opt_type, pr[0], pr[1])
                lot_use = real_lot or lot
                cost1 = (opt_ltp * lot_use) if opt_ltp else (pr[1] * lot_use)
                lots = min(max(1, int(bal // 16000)), int(bal // cost1)) if bal >= cost1 else 0
                if lots <= 0:
                    _done_today.add(name)
                    send_india_telegram(f"<b>SKIPPED {name}:</b> Bal ₹{bal:,.0f} < 1 Lot ₹{cost1:,.0f}")
                    continue
                qty = lots * lot_use
                ord_msg = "No Contract"
                if opt_sym and opt_tok:
                    ok, res = angel_api.place_order(opt_sym, opt_tok, qty, "BUY")
                    ord_msg = f"BUY ID {res}" if ok else res
                _daily_count += 1; _done_today.add(name)
                be = entry + risk if opt_type == "CE" else entry - risk
                _active_india[name] = {"type": opt_type, "entry": entry, "risk": risk, "sl": sl, "step": 0, "lots": lots, "lot": lot_use, "entry_ts": time.time(), "opt_sym": opt_sym, "opt_tok": opt_tok}
                ltp_s = f"₹{opt_ltp:.2f}" if opt_ltp else "N/A"
                send_india_telegram(f"<b>INDIA 5M EMA ({_daily_count}/3): {name} {opt_type}</b>\nContract: {opt_sym or atm} | LTP: {ltp_s}\nLots: {lots} ({qty} Qty) | Bal: ₹{bal:,.0f}\nSpot: {entry:.2f} | SL: {sl:.2f} | BE: {be:.2f}\nOrder: {ord_msg}")
        except Exception as e:
            print(f"India scan err {name}:", e)

def run_india_loop():
    _poll_tg_cmds()
    ang_msg = angel_api.test_angel_login()
    send_india_telegram(f"<b>INDIA 5M EMA BOT ONLINE (PRO)</b>\n{ang_msg}\nDays: Tue / Wed / Fri | 09:20-10:30 & 13:30-15:15")
    while True:
        try:
            _poll_tg_cmds()
            scan_india_5m_ema()
        except Exception as e: print("India loop err:", e)
        time.sleep(30)
