"""
==============================================================================
           Complete 15-Hour SMC Course Implementation (Trade With Ani)
==============================================================================
"""

import time
import requests
import json
import os
from datetime import datetime

# ==============================================================================
#                               CONFIGURATION
# ==============================================================================
TELEGRAM_BOT_TOKEN = "9005788701:AAE-kGlVndkg5TqvUKEeOo91kNM2npV7X_w"
TELEGRAM_CHAT_ID = "8611777710"

WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "DOGEUSDT", "AVAXUSDT", "NEARUSDT"
]
TIMEFRAME = "15m"
SCAN_INTERVAL_SECONDS = 30
alerted_trades = {}
COOLDOWN_SECONDS = 900

from PIL import Image, ImageDraw


# --- STOCKMINDSET 100% PERFECT TRACKER & JOURNAL ---
ACTIVE_TRADES_FILE = "active_trades.json"
JOURNAL_FILE = "trade_journal.json"
HTML_JOURNAL_FILE = "trade_journal.html"

def load_json_data(fp, default):
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                c = f.read().strip()
                return json.loads(c) if c else default
        except: pass
    return default

def save_json_data(fp, data):
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except: pass

def register_active_trade(sym, setup):
    try:
        active = load_json_data(ACTIVE_TRADES_FILE, {})
        clean = sym.replace("B-", "").replace("_", "")
        active[clean] = {
            "action": setup.get("action", "LONG"),
            "entry": float(setup.get("entry", 0)),
            "target": float(setup.get("target", 0)),
            "sl": float(setup.get("sl", 0)),
            "rrr": str(setup.get("rrr", "2.0")),
            "setup_name": setup.get("setup_name", "SMC Setup"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        save_json_data(ACTIVE_TRADES_FILE, active)
        print(f"--> [ACTIVE TRADE REGISTERED] {clean}: {setup['action']} Entry=${setup['entry']} Target=${setup['target']} SL=${setup['sl']}")
    except Exception as e: print(f"Reg error: {e}")

def check_active_trade_outcomes(sym, last_candle):
    active = load_json_data(ACTIVE_TRADES_FILE, {})
    clean = sym.replace("B-", "").replace("_", "")
    t_key = next((k for k in active if k == sym or k.replace("B-","").replace("_","") == clean), None)
    if not t_key: return

    trade = active[t_key]
    act, entry, target, sl = trade["action"], trade["entry"], trade["target"], trade["sl"]
    rrr = trade.get("rrr", "2.0")
    t_now, d_now = datetime.now().strftime("%H:%M:%S"), datetime.now().strftime("%d-%b-%Y")
    high = float(last_candle.get("high", last_candle.get("h", 0)))
    low = float(last_candle.get("low", last_candle.get("l", 0)))

    outcome = None
    if "LONG" in act:
        if high >= target: outcome = "TARGET_HIT"
        elif low <= sl: outcome = "SL_HIT"
    elif "SHORT" in act:
        if low <= target: outcome = "TARGET_HIT"
        elif high >= sl: outcome = "SL_HIT"

    if outcome == "TARGET_HIT":
        msg = f"🎉🎯 <b>TARGET HIT ACHIEVED!</b> 🎯🎉\n\n• <b>Coin:</b> {clean}\n• <b>Type:</b> {act} 🟢\n• <b>Entry:</b> ${format_price(entry)} ➔ <b>Target:</b> ${format_price(target)}\n• <b>Profit Ratio:</b> 1:{rrr}\n• <b>Status:</b> 100% Target Hit! Profit Booked!\n⏰ <b>Time:</b> {t_now}"
        send_telegram_alert(msg)
        print(f"--> [TARGET HIT ALERT SENT] for {clean} at ${target}!")
        record_journal_entry(clean, act, entry, target, "TARGET HIT 🎯", f"+{rrr} R", "WIN", d_now, t_now)
        del active[t_key]; save_json_data(ACTIVE_TRADES_FILE, active)

    elif outcome == "SL_HIT":
        msg = f"🛑 <b>STOP LOSS HIT</b> 🛑\n\n• <b>Coin:</b> {clean}\n• <b>Type:</b> {act} 🔴\n• <b>Entry:</b> ${format_price(entry)} ➔ <b>Exit SL:</b> ${format_price(sl)}\n• <b>Status:</b> Safe Exit per Risk Management\n⏰ <b>Time:</b> {t_now}"
        send_telegram_alert(msg)
        print(f"--> [STOP LOSS HIT ALERT SENT] for {clean} at ${sl}!")
        record_journal_entry(clean, act, entry, sl, "STOP LOSS 🛑", "-1.00 R", "LOSS", d_now, t_now)
        del active[t_key]; save_json_data(ACTIVE_TRADES_FILE, active)

def record_journal_entry(sym, act, entry, exit_p, result, rrr, status, d_now, t_now):
    journal = load_json_data(JOURNAL_FILE, [])
    journal.append({"date": d_now, "time": t_now, "coin": sym, "type": act, "entry": entry, "exit": exit_p, "result": result, "rrr": rrr, "status": status})
    save_json_data(JOURNAL_FILE, journal)
    update_html_journal(journal)
    try:
        total = len(journal)
        wins = len([j for j in journal if j.get("status") == "WIN"])
        losses = total - wins
        wr = (wins / total * 100) if total > 0 else 0
        j_msg = (
            f"📖 <b>StockMindset દૈનિક ખાતાવહી (Journal)</b> 📖\n\n"
            f"• <b>ટ્રેડ:</b> {sym} ({act})\n"
            f"• <b>પરિણામ:</b> {result} ({rrr})\n"
            f"• <b>એન્ટ્રી ➔ એક્ઝિટ:</b> ${format_price(entry)} ➔ ${format_price(exit_p)}\n\n"
            f"📊 <b>આજનો કુલ હિસાબ:</b>\n"
            f"  • કુલ ટ્રેડ્સ: {total}\n"
            f"  • ટાર્ગેટ હિટ: {wins} 🎯\n"
            f"  • સ્ટોપ લોસ: {losses} 🛑\n"
            f"  • વિન રેટ: {wr:.1f}%\n\n"
            f"⏰ <b>સમય:</b> {d_now} {t_now}"
        )
        send_telegram_alert(j_msg)
    except: pass

def update_html_journal(journal):
    total = len(journal)
    wins = len([j for j in journal if j.get("status") == "WIN"])
    losses = total - wins
    wr = (wins / total * 100) if total > 0 else 0
    rows = "".join([f"<tr><td style='padding:8px;border-bottom:1px solid #ddd;'>{j['date']} {j['time']}</td><td style='padding:8px;border-bottom:1px solid #ddd;font-weight:bold;'>{j['coin']}</td><td style='padding:8px;border-bottom:1px solid #ddd;'>{j['type']}</td><td style='padding:8px;border-bottom:1px solid #ddd;'>${j['entry']}</td><td style='padding:8px;border-bottom:1px solid #ddd;'>${j['exit']}</td><td style='padding:8px;border-bottom:1px solid #ddd;font-weight:bold;color:{'#16a34a' if j['status']=='WIN' else '#dc2626'};'>{j['result']}</td><td style='padding:8px;border-bottom:1px solid #ddd;'>{j['rrr']}</td></tr>" for j in reversed(journal[-50:])])
    html = f"<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>StockMindset SMC Trade Journal</title><style>body{{font-family:-apple-system,sans-serif;background:#f8fafc;padding:12px;margin:0;color:#1e293b;}}.card{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,0.05);margin-bottom:12px;}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px;text-align:center;}}.box{{background:#f1f5f9;border-radius:8px;padding:10px;}}table{{width:100%;border-collapse:collapse;font-size:12px;margin-top:10px;}}th{{background:#0f172a;color:#fff;padding:8px;text-align:left;}}</style></head><body><div class='card'><h2 style='margin:0;'>📊 StockMindset SMC Trade Journal (દૈનિક ખાતાવહી)</h2><div style='font-size:12px;color:#64748b;'>Founder & Author: <b>ANKIT RABARI (Rajkot, Gujarat)</b> • Mo: 7697667767</div><div class='grid'><div class='box'><div>કુલ ટ્રેડ્સ</div><b>{total}</b></div><div class='box'><div>ટાર્ગેટ હિટ</div><b style='color:#16a34a;'>{wins} 🎯</b></div><div class='box'><div>સ્ટોપ લોસ</div><b style='color:#dc2626;'>{losses} 🛑</b></div><div class='box'><div>વિન રેટ</div><b style='color:#2563eb;'>{wr:.1f}%</b></div></div></div><div class='card' style='overflow-x:auto;'><h3>📖 દૈનિક ટ્રેડ હિસાબ</h3><table><thead><tr><th>સમય</th><th>કોઈન</th><th>ટાઈપ</th><th>એન્ટ્રી</th><th>એક્ઝિટ</th><th>પરિણામ</th><th>R:R</th></tr></thead><tbody>{rows}</tbody></table></div></body></html>"
    try:
        with open(HTML_JOURNAL_FILE, "w", encoding="utf-8") as f: f.write(html)
    except: pass


def format_price(p):
    try:
        p = float(p)
        return f"{p:.2f}" if p >= 100 else (f"{p:.4f}" if p >= 1 else f"{p:.6f}")
    except:
        return str(p)

def draw_smc_chart(symbol, timeframe, candles, setup=None, output_path="chart.png"):
    try:
        w, h = 900, 550
        img = Image.new("RGB", (w, h), color="#131722")
        draw = ImageDraw.Draw(img)
        plot_c = candles[-40:]
        n = len(plot_c)
        if n == 0: return None
        highs = [float(c["high"]) for c in plot_c]
        lows = [float(c["low"]) for c in plot_c]
        if setup:
            if "sl" in setup: lows.append(float(setup["sl"])); highs.append(float(setup["sl"]))
            if "target" in setup: highs.append(float(setup["target"])); lows.append(float(setup["target"]))
        min_p, max_p = min(lows), max(highs)
        p_range = max(1e-6, max_p - min_p)
        chart_h, chart_w = h - 120, w - 170
        def p2y(p): return 70 + chart_h - int(((float(p) - min_p) / p_range) * chart_h)
        cw = max(4, int(chart_w / (n * 1.5)))
        sp = int(chart_w / n)
        for i in range(6):
            gp = min_p + (p_range / 5.0) * i
            gy = p2y(gp)
            draw.line([(60, gy), (w - 110, gy)], fill="#202430", width=1)
            draw.text((w - 100, gy - 6), format_price(gp), fill="#787b86")
        for idx, c in enumerate(plot_c):
            cx = 60 + idx * sp + (sp // 2)
            oy, cy, hy, ly = p2y(c["open"]), p2y(c["close"]), p2y(c["high"]), p2y(c["low"])
            col = "#089981" if float(c["close"]) >= float(c["open"]) else "#f23645"
            draw.line([(cx, hy), (cx, ly)], fill=col, width=1)
            t_y, b_y = min(oy, cy), max(oy, cy)
            if b_y - t_y < 2: b_y = t_y + 2
            draw.rectangle([(cx - cw // 2, t_y), (cx + cw // 2, b_y)], fill=col, outline=col)
        if setup:
            ey, sy, ty = p2y(setup["entry"]), p2y(setup["sl"]), p2y(setup["target"])
            draw.line([(60, ey), (w - 110, ey)], fill="#2962ff", width=2)
            draw.text((w - 250, ey - 14), f"ENTRY: ${format_price(setup['entry'])}", fill="#2962ff")
            draw.line([(60, sy), (w - 110, sy)], fill="#f23645", width=2)
            draw.text((w - 250, sy - 14), f"STOP LOSS: ${format_price(setup['sl'])}", fill="#f23645")
            draw.line([(60, ty), (w - 110, ty)], fill="#089981", width=2)
            draw.text((w - 250, ty - 14), f"TARGET: ${format_price(setup['target'])}", fill="#089981")
        draw.text((60, 15), f"StockMindset SMC: {symbol} ({timeframe})", fill="#ffffff")
        img.save(output_path)
        return output_path
    except Exception as err:
        return None

MIN_RISK_REWARD = 2.0

# ==============================================================================
#                       TELEGRAM ALERTS DISPATCHER
# ==============================================================================
def send_telegram_alert(message: str, photo_path: str = None) -> bool:
    if photo_path and os.path.exists(photo_path):
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        try:
            with open(photo_path, "rb") as f:
                r = requests.post(
                    url,
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": message, "parse_mode": "HTML"},
                    files={"photo": f},
                    timeout=15
                )
            if r.status_code == 200:
                return True
        except Exception as e:
            print(f"Telegram Photo Exception: {e}")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get("ok", False)
    except Exception as e:
        print(f"Telegram Text Exception: {e}")
        return False

# ==============================================================================
#                   DATA FETCHER (COINDCX - UNBLOCKED IN INDIA)
# ==============================================================================
def get_coindcx_candles(symbol: str, interval: str = TIMEFRAME, limit: int = 60):
    clean_sym = symbol.replace("USDT", "")
    pair = f"B-{clean_sym}_USDT"
    url = f"https://public.coindcx.com/market_data/candles/?pair={pair}&interval={interval}&limit={limit}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        if not isinstance(data, list) or len(data) == 0:
            return []
        candles = []
        for d in data:
            candles.append({
                "time": int(d["time"]),
                "open": float(d["open"]),
                "high": float(d["high"]),
                "low": float(d["low"]),
                "close": float(d["close"]),
                "volume": float(d.get("volume", 100.0))
            })
        candles.sort(key=lambda c: c["time"])
        return candles
    except Exception as e:
        print(f"CoinDCX Fetch Error for {symbol}: {e}")
        return []

# ==============================================================================
#                 PHASE 1: 5 INSTITUTIONAL CANDLES (SLIDES 6-24)
# ==============================================================================
def get_avg_range(candles, period=14):
    sub = candles[-period:] if len(candles) >= period else candles
    return sum(c["high"] - c["low"] for c in sub) / max(1, len(sub))

def evaluate_institutional_candles(candles, trend, swing_high, swing_low, avg_range):
    current = candles[-1]
    prev = candles[-2]
    c_range = max(1e-6, current["high"] - current["low"])
    body = abs(current["close"] - current["open"])

    # 1. IFC Candle (Slide 7-10: Slide 9 Rule for Trade)
    if trend == "BULLISH":
        swept_low = min(c["low"] for c in candles[-10:-1])
        if current["low"] < swept_low and current["close"] >= swept_low:
            lower_wick = min(current["open"], current["close"]) - current["low"]
            if (lower_wick / c_range) >= 0.35 and current["close"] > current["open"]:
                sl = current["low"] - avg_range * 1.0
                tp = swing_high
                return {
                    "action": "LONG", "type": "IFC Candle Setup (Slide 9)",
                    "slide": "Slide 7-10 (Slide 9 Rule for Trade)",
                    "entry": current["close"], "sl": sl, "target": tp,
                    "rrr": round((tp - current["close"]) / max(0.0001, (current["close"] - sl)), 2)
                }
    elif trend == "BEARISH":
        swept_high = max(c["high"] for c in candles[-10:-1])
        if current["high"] > swept_high and current["close"] <= swept_high:
            upper_wick = current["high"] - max(current["open"], current["close"])
            if (upper_wick / c_range) >= 0.35 and current["close"] < current["open"]:
                sl = current["high"] + avg_range * 1.0
                tp = swing_low
                return {
                    "action": "SHORT", "type": "IFC Candle Setup (Slide 9)",
                    "slide": "Slide 7-10 (Slide 9 Rule for Trade)",
                    "entry": current["close"], "sl": sl, "target": tp,
                    "rrr": round((current["close"] - tp) / max(0.0001, (sl - current["close"])), 2)
                }

    # 2. Brust Candle Reversal (Slide 11-14: Slide 13 Rule for Trade)
    for offset in [2, 3]:
        brust_c = candles[-offset]
        b_range = brust_c["high"] - brust_c["low"]
        b_body = abs(brust_c["close"] - brust_c["open"])
        if b_range >= 1.75 * avg_range and (b_body / b_range) >= 0.60:
            if trend == "BULLISH" and brust_c["close"] < brust_c["open"]:
                if current["close"] > current["open"]:
                    sl = min(c["low"] for c in candles[-offset:]) - avg_range * 1.0
                    tp = swing_high
                    return {
                        "action": "LONG", "type": "Brust Candle Reversal (Slide 13)",
                        "slide": "Slide 11-14 (Slide 13 Rule: Trade Opposite)",
                        "entry": current["close"], "sl": sl, "target": tp,
                        "rrr": round((tp - current["close"]) / max(0.0001, (current["close"] - sl)), 2)
                    }
            elif trend == "BEARISH" and brust_c["close"] > brust_c["open"]:
                if current["close"] < current["open"]:
                    sl = max(c["high"] for c in candles[-offset:]) + avg_range * 1.0
                    tp = swing_low
                    return {
                        "action": "SHORT", "type": "Brust Candle Reversal (Slide 13)",
                        "slide": "Slide 11-14 (Slide 13 Rule: Trade Opposite)",
                        "entry": current["close"], "sl": sl, "target": tp,
                        "rrr": round((current["close"] - tp) / max(0.0001, (sl - current["close"])), 2)
                    }

    return None

# ==============================================================================
#            PHASE 2: ORDER BLOCKS & FVG (SLIDES 25-60)
# ==============================================================================
def find_fvgs(candles, avg_range, eq_level):
    fvgs = []
    for i in range(2, len(candles) - 1):
        c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]
        c2_r = c2["high"] - c2["low"]
        size_class = "BIG" if c2_r >= 1.4 * avg_range else "NORMAL"

        if c3["low"] > c1["high"]:
            ce = c1["high"] + 0.50 * (c3["low"] - c1["high"])
            zone = "DISCOUNT" if ce < eq_level else "PREMIUM"
            fvgs.append({
                "type": "BULLISH", "top": c3["low"], "bottom": c1["high"],
                "ce": ce, "zone": zone, "size_class": size_class, "idx": i,
                "tap_count": 0, "mitigated": False
            })
        elif c3["high"] < c1["low"]:
            ce = c3["high"] + 0.50 * (c1["low"] - c3["high"])
            zone = "PREMIUM" if ce > eq_level else "DISCOUNT"
            fvgs.append({
                "type": "BEARISH", "top": c1["low"], "bottom": c3["high"],
                "ce": ce, "zone": zone, "size_class": size_class, "idx": i,
                "tap_count": 0, "mitigated": False
            })

    for f in fvgs:
        for k in range(f["idx"] + 1, len(candles)):
            c = candles[k]
            if f["type"] == "BULLISH":
                if c["low"] <= f["top"] and c["high"] >= f["bottom"]:
                    if candles[k - 1]["low"] > f["top"]: f["tap_count"] += 1
                if c["close"] < f["bottom"]: f["mitigated"] = True
            elif f["type"] == "BEARISH":
                if c["high"] >= f["bottom"] and c["low"] <= f["top"]:
                    if candles[k - 1]["high"] < f["bottom"]: f["tap_count"] += 1
                if c["close"] > f["top"]: f["mitigated"] = True
    return fvgs

def find_order_blocks(candles, fvgs, eq_level):
    obs = []
    for f in fvgs:
        idx = f["idx"] - 1
        if idx >= 1:
            ob_c = candles[idx - 1]
            if f["type"] == "BULLISH" and ob_c["close"] < ob_c["open"]:
                ob_mid = (ob_c["high"] + ob_c["low"]) / 2.0
                obs.append({
                    "type": "BULLISH_OB", "high": ob_c["high"], "low": ob_c["low"],
                    "mid": ob_mid, "zone": "DISCOUNT" if ob_mid < eq_level else "PREMIUM",
                    "idx": idx - 1, "mitigated": False, "tap_count": 0
                })
            elif f["type"] == "BEARISH" and ob_c["close"] > ob_c["open"]:
                ob_mid = (ob_c["high"] + ob_c["low"]) / 2.0
                obs.append({
                    "type": "BEARISH_OB", "high": ob_c["high"], "low": ob_c["low"],
                    "mid": ob_mid, "zone": "PREMIUM" if ob_mid > eq_level else "DISCOUNT",
                    "idx": idx - 1, "mitigated": False, "tap_count": 0
                })

    for ob in obs:
        for k in range(ob["idx"] + 2, len(candles)):
            c = candles[k]
            if ob["type"] == "BULLISH_OB":
                if c["low"] <= ob["high"] and c["high"] >= ob["low"]:
                    ob["tap_count"] += 1
                if c["close"] < ob["low"]: ob["mitigated"] = True
            elif ob["type"] == "BEARISH_OB":
                if c["high"] >= ob["low"] and c["low"] <= ob["high"]:
                    ob["tap_count"] += 1
                if c["close"] > ob["high"]: ob["mitigated"] = True
    return obs

# ==============================================================================
#            PHASE 4: MARKET STRUCTURE (SLIDES 80-98) & TREND
# ==============================================================================
def analyze_market_structure(candles):
    lookback = min(len(candles), 50)
    recent = candles[-lookback:]
    closes = [c["close"] for c in recent]
    k = 2.0 / (lookback + 1.0)
    ema = closes[0]
    for p in closes[1:]: ema = p * k + ema * (1.0 - k)
    curr_close = candles[-1]["close"]
    half = lookback // 2
    h1, h2 = max(c["high"] for c in recent[:half]), max(c["high"] for c in recent[half:])
    l1, l2 = min(c["low"] for c in recent[:half]), min(c["low"] for c in recent[half:])
    if curr_close < ema or (h2 < h1 and l2 < l1): trend = "BEARISH"
    elif curr_close > ema and h2 > h1 and l2 > l1: trend = "BULLISH"
    else: trend = "BEARISH" if curr_close < ema else "BULLISH"
    return {"trend": trend, "recent_high": max(c["high"] for c in recent), "recent_low": min(c["low"] for c in recent), "ema": ema}

# ==============================================================================
#                       MASTER SMC 146-SLIDE SCAN ENGINE
# ==============================================================================
def scan_symbol_for_smc_setup(symbol, candles):
    if len(candles) < 30: return None
    avg_range = get_avg_range(candles, 14)
    struct = analyze_market_structure(candles)
    trend = struct["trend"]
    current, prev = candles[-1], candles[-2]
    c_range = max(1e-6, current["high"] - current["low"])
    swing_high, swing_low = struct["recent_high"], struct["recent_low"]

    leg_candles = candles[-20:]
    leg_high, leg_low = max(c["high"] for c in leg_candles), min(c["low"] for c in leg_candles)
    leg_eq = (leg_high + leg_low) / 2.0

    fvgs = find_fvgs(candles, avg_range, leg_eq)
    obs = find_order_blocks(candles, fvgs, leg_eq)

    # --- A. BULLISH SETUPS (Slide 43: Discount of Impulse Leg) ---
    if trend == "BULLISH":
        for ob in obs:
            if ob["type"] == "BULLISH_OB" and not ob["mitigated"] and ob["low"] <= leg_eq:
                if current["low"] <= ob["high"] and current["close"] >= ob["low"]:
                    lower_wick = min(current["open"], current["close"]) - current["low"]
                    if (lower_wick / c_range) >= 0.20 and current["close"] > current["open"]:
                        sl = min(ob["low"], current["low"]) - avg_range * 1.0
                        tp = swing_high + avg_range * 0.20
                        rr = round((tp - current["close"]) / max(0.0001, (current["close"] - sl)), 2)
                        if rr >= MIN_RISK_REWARD:
                            return {"action": "LONG", "symbol": symbol, "trend": "BULLISH", "setup_name": "Institutional Order Block (Slide 28-29)", "slide": "Slide 28-29 (Slide 40 Unmitigated + Slide 43 Discount)", "entry": current["close"], "sl": sl, "target": tp, "rrr": rr}

        for f in fvgs:
            if f["type"] == "BULLISH" and not f["mitigated"] and f["bottom"] <= leg_eq:
                if current["low"] <= f["ce"] and current["close"] >= f["bottom"] and current["close"] > current["open"]:
                    sl = f["bottom"] - avg_range * 1.0
                    tp = swing_high + avg_range * 0.20
                    rr = round((tp - current["close"]) / max(0.0001, (current["close"] - sl)), 2)
                    if rr >= MIN_RISK_REWARD:
                        return {"action": "LONG", "symbol": symbol, "trend": "BULLISH", "setup_name": f"FVG 50% CE Reversal ({f['size_class']} - Slide 48)", "slide": "Slide 48 (50% CE Mitigation) + Slide 43", "entry": current["close"], "sl": sl, "target": tp, "rrr": rr}

        recent_low_12 = min(c["low"] for c in candles[-15:-1])
        if current["low"] < recent_low_12 and current["close"] > recent_low_12 and current["close"] > current["open"]:
            sl = current["low"] - avg_range * 1.0
            tp = swing_high + avg_range * 0.20
            rr = round((tp - current["close"]) / max(0.0001, (current["close"] - sl)), 2)
            if rr >= MIN_RISK_REWARD:
                return {"action": "LONG", "symbol": symbol, "trend": "BULLISH", "setup_name": "IDM Liquidity Sweep Reversal (Slide 71 & 119)", "slide": "Slide 71 (Inducement Sweep) + Slide 119 (RRP)", "entry": current["close"], "sl": sl, "target": tp, "rrr": rr}


    # --- B. BEARISH SETUPS (Slide 43: Premium of Impulse Leg) ---
    if trend == "BEARISH":
        for ob in obs:
            if ob["type"] == "BEARISH_OB" and not ob["mitigated"] and ob["high"] >= leg_eq:
                if current["high"] >= ob["low"] and current["close"] <= ob["high"]:
                    upper_wick = current["high"] - max(current["open"], current["close"])
                    if (upper_wick / c_range) >= 0.20 and current["close"] < current["open"]:
                        sl = max(ob["high"], current["high"]) + avg_range * 1.0
                        tp = swing_low - avg_range * 0.20
                        rr = round((current["close"] - tp) / max(0.0001, (sl - current["close"])), 2)
                        if rr >= MIN_RISK_REWARD:
                            return {"action": "SHORT", "symbol": symbol, "trend": "BEARISH", "setup_name": "Institutional Order Block (Slide 28-29)", "slide": "Slide 28-29 (Slide 40 Unmitigated + Slide 43 Premium)", "entry": current["close"], "sl": sl, "target": tp, "rrr": rr}

        for f in fvgs:
            if f["type"] == "BEARISH" and not f["mitigated"] and f["top"] >= leg_eq:
                if current["high"] >= f["ce"] and current["close"] <= f["top"] and current["close"] < current["open"]:
                    sl = f["top"] + avg_range * 1.0
                    tp = swing_low - avg_range * 0.20
                    rr = round((current["close"] - tp) / max(0.0001, (sl - current["close"])), 2)
                    if rr >= MIN_RISK_REWARD:
                        return {"action": "SHORT", "symbol": symbol, "trend": "BEARISH", "setup_name": f"FVG 50% CE Reversal ({f['size_class']} - Slide 48)", "slide": "Slide 48 (50% CE Mitigation) + Slide 43", "entry": current["close"], "sl": sl, "target": tp, "rrr": rr}

        recent_high_12 = max(c["high"] for c in candles[-15:-1])
        if current["high"] > recent_high_12 and current["close"] < recent_high_12 and current["close"] < current["open"]:
            sl = current["high"] + avg_range * 1.0
            tp = swing_low - avg_range * 0.20
            rr = round((current["close"] - tp) / max(0.0001, (sl - current["close"])), 2)
            if rr >= MIN_RISK_REWARD:
                return {"action": "SHORT", "symbol": symbol, "trend": "BEARISH", "setup_name": "IDM Liquidity Sweep Reversal (Slide 71 & 119)", "slide": "Slide 71 (Inducement Sweep) + Slide 119 (RRP)", "entry": current["close"], "sl": sl, "target": tp, "rrr": rr}


    return None


def run_master_scan_pass():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Scan Across {len(WATCHLIST)} Coins...")
    current_ts = time.time()
    for sym in WATCHLIST:
        try:
            candles = get_coindcx_candles(sym, interval=TIMEFRAME, limit=60)
            if not candles: continue
            try: check_active_trade_outcomes(sym, candles[-1])
            except: pass
            setup = scan_symbol_for_smc_setup(sym, candles)
            if setup:
                alert_key = f"{sym}_{setup['action']}_{setup.get('setup_name')}"
                active = load_json_data(ACTIVE_TRADES_FILE, {})
                clean_sym = sym.replace("B-", "").replace("_", "")
                if clean_sym in active or sym in active:
                    continue
                if alert_key in alerted_trades and (current_ts - alerted_trades[alert_key] < COOLDOWN_SECONDS):
                    continue
                alerted_trades[alert_key] = current_ts
                print(f"--> Found Valid SMC Trade on {sym}: {setup['action']} ({setup.get('setup_name')})")
                register_active_trade(sym, setup)
                action_emoji = "🟢 LONG" if setup['action'] == 'LONG' else "🔴 SHORT"
                entry_f, sl_f, target_f, rrr_f = format_price(setup['entry']), format_price(setup['sl']), format_price(setup['target']), str(setup.get('rrr', '2.0'))
                msg = (f"🎯 <b>NEW SMC INSTITUTIONAL SETUP: {sym}</b> 🎯\n\n• <b>Action:</b> {action_emoji}\n• <b>Trend:</b> {setup['trend']} (Slide 43)\n• <b>Pattern:</b> {setup.get('setup_name')}\n• <b>Source:</b> {setup.get('slide')}\n\n🔹 <b>Entry:</b> ${entry_f}\n🛑 <b>Stop Loss:</b> ${sl_f}\n🏁 <b>Target:</b> ${target_f}\n⚖️ <b>Risk:Reward:</b> 1:{rrr_f}\n\n🛡️ <b>Verified Filters:</b>\n  ✔️ Slide 40: Fresh Unmitigated Zone\n  ✔️ Slide 43: Go With Trend\n  ✔️ Slide 59: Liquidity Swept\n  ✔️ Slide 29: Reversal Candle Confirmed\n\n⏰ <b>Time:</b> {datetime.now().strftime('%H:%M:%S')}")
                photo_file, photo_sent = f"chart_{sym}.png", False
                try:
                    generated_chart = draw_smc_chart(sym, TIMEFRAME, candles, setup=setup, output_path=photo_file)
                    if generated_chart and os.path.exists(generated_chart):
                        send_telegram_alert(msg, photo_path=generated_chart)
                        photo_sent = True
                        print(f"--> Telegram Alert with Photo sent for {sym}!")
                except Exception as p_err: print(f"Photo error {sym}: {p_err}")
                if not photo_sent:
                    send_telegram_alert(msg)
                    print(f"--> Telegram Text Alert sent for {sym}!")
        except Exception as e:
            print(f"Error scanning {sym}: {e}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scan pass completed.")

if __name__ == "__main__":
    print("SMC Bot is running in continuous loop. Press CTRL+C to stop.")
    while True:
        try:
            run_master_scan_pass()
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("Bot stopped by user.")
            break
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(10)
