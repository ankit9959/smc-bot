import os, time, hmac, hashlib, struct, base64, requests
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
BASE = "https://apiconnect.angelone.in"
LOGIN_URL = f"{BASE}/rest/auth/angelbroking/user/v1/loginByPassword"
RMS_URL = f"{BASE}/rest/secure/angelbroking/user/v1/getRMS"
LTP_URL = f"{BASE}/order-service/rest/secure/angelbroking/order/v1/getLtpData"
ORD_URL = f"{BASE}/rest/secure/angelbroking/order/v1/placeOrder"
SCRIP_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"

_sess = {"jwt": None, "date": None}
_auto_trade = os.environ.get("ANGEL_AUTO_TRADE", "0") == "1"
_scrip = {"date": None, "rows": []}

def _totp(sec):
    s = sec.replace(" ", "").upper()
    s += "=" * ((8 - len(s) % 8) % 8)
    k = base64.b32decode(s)
    m = struct.pack(">Q", int(time.time() // 30))
    h = hmac.new(k, m, hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o+4])[0] & 0x7FFFFFFF) % 1000000:06d}"

def _cfg():
    px = os.environ.get("STATIC_PROXY_URL", "").strip()
    return (
        os.environ.get("ANGEL_API_KEY", "").strip(),
        os.environ.get("ANGEL_CLIENT_CODE", "").strip(),
        os.environ.get("ANGEL_PIN", "").strip(),
        os.environ.get("ANGEL_TOTP_SECRET", "").strip(),
        {"http": px, "https": px} if px else None,
    )

def _hdr(ak, jwt=None):
    h = {
        "Content-Type": "application/json", "Accept": "application/json",
        "X-UserType": "USER", "X-SourceID": "WEB",
        "X-ClientLocalIP": "127.0.0.1", "X-ClientPublicIP": "185.155.223.42",
        "X-MACAddress": "00:00:00:00:00:00", "X-PrivateKey": ak,
    }
    if jwt: h["Authorization"] = f"Bearer {jwt}"
    return h

def ensure_login(force=False):
    ak, cc, pin, totp_sec, px = _cfg()
    if not all([ak, cc, pin, totp_sec, px]): return None, "Env vars missing"
    today = datetime.now(IST).date()
    if not force and _sess["jwt"] and _sess["date"] == today:
        return _sess["jwt"], None
    try:
        r = requests.post(LOGIN_URL, headers=_hdr(ak), json={"clientcode": cc, "password": pin, "totp": _totp(totp_sec), "state": "live"}, proxies=px, timeout=15).json()
        if not r.get("status"): return None, r.get("message", str(r))
        _sess["jwt"], _sess["date"] = r["data"]["jwtToken"], today
        return _sess["jwt"], None
    except Exception as e:
        return None, str(e)

def get_balance():
    ak, _, _, _, px = _cfg()
    jwt, err = ensure_login()
    if not jwt: return None
    try:
        r = requests.get(RMS_URL, headers=_hdr(ak, jwt), proxies=px, timeout=15).json()
        if not r.get("status"):
            jwt, _ = ensure_login(force=True)
            if not jwt: return None
            r = requests.get(RMS_URL, headers=_hdr(ak, jwt), proxies=px, timeout=15).json()
        d = r.get("data", {})
        return float(d.get("availablecash") or d.get("net") or 0)
    except Exception: return None

def test_angel_login():
    _, err = ensure_login(force=True)
    if err: return f"Angel Err: {err}"
    bal = get_balance()
    mode = "AUTO-ORDER ON" if _auto_trade else "PAPER MODE"
    return f"Angel One: CONNECTED ({mode})\nReal Balance: ₹{bal:,.2f}" if bal is not None else "Angel One: CONNECTED"

def _load_scrips():
    today = datetime.now(IST).date()
    if _scrip["date"] == today and _scrip["rows"]: return _scrip["rows"]
    raw = requests.get(SCRIP_URL, timeout=25).json()
    _scrip["rows"] = [x for x in raw if x.get("exch_seg") == "NFO" and x.get("instrumenttype") == "OPTIDX" and x.get("name") in ("NIFTY", "BANKNIFTY", "FINNIFTY")]
    _scrip["date"] = today
    return _scrip["rows"]

def find_option(idx_name, strike, opt_type):
    nm = "NIFTY" if "NIFTY 50" in idx_name else idx_name
    today = datetime.now(IST).date()
    cands = []
    for x in _load_scrips():
        if x.get("name") != nm or not x.get("symbol", "").endswith(opt_type): continue
        try:
            if round(float(x["strike"]) / 100) != strike: continue
            exp = datetime.strptime(x["expiry"], "%d%b%Y").date()
            if exp >= today: cands.append((exp, x["symbol"], x["token"], int(x["lotsize"])))
        except Exception: continue
    if not cands: return None, None, None
    cands.sort(key=lambda z: z[0])
    _, sym, tok, lot = cands[0]
    return sym, tok, lot

def get_ltp(sym, tok):
    ak, _, _, _, px = _cfg()
    jwt, _ = ensure_login()
    if not jwt: return None
    try:
        r = requests.post(LTP_URL, headers=_hdr(ak, jwt), json={"exchange": "NFO", "tradingsymbol": sym, "symboltoken": str(tok)}, proxies=px, timeout=10).json()
        return float(r["data"]["ltp"]) if r.get("status") else None
    except Exception: return None

def place_order(sym, tok, qty, side):
    if not _auto_trade:
        return False, "PAPER MODE (ANGEL_AUTO_TRADE=0)"
    ak, _, _, _, px = _cfg()
    jwt, err = ensure_login()
    if not jwt: return False, f"Login fail: {err}"
    ltp = get_ltp(sym, tok)
    if not ltp: return False, "LTP fetch failed"
    px_lim = round((ltp * 1.03 if side == "BUY" else max(0.05, ltp * 0.97)) * 20) / 20
    payload = {
        "variety": "NORMAL", "tradingsymbol": sym, "symboltoken": str(tok),
        "transactiontype": side, "exchange": "NFO", "ordertype": "LIMIT",
        "producttype": "INTRADAY", "duration": "DAY", "price": f"{px_lim:.2f}",
        "squareoff": "0", "stoploss": "0", "quantity": str(qty),
    }
    try:
        r = requests.post(ORD_URL, headers=_hdr(ak, jwt), json=payload, proxies=px, timeout=15).json()
        if r.get("status"): return True, r["data"]["orderid"]
        return False, r.get("message", str(r))
    except Exception as e:
        return False, str(e)

def find_option_by_price(idx_name, atm, step, opt_type, min_p, max_p):
    nm = "NIFTY" if "NIFTY 50" in idx_name else idx_name
    today = datetime.now(IST).date()
    rows = _load_scrips()
    exps = sorted({datetime.strptime(x["expiry"], "%d%b%Y").date() for x in rows if x.get("name") == nm})
    exps = [e for e in exps if e >= today]
    if not exps: return None, None, None, None
    exp_str = exps[0].strftime("%d%b%Y").upper()
    by_str = {}
    for x in rows:
        if x.get("name") == nm and x.get("expiry", "").upper() == exp_str and x.get("symbol", "").endswith(opt_type):
            try: by_str[round(float(x["strike"]) / 100)] = (x["symbol"], x["token"], int(x["lotsize"]))
            except Exception: pass
    mid, best = (min_p + max_p) / 2.0, None
    for k in range(0, 15):
        st = atm + k * step if opt_type == "CE" else atm - k * step
        if st not in by_str: continue
        sym, tok, lot = by_str[st]
        ltp = get_ltp(sym, tok)
        if not ltp: continue
        if min_p <= ltp <= max_p: return sym, tok, lot, ltp
        diff = abs(ltp - mid)
        if best is None or diff < best[0]: best = (diff, sym, tok, lot, ltp)
        if ltp < min_p * 0.7: break
    return (best[1], best[2], best[3], best[4]) if best else (None, None, None, None)

CANDLE_URL = f"{BASE}/rest/secure/angelbroking/historical/v1/getCandleData"
IDX_TOKS = {"BANKNIFTY": "99926009", "FINNIFTY": "99926037", "NIFTY 50": "99926000"}

def get_5m_candles(idx_name):
    tok = IDX_TOKS.get(idx_name)
    if not tok: return None
    ak, _, _, _, px = _cfg()
    jwt, _ = ensure_login()
    if not jwt: return None
    now = datetime.now(IST)
    payload = {
        "exchange": "NSE", "symboltoken": tok, "interval": "FIVE_MINUTE",
        "fromdate": (now - timedelta(days=7)).strftime("%Y-%m-%d 09:15"),
        "todate": now.strftime("%Y-%m-%d %H:%M"),
    }
    try:
        r = requests.post(CANDLE_URL, headers=_hdr(ak, jwt), json=payload, proxies=px, timeout=12).json()
        rows = r.get("data") or []
        if len(rows) < 210: return None
        return [{"t": int(datetime.fromisoformat(x[0]).timestamp()), "h": float(x[2]), "l": float(x[3]), "c": float(x[4])} for x in rows]
    except Exception:
        return None

def fetch_1y_5m(idx_name):
    tok = IDX_TOKS.get(idx_name)
    if not tok: return []
    ak, _, _, _, px = _cfg()
    jwt, _ = ensure_login()
    if not jwt: return []
    end = datetime.now(IST)
    all_rows, seen = [], set()
    for k in range(12, 0, -1):
        f_dt = end - timedelta(days=k * 30)
        t_dt = end - timedelta(days=(k - 1) * 30)
        p = {"exchange": "NSE", "symboltoken": tok, "interval": "FIVE_MINUTE", "fromdate": f_dt.strftime("%Y-%m-%d 09:15"), "todate": t_dt.strftime("%Y-%m-%d 15:30")}
        try:
            r = requests.post(CANDLE_URL, headers=_hdr(ak, jwt), json=p, proxies=px, timeout=15).json()
            for x in (r.get("data") or []):
                ts = int(datetime.fromisoformat(x[0]).timestamp())
                if ts not in seen:
                    seen.add(ts)
                    all_rows.append((datetime.fromtimestamp(ts, IST), float(x[2]), float(x[3]), float(x[4])))
        except Exception: pass
        time.sleep(0.4)
    all_rows.sort(key=lambda z: z[0])
    out, e9, e21, e200 = [], None, None, None
    for dt, h, l, c in all_rows:
        e9 = c if e9 is None else c * 0.2 + e9 * 0.8
        e21 = c if e21 is None else c * (2/22) + e21 * (20/22)
        e200 = c if e200 is None else c * (2/201) + e200 * (199/201)
        out.append((dt, h, l, c, e9, e21, e200))
    return out

def run_1y_backtest():
    idxs = [("BANKNIFTY", 30, 8250), ("FINNIFTY", 60, 8250), ("NIFTY 50", 65, 8125)]
    lines, evs = ["<b>1-YEAR MONTHLY COMPOUNDING (₹15k Start):</b>"], []
    for name, lot, c1 in idxs:
        rows = fetch_1y_5m(name)
        if len(rows) < 250: continue
        done = set()
        for i in range(200, len(rows) - 1):
            dt, hi, lo, c, e9, e21, e200 = rows[i]
            day, t = dt.date(), dt.strftime("%H:%M")
            if dt.weekday() in (0, 3) or day in done or not (("09:20" <= t < "10:30") or ("13:30" <= t < "15:15")): continue
            p9, p21 = rows[i-1][4], rows[i-1][5]
            sig = "CE" if p9 <= p21 and e9 > e21 and c > e200 else ("PE" if p9 >= p21 and e9 < e21 and c < e200 else None)
            if not sig: continue
            sl = min(x[2] for x in rows[i-4:i+1]) if sig == "CE" else max(x[1] for x in rows[i-4:i+1])
            risk = (c - sl) if sig == "CE" else (sl - c)
            if risk <= 0: continue
            sl_r, res_r, end_j = -1.0, 0.0, i
            for j in range(i + 1, len(rows)):
                if rows[j][0].date() != day: break
                end_j = j
                dtj, hj, lj, cj = rows[j][:4]
                lo_r = ((lj - c) if sig == "CE" else (c - hj)) / risk
                hi_r = ((hj - c) if sig == "CE" else (c - lj)) / risk
                cl_r = ((cj - c) if sig == "CE" else (c - cj)) / risk
                if lo_r <= sl_r: res_r = sl_r; break
                if hi_r >= 1.0: sl_r = max(sl_r, float(int(hi_r) - 1))
                if dtj.strftime("%H:%M") >= "15:20": res_r = cl_r; break
            else:
                cj = rows[end_j][3]
                res_r = ((cj - c) if sig == "CE" else (c - cj)) / risk
            pnl1 = (res_r * risk * 0.35 * lot) - ((end_j - i) * 0.15 * lot)
            done.add(day); evs.append((dt, name, c1, pnl1))

    by_mon = {}
    for dt, name, c1, pnl1 in sorted(evs):
        by_mon.setdefault(dt.strftime("%Y-%m"), []).append((dt, name, c1, pnl1))

    cap, added, tot_1l = 15000.0, 0.0, 0.0
    for ym in sorted(by_mon):
        lots = max(1, int(cap // 16000))
        m_1l, m_cp, m_add = 0.0, 0.0, 0.0
        for dt, name, c1, pnl1 in by_mon[ym]:
            m_1l += (pnl1 - 55.0)
            net = (pnl1 * lots) - (55.0 + 10.0 * (lots - 1))
            cap += net; m_cp += net
            if cap < 15000.0:
                top = 15000.0 - cap
                cap += top; added += top; m_add += top
        tot_1l += m_1l
        add_s = f" | +Add ₹{m_add:,.0f}" if m_add > 0 else ""
        lines.append(f"{ym} ({lots}L) | 1L: ₹{m_1l:+,.0f} | Cp: ₹{m_cp:+,.0f}{add_s} | Bal ₹{cap:,.0f}")

    inv = 15000.0 + added
    lines.append(f"\n<b>1-Lot Fixed Total:</b> ₹{tot_1l:+,.0f}")
    lines.append(f"<b>Total Invested:</b> ₹15,000 + ₹{added:,.0f} = ₹{inv:,.0f}")
    lines.append(f"<b>Final Balance:</b> ₹{cap:,.0f}")
    lines.append(f"<b>TRUE NET PROFIT: ₹{cap - inv:+,.0f}</b>")
    return "\n".join(lines)
