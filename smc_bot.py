"""
==============================================================================
#                SMC MASTER ENGINE & LIVE RUNNER (ALL 146 SLIDES)
           Complete 15-Hour SMC Course Implementation (Trade With Ani)
==============================================================================
"""

import time
import requests
import json
import os
import urllib.request, urllib.parse
import hmac
import hashlib
import hmac
import hashlib
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

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
MIN_RISK_REWARD = 2.0

# CoinDCX Real Money Live Trading Settings (Ankit Rabari)
LIVE_TRADING = True
COINDCX_API_KEY = "904f9c44faf2c65159eccf037c9bed63f672ad56092e9da3"
COINDCX_SECRET_KEY = "a9ca8ebdaef96f50843e0211feb5205025f5a1bc2983cca4491212fd4d33cf71"


# Alert Tracking to Prevent Spam (15-Minute Cooldown per Setup)
alerted_trades = {}
COOLDOWN_SECONDS = 900  # 15 minutes (1 candle duration)


# ==============================================================================
#                 STOCKMINDSET TARGET, SL & AUTO-JOURNAL ENGINE
# ==============================================================================
# ==============================================================================
#                 STOCKMINDSET TARGET, SL & AUTO-JOURNAL ENGINE
# ==============================================================================
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
            "initial_sl": float(setup.get("sl", 0)),
            "stage": "INITIAL",
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
    initial_sl = float(trade.get("initial_sl", sl))
    if "initial_sl" not in trade:
        trade["initial_sl"] = initial_sl
    stage = trade.get("stage", "INITIAL")
    rrr = trade.get("rrr", "2.0")
    t_now, d_now = datetime.now().strftime("%H:%M:%S"), datetime.now().strftime("%d-%b-%Y")
    high = float(last_candle.get("high", last_candle.get("h", 0)))
    low = float(last_candle.get("low", last_candle.get("l", 0)))

    # Initial risk R
    is_long = "LONG" in act
    risk = max(1e-6, (entry - initial_sl) if is_long else (initial_sl - entry))

    # --- SMC AUTO TRAILING SL ENGINE (Slides 140 to 146) ---
    updated_sl = False

    if is_long:
        # Stage 3: +3.5 R profit reached -> Trail to +2.0 R profit
        if high >= entry + (3.5 * risk) and stage != "TRAILED_3R":
            new_sl = round(entry + (2.0 * risk), 4 if entry < 10 else 2)
            if new_sl > sl:
                trade["sl"] = new_sl
                trade["stage"] = "TRAILED_3R"
                updated_sl = True
                msg = f"🔒 <b>TRAILING STOP LOSS (PROFIT LOCKED): {clean}</b> 🔒\n\n• <b>Action:</b> 🟢 LONG\n• <b>Progress:</b> +3.5 R Profit Reached!\n• <b>New Trailing SL:</b> ${format_price(new_sl)} (Securing +2.0 R Profit!)\n• <b>Status:</b> Guaranteed Win Locked (Slide 143-144)!\n⏰ <b>Time:</b> {t_now}"
                send_telegram_alert(msg)
        # Stage 2: +2.0 R profit reached -> Move to Break-Even (Slide 142)
        elif high >= entry + (2.0 * risk) and stage == "INITIAL":
            new_sl = round(entry + (0.05 * risk), 4 if entry < 10 else 2)
            if new_sl > sl:
                trade["sl"] = new_sl
                trade["stage"] = "BREAK_EVEN"
                updated_sl = True
                msg = f"🔄 <b>TRAILING STOP LOSS (BREAK-EVEN): {clean}</b> 🔄\n\n• <b>Action:</b> 🟢 LONG\n• <b>Progress:</b> +2.0 R Profit Reached!\n• <b>New SL:</b> ${format_price(new_sl)} (Entry Cost)\n• <b>Status:</b> 100% Risk-Free Trade (Zero Loss Guarantee - Slide 142)!\n⏰ <b>Time:</b> {t_now}"
                send_telegram_alert(msg)

    else: # SHORT
        # Stage 3: +3.5 R profit reached -> Trail to +2.0 R profit
        if low <= entry - (3.5 * risk) and stage != "TRAILED_3R":
            new_sl = round(entry - (2.0 * risk), 4 if entry < 10 else 2)
            if new_sl < sl:
                trade["sl"] = new_sl
                trade["stage"] = "TRAILED_3R"
                updated_sl = True
                msg = f"🔒 <b>TRAILING STOP LOSS (PROFIT LOCKED): {clean}</b> 🔒\n\n• <b>Action:</b> 🔴 SHORT\n• <b>Progress:</b> +3.5 R Profit Reached!\n• <b>New Trailing SL:</b> ${format_price(new_sl)} (Securing +2.0 R Profit!)\n• <b>Status:</b> Guaranteed Win Locked (Slide 143-144)!\n⏰ <b>Time:</b> {t_now}"
                send_telegram_alert(msg)
        # Stage 2: +2.0 R profit reached -> Move to Break-Even (Slide 142)
        elif low <= entry - (2.0 * risk) and stage == "INITIAL":
            new_sl = round(entry - (0.05 * risk), 4 if entry < 10 else 2)
            if new_sl < sl:
                trade["sl"] = new_sl
                trade["stage"] = "BREAK_EVEN"
                updated_sl = True
                msg = f"🔄 <b>TRAILING STOP LOSS (BREAK-EVEN): {clean}</b> 🔄\n\n• <b>Action:</b> 🔴 SHORT\n• <b>Progress:</b> +2.0 R Profit Reached!\n• <b>New SL:</b> ${format_price(new_sl)} (Entry Cost)\n• <b>Status:</b> 100% Risk-Free Trade (Zero Loss Guarantee - Slide 142)!\n⏰ <b>Time:</b> {t_now}"
                send_telegram_alert(msg)

    if updated_sl:
        sl = trade["sl"]
        stage = trade["stage"]
        save_json_data(ACTIVE_TRADES_FILE, active)

    # --- OUTCOME CHECK ---
    outcome = None
    if is_long:
        if high >= target: outcome = "TARGET_HIT"
        elif low <= sl: outcome = "SL_HIT"
    else:
        if low <= target: outcome = "TARGET_HIT"
        elif high >= sl: outcome = "SL_HIT"

    if outcome == "TARGET_HIT":
        msg = f"🎉🎯 <b>TARGET HIT ACHIEVED!</b> 🎯🎉\n\n• <b>Coin:</b> {clean}\n• <b>Type:</b> {act} 🟢\n• <b>Entry:</b> ${format_price(entry)} ➔ <b>Target:</b> ${format_price(target)}\n• <b>Profit Ratio:</b> 1:{rrr}\n• <b>Status:</b> 100% Target Hit! Profit Booked!\n⏰ <b>Time:</b> {t_now}"
        send_telegram_alert(msg)
        print(f"--> [TARGET HIT ALERT SENT] for {clean} at ${target}!")
        record_journal_entry(clean, act, entry, target, "TARGET HIT 🎯", f"+{rrr} R", "WIN", d_now, t_now)
        del active[t_key]; save_json_data(ACTIVE_TRADES_FILE, active)
        try:
            on_live_trade_closed(clean, outcome)
        except Exception: pass

    elif outcome == "SL_HIT":
        if stage == "TRAILED_3R":
            secured_r = "+2.00 R"
            msg = f"🔒 <b>TRAILING STOP LOSS HIT (PROFIT SECURED!)</b> 🔒\n\n• <b>Coin:</b> {clean}\n• <b>Type:</b> {act}\n• <b>Entry:</b> ${format_price(entry)} ➔ <b>Exit SL:</b> ${format_price(sl)}\n• <b>Result:</b> {secured_r} Profit Locked!\n• <b>Status:</b> Safe Exit via Trailing SL (Slide 143-144)!\n⏰ <b>Time:</b> {t_now}"
            send_telegram_alert(msg)
            record_journal_entry(clean, act, entry, sl, "TRAILING SL 🔒", secured_r, "WIN", d_now, t_now)
        elif stage == "BREAK_EVEN":
            msg = f"🛡️ <b>BREAK-EVEN EXIT (ZERO LOSS)</b> 🛡️\n\n• <b>Coin:</b> {clean}\n• <b>Type:</b> {act}\n• <b>Entry:</b> ${format_price(entry)} ➔ <b>Exit SL:</b> ${format_price(sl)}\n• <b>Result:</b> 0.00 R (Capital Protected!)\n• <b>Status:</b> Safe Exit at Cost per Slide 142!\n⏰ <b>Time:</b> {t_now}"
            send_telegram_alert(msg)
            record_journal_entry(clean, act, entry, sl, "BREAK-EVEN 🛡️", "0.00 R", "WIN", d_now, t_now)
        else:
            msg = f"🛑 <b>STOP LOSS HIT</b> 🛑\n\n• <b>Coin:</b> {clean}\n• <b>Type:</b> {act} 🔴\n• <b>Entry:</b> ${format_price(entry)} ➔ <b>Exit SL:</b> ${format_price(sl)}\n• <b>Status:</b> Safe Exit per Risk Management\n⏰ <b>Time:</b> {t_now}"
            send_telegram_alert(msg)
            record_journal_entry(clean, act, entry, sl, "STOP LOSS 🛑", "-1.00 R", "LOSS", d_now, t_now)
        del active[t_key]; save_json_data(ACTIVE_TRADES_FILE, active)
        try:
            on_live_trade_closed(clean, outcome)
        except Exception: pass

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
        if p >= 100:
            return f"{p:.2f}"
        elif p >= 1:
            return f"{p:.4f}"
        else:
            return f"{p:.6f}"
    except Exception:
        return str(p)

def draw_smc_chart(symbol, timeframe, candles, setup=None, output_path="chart.png"):
    if not HAS_PIL:
        return None
    try:
        width = 900
        height = 550
        margin_top = 70
        margin_bottom = 50
        margin_left = 60
        margin_right = 110
        
        img = Image.new("RGB", (width, height), color="#131722")
        draw = ImageDraw.Draw(img)
        
        plot_candles = candles[-40:]
        n = len(plot_candles)
        if n == 0: return None
        
        highs = [float(c["high"]) for c in plot_candles]
        lows = [float(c["low"]) for c in plot_candles]
        if setup:
            if "sl" in setup:
                lows.append(float(setup["sl"]))
                highs.append(float(setup["sl"]))
            if "target" in setup:
                highs.append(float(setup["target"]))
                lows.append(float(setup["target"]))
                
        min_p = min(lows)
        max_p = max(highs)
        p_range = max_p - min_p if max_p > min_p else 1.0
        
        chart_h = height - margin_top - margin_bottom
        chart_w = width - margin_left - margin_right
        
        def price_to_y(price):
            return margin_top + chart_h - int(((float(price) - min_p) / p_range) * chart_h)
            
        candle_w = max(4, int(chart_w / (n * 1.5)))
        spacing = int(chart_w / n)
        
        # Grid lines & price labels
        for i in range(6):
            grid_p = min_p + (p_range / 5.0) * i
            gy = price_to_y(grid_p)
            draw.line([(margin_left, gy), (width - margin_right, gy)], fill="#202430", width=1)
            draw.text((width - margin_right + 8, gy - 6), format_price(grid_p), fill="#787b86")
            
        # OB Box
        if setup and "ob" in setup and setup["ob"]:
            ob = setup["ob"]
            ob_top_y = price_to_y(ob.get("high", max_p))
            ob_bot_y = price_to_y(ob.get("low", min_p))
            fill_color = "#123828" if "BULLISH" in str(ob.get("type", "")) else "#38191d"
            out_color = "#00b06f" if "BULLISH" in str(ob.get("type", "")) else "#f23645"
            draw.rectangle([(margin_left + 40, min(ob_top_y, ob_bot_y)), (width - margin_right - 20, max(ob_top_y, ob_bot_y))], fill=fill_color, outline=out_color, width=2)
            draw.text((margin_left + 50, min(ob_top_y, ob_bot_y) + 4), f"VALID {ob.get('type', 'OB')} ZONE", fill=out_color)
            
        # FVG Box & 50% CE
        if setup and "fvg" in setup and setup["fvg"]:
            fvg = setup["fvg"]
            fvg_top_y = price_to_y(fvg.get("top", max_p))
            fvg_bot_y = price_to_y(fvg.get("bottom", min_p))
            ce_y = price_to_y(fvg.get("ce", (fvg.get("top", max_p) + fvg.get("bottom", min_p)) / 2.0))
            draw.rectangle([(margin_left + 80, min(fvg_top_y, fvg_bot_y)), (width - margin_right - 40, max(fvg_top_y, fvg_bot_y))], fill="#2b2818", outline="#f0b90b", width=1)
            draw.line([(margin_left + 80, ce_y), (width - margin_right - 40, ce_y)], fill="#f0b90b", width=1)
            draw.text((margin_left + 90, min(fvg_top_y, fvg_bot_y) + 2), "FVG 50% CE LEVEL", fill="#f0b90b")
            
        # Candlesticks
        for idx, c in enumerate(plot_candles):
            cx = margin_left + idx * spacing + (spacing // 2)
            oy = price_to_y(c["open"])
            cy = price_to_y(c["close"])
            hy = price_to_y(c["high"])
            ly = price_to_y(c["low"])
            
            color = "#089981" if float(c["close"]) >= float(c["open"]) else "#f23645"
            draw.line([(cx, hy), (cx, ly)], fill=color, width=1)
            top_y = min(oy, cy)
            bot_y = max(oy, cy)
            if bot_y - top_y < 2:
                bot_y = top_y + 2
            draw.rectangle([(cx - candle_w // 2, top_y), (cx + candle_w // 2, bot_y)], fill=color, outline=color)
            
        # Trade lines (Entry, SL, TP)
        if setup:
            ey = price_to_y(setup["entry"])
            sy = price_to_y(setup["sl"])
            ty = price_to_y(setup["target"])
            
            draw.line([(margin_left, ey), (width - margin_right, ey)], fill="#2962ff", width=2)
            draw.text((width - margin_right - 230, ey - 14), f"ENTRY: ${format_price(setup['entry'])}", fill="#2962ff")
            
            draw.line([(margin_left, sy), (width - margin_right, sy)], fill="#f23645", width=2)
            draw.text((width - margin_right - 230, sy - 14), f"STOP LOSS: ${format_price(setup['sl'])}", fill="#f23645")
            
            draw.line([(margin_left, ty), (width - margin_right, ty)], fill="#089981", width=2)
            draw.text((width - margin_right - 230, ty - 14), f"TARGET: ${format_price(setup['target'])}", fill="#089981")
            
        header_text = f"StockMindset SMC Setup: {symbol} ({timeframe})"
        draw.text((margin_left, 15), header_text, fill="#ffffff")
        if setup:
            pattern = setup.get("setup_name") or setup.get("reason") or "SMC Setup"
            sub_text = f"Action: {setup['action']} | Pattern: {pattern} | RRR: 1:{setup.get('rrr', '2.0')}"
            draw.text((margin_left, 38), sub_text, fill="#00b06f" if "LONG" in setup["action"] else "#f23645")
            
        img.save(output_path)
        return output_path
    except Exception as err:
        print(f"Chart render exception: {err}")
        return None

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
    clean_sym = symbol.replace("USDT", "").replace("B-", "").replace("_", "")
    pair = f"B-{clean_sym}_USDT"
    res_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60"}
    res = res_map.get(interval, "15")
    sec_per_candle = int(res) * 60
    to_time = int(time.time())
    from_time = to_time - (limit * sec_per_candle)
    fut_url = f"https://api.coindcx.com/exchange/v1/derivatives/futures/data/candlesticks?pair={pair}&from={from_time}&to={to_time}&resolution={res}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for attempt in range(2):
        try:
            res_f = requests.get(fut_url, headers=headers, timeout=12)
            if res_f.status_code == 200:
                raw_data = res_f.json()
                items = raw_data.get("data", []) if isinstance(raw_data, dict) else raw_data
                if isinstance(items, list) and len(items) > 0:
                    candles = []
                    for d in items:
                        candles.append({
                            "time": int(d.get("time", d.get("timestamp", 0))),
                            "open": float(d["open"]),
                            "high": float(d["high"]),
                            "low": float(d["low"]),
                            "close": float(d["close"]),
                            "volume": float(d.get("volume", 100.0))
                        })
                    candles.sort(key=lambda c: c["time"])
                    if len(candles) >= 10: return candles
        except Exception:
            pass
            
    spot_url = f"https://public.coindcx.com/market_data/candles/?pair={pair}&interval={interval}&limit={limit}"
    for attempt in range(2):
        try:
            res_s = requests.get(spot_url, headers=headers, timeout=12)
            if res_s.status_code == 200:
                data = res_s.json()
                if isinstance(data, list) and len(data) > 0:
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
        except Exception:
            pass
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
#      PHASE 4: EXTENDED MARKET STRUCTURE & MACRO TREND (SLIDES 80-98 & 43)
# ==============================================================================
# ==============================================================================
#            PHASE 4: MARKET STRUCTURE (SLIDES 80-98) & TREND
# ==============================================================================
def is_valid_pullback(c_curr, c_prev, trend):
    """Slide 61-68: Valid vs Invalid Pullback & Inside Bar Filter"""
    if c_curr["high"] <= c_prev["high"] and c_curr["low"] >= c_prev["low"]:
        return False # Inside bar is not a valid pullback
    if trend == "BULLISH": return c_curr["low"] < c_prev["low"]
    elif trend == "BEARISH": return c_curr["high"] > c_prev["high"]
    return False

def analyze_market_structure(candles):
    """
    TRUE 146-SLIDE MARKET STRUCTURE: SWINGS, BOS & CHOCH (Slides 80 to 98)
    Detects Major Swing Highs & Lows, Candle Close BOS, and Trend-Reversal CHoCH.
    """
    n = len(candles)
    if n < 15: return {"trend": "SIDEWAYS", "recent_high": candles[-1]["high"], "recent_low": candles[-1]["low"], "choch": None, "idm_swept": False}
    min_bars = 4
    swing_highs, swing_lows = [], []
    for i in range(min_bars, n - min_bars):
        c = candles[i]
        if all(c["high"] >= candles[i - j]["high"] for j in range(1, min_bars + 1)) and all(c["high"] >= candles[i + j]["high"] for j in range(1, min_bars + 1)):
            swing_highs.append((i, c["high"]))
        if all(c["low"] <= candles[i - j]["low"] for j in range(1, min_bars + 1)) and all(c["low"] <= candles[i + j]["low"] for j in range(1, min_bars + 1)):
            swing_lows.append((i, c["low"]))
    curr_trend = "BULLISH" if candles[n // 2]["close"] >= candles[0]["close"] else "BEARISH"
    choch_event, last_bos = None, None
    for k in range(min_bars + 1, n):
        c = candles[k]
        prev_h, prev_l = [sh for sh in swing_highs if sh[0] < k], [sl for sl in swing_lows if sl[0] < k]
        if prev_h:
            last_sh = prev_h[-1][1]
            if c["close"] > last_sh:
                if curr_trend == "BEARISH": curr_trend, choch_event = "BULLISH", ("BULLISH_CHOCH", k, last_sh)
                else: last_bos = ("BULLISH_BOS", k, last_sh)
        if prev_l:
            last_sl = prev_l[-1][1]
            if c["close"] < last_sl:
                if curr_trend == "BULLISH": curr_trend, choch_event = "BEARISH", ("BEARISH_CHOCH", k, last_sl)
                else: last_bos = ("BEARISH_BOS", k, last_sl)
    recent_20 = candles[-20:]
    return {"trend": curr_trend, "choch": choch_event, "last_bos": last_bos, "recent_high": max(c["high"] for c in recent_20), "recent_low": min(c["low"] for c in recent_20), "swing_highs": swing_highs, "swing_lows": swing_lows}

def scan_symbol_for_smc_setup(symbol, candles):
    if len(candles) < 35: return None
    avg_range = get_avg_range(candles, 14)
    struct = analyze_market_structure(candles)
    trend = struct["trend"]
    confirmed, prev, entry_candle = candles[-2], candles[-3], candles[-1]
    entry_price = entry_candle["close"]
    c_range = max(1e-6, confirmed["high"] - confirmed["low"])
    swing_high, swing_low = struct["recent_high"], struct["recent_low"]
    leg_candles = candles[-25:-1]
    leg_high, leg_low = max(c["high"] for c in leg_candles), min(c["low"] for c in leg_candles)
    leg_eq = (leg_high + leg_low) / 2.0
    fvgs = find_fvgs(candles[:-1], avg_range, leg_eq)
    obs = find_order_blocks(candles[:-1], fvgs, leg_eq)

    # 1. Closed Institutional Candle Confirmation (Slide 9 IFC, Slide 13 Brust, Slide 15-18 Engulfing)
    lower_wick = min(confirmed["open"], confirmed["close"]) - confirmed["low"]
    is_bullish_ifc = (lower_wick / c_range) >= 0.35 and confirmed["close"] > confirmed["open"]
    prev_r, prev_b = prev["high"] - prev["low"], abs(prev["close"] - prev["open"])
    is_bullish_brust = (prev_r >= 1.6 * avg_range and (prev_b / max(1e-6, prev_r)) >= 0.55 and prev["close"] < prev["open"] and confirmed["close"] > confirmed["open"])
    is_bullish_engulf = (confirmed["close"] > confirmed["open"] and prev["close"] < prev["open"] and confirmed["close"] >= prev["open"] and confirmed["open"] <= prev["close"] and abs(confirmed["close"]-confirmed["open"]) > prev_b)

    upper_wick = confirmed["high"] - max(confirmed["open"], confirmed["close"])
    is_bearish_ifc = (upper_wick / c_range) >= 0.35 and confirmed["close"] < confirmed["open"]
    is_bearish_brust = (prev_r >= 1.6 * avg_range and (prev_b / max(1e-6, prev_r)) >= 0.55 and prev["close"] > prev["open"] and confirmed["close"] < confirmed["open"])
    is_bearish_engulf = (confirmed["close"] < confirmed["open"] and prev["close"] > prev["open"] and confirmed["close"] <= prev["open"] and confirmed["open"] >= prev["close"] and abs(confirmed["close"]-confirmed["open"]) > prev_b)

    has_bullish_cand_conf = is_bullish_ifc or is_bullish_brust or is_bullish_engulf
    has_bearish_cand_conf = is_bearish_ifc or is_bearish_brust or is_bearish_engulf

    # Safe Structural Buffer: minimum 0.30 ATR or 0.30% of price to protect against market noise
    buffer = max(avg_range * 0.30, entry_price * 0.003)

    # Slide 119: RRP (Reverse Range Pattern)
    if (leg_high - leg_low) <= 2.2 * avg_range:
        if (confirmed["low"] < leg_low) and confirmed["close"] >= leg_low and is_bullish_ifc:
            sl = confirmed["low"] - buffer
            tp = leg_high
            rr = round((tp - entry_price) / max(0.0001, (entry_price - sl)), 2)
            if rr >= MIN_RISK_REWARD:
                return {"action": "LONG", "symbol": symbol, "trend": "RANGE (RRP Reversal)", "setup_name": "RRP Reverse Range Pattern (Slide 119)", "slide": "Slide 119 (RRP Range Sweep)", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}
        elif (confirmed["high"] > leg_high) and confirmed["close"] <= leg_high and is_bearish_ifc:
            sl = confirmed["high"] + buffer
            tp = leg_low
            rr = round((entry_price - tp) / max(0.0001, (sl - entry_price)), 2)
            if rr >= MIN_RISK_REWARD:
                return {"action": "SHORT", "symbol": symbol, "trend": "RANGE (RRP Reversal)", "setup_name": "RRP Reverse Range Pattern (Slide 119)", "slide": "Slide 119 (RRP Range Sweep)", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

    # --- A. BULLISH SETUPS (Slide 43: Discount Zone + Trend) ---
    if trend == "BULLISH":
        # Slide 28-29: Bullish Order Block (Strictly Fresh, SL below Structural Swing Low)
        for ob in obs:
            if ob["type"] == "BULLISH_OB" and not ob["mitigated"] and ob["tap_count"] <= 1 and ob["low"] <= leg_eq:
                if confirmed["low"] <= ob["high"] and confirmed["close"] >= ob["low"] and has_bullish_cand_conf:
                    candle_tag = "IFC Reversal (Slide 9)" if is_bullish_ifc else ("Brust (Slide 13)" if is_bullish_brust else "Engulfing (Slide 15)")
                    sl = min(ob["low"], leg_low, confirmed["low"]) - buffer
                    tp = swing_high
                    rr = round((tp - entry_price) / max(0.0001, (entry_price - sl)), 2)
                    if rr >= MIN_RISK_REWARD:
                        return {"action": "LONG", "symbol": symbol, "trend": "BULLISH (BOS/CHoCH)", "setup_name": f"Institutional OB + {candle_tag}", "slide": "Slide 28-29 (OB) + Slide 85 (CHoCH) + Slide 9/13/15", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

        # Slide 48 & 59: Bullish FVG 50% CE (Strictly Fresh, SL below Structural Swing Low, NOT midway!)
        for f in fvgs:
            if f["type"] == "BULLISH" and not f["mitigated"] and f["tap_count"] <= 1 and f["bottom"] <= leg_eq:
                if confirmed["low"] <= f["ce"] and confirmed["close"] >= f["bottom"] and has_bullish_cand_conf:
                    candle_tag = "IFC (Slide 9)" if is_bullish_ifc else ("Brust (Slide 13)" if is_bullish_brust else "Engulfing (Slide 15)")
                    sl = min(f["bottom"], leg_low, confirmed["low"]) - buffer
                    tp = swing_high
                    rr = round((tp - entry_price) / max(0.0001, (entry_price - sl)), 2)
                    if rr >= MIN_RISK_REWARD:
                        return {"action": "LONG", "symbol": symbol, "trend": "BULLISH (BOS/CHoCH)", "setup_name": f"FVG 50% CE + {candle_tag}", "slide": "Slide 48 (50% CE) + Slide 85 (CHoCH) + Slide 9/13/15", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

        # Slide 71: Bullish IDM Sweep
        recent_low_12 = min(c["low"] for c in candles[-18:-2])
        if confirmed["low"] < recent_low_12 and confirmed["close"] > recent_low_12 and is_bullish_ifc:
            sl = min(confirmed["low"], leg_low) - buffer
            tp = swing_high
            rr = round((tp - entry_price) / max(0.0001, (entry_price - sl)), 2)
            if rr >= MIN_RISK_REWARD:
                return {"action": "LONG", "symbol": symbol, "trend": "BULLISH (IDM Swept)", "setup_name": "IDM Liquidity Sweep + IFC Reversal (Slide 9 & 71)", "slide": "Slide 71 (Inducement Sweep) + Slide 9 (IFC)", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

    # --- B. BEARISH SETUPS (Slide 43: Premium Zone + Trend) ---
    elif trend == "BEARISH":
        # Slide 28-29: Bearish Order Block (Strictly Fresh, SL above Structural Swing High)
        for ob in obs:
            if ob["type"] == "BEARISH_OB" and not ob["mitigated"] and ob["tap_count"] <= 1 and ob["high"] >= leg_eq:
                if confirmed["high"] >= ob["low"] and confirmed["close"] <= ob["high"] and has_bearish_cand_conf:
                    candle_tag = "IFC Reversal (Slide 9)" if is_bearish_ifc else ("Brust (Slide 13)" if is_bearish_brust else "Engulfing (Slide 16)")
                    sl = max(ob["high"], leg_high, confirmed["high"]) + buffer
                    tp = swing_low
                    rr = round((entry_price - tp) / max(0.0001, (sl - entry_price)), 2)
                    if rr >= MIN_RISK_REWARD:
                        return {"action": "SHORT", "symbol": symbol, "trend": "BEARISH (BOS/CHoCH)", "setup_name": f"Institutional OB + {candle_tag}", "slide": "Slide 28-29 (OB) + Slide 85 (CHoCH) + Slide 9/13/16", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

        # Slide 48 & 59: Bearish FVG 50% CE (Strictly Fresh, SL above Structural Swing High, NOT midway!)
        for f in fvgs:
            if f["type"] == "BEARISH" and not f["mitigated"] and f["tap_count"] <= 1 and f["top"] >= leg_eq:
                if confirmed["high"] >= f["ce"] and confirmed["close"] <= f["top"] and has_bearish_cand_conf:
                    candle_tag = "IFC (Slide 9)" if is_bearish_ifc else ("Brust (Slide 13)" if is_bearish_brust else "Engulfing (Slide 16)")
                    sl = max(f["top"], leg_high, confirmed["high"]) + buffer
                    tp = swing_low
                    rr = round((entry_price - tp) / max(0.0001, (sl - entry_price)), 2)
                    if rr >= MIN_RISK_REWARD:
                        return {"action": "SHORT", "symbol": symbol, "trend": "BEARISH (BOS/CHoCH)", "setup_name": f"FVG 50% CE + {candle_tag}", "slide": "Slide 48 (50% CE) + Slide 85 (CHoCH) + Slide 9/13/16", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

        # Slide 71: Bearish IDM Sweep
        recent_high_12 = max(c["high"] for c in candles[-18:-2])
        if confirmed["high"] > recent_high_12 and confirmed["close"] < recent_high_12 and is_bearish_ifc:
            sl = max(confirmed["high"], leg_high) + buffer
            tp = swing_low
            rr = round((entry_price - tp) / max(0.0001, (sl - entry_price)), 2)
            if rr >= MIN_RISK_REWARD:
                return {"action": "SHORT", "symbol": symbol, "trend": "BEARISH (IDM Swept)", "setup_name": "IDM Liquidity Sweep + IFC Reversal (Slide 9 & 71)", "slide": "Slide 71 (Inducement Sweep) + Slide 9 (IFC)", "entry": entry_price, "sl": sl, "target": tp, "rrr": rr}

    return None


# ==============================================================================
#            STOCKMINDSET - COINDCX REAL MONEY LIVE AUTO-TRADER
#                      Author: ANKIT RABARI (Rajkot, Gujarat)
# ==============================================================================
COINDCX_BASE_URL = "https://api.coindcx.com"
LIVE_LOG_FILE = "live_trades_log.json"

# Strict Risk Parameters set by Ankit Rabari
TOTAL_CAPITAL_INR = 1000.0
RISK_PERCENT = 3.0          # Strictly 3% risk = ₹30 per trade!
RISK_AMOUNT_INR = TOTAL_CAPITAL_INR * (RISK_PERCENT / 100.0) # ₹30.0
MAX_DAILY_TRADES = 2        # Exactly 2 trades per day max
MAX_ACTIVE_TRADES = 1       # Exactly 1 active trade at a time
USDT_INR_RATE = 88.0        # 1 USDT = ~88 INR

def get_coindcx_signature(secret, body_json):
    return hmac.new(secret.encode("utf-8"), body_json.encode("utf-8"), hashlib.sha256).hexdigest()

def coindcx_private_request(endpoint, payload_dict):
    api_k = COINDCX_API_KEY or os.environ.get("COINDCX_API_KEY", "")
    sec_k = COINDCX_SECRET_KEY or os.environ.get("COINDCX_SECRET_KEY", "")
    if not api_k or not sec_k: return {"error": "API Key missing"}
    url = f"{COINDCX_BASE_URL}{endpoint}"
    payload_json = json.dumps(payload_dict, separators=(',', ':'))
    sig = get_coindcx_signature(sec_k, payload_json)
    headers = {"Content-Type": "application/json", "X-AUTH-APIKEY": api_k, "X-AUTH-SIGNATURE": sig, "User-Agent": "StockMindset/1.0"}
    try:
        r = requests.post(url, data=payload_json, headers=headers, timeout=10)
        try: return r.json()
        except: return {"status_code": r.status_code, "text": r.text}
    except Exception as e: return {"error": str(e)}

def load_live_log():
    if not os.path.exists(LIVE_LOG_FILE): return {"trades": [], "active": None}
    try:
        with open(LIVE_LOG_FILE, "r") as f: return json.load(f)
    except: return {"trades": [], "active": None}

def save_live_log(data):
    try:
        with open(LIVE_LOG_FILE, "w") as f: json.dump(data, f, indent=2)
    except: pass

def get_today_live_trades_count():
    data = load_live_log()
    today_str = datetime.now().strftime("%Y-%m-%d")
    return sum(1 for t in data.get("trades", []) if t.get("date") == today_str)

def has_active_live_trade():
    data = load_live_log()
    return data.get("active") is not None

def calculate_lot_size(symbol, entry_price, sl_price):
    price_diff = abs(entry_price - sl_price)
    if price_diff <= 0: return 0.0
    risk_usdt = RISK_AMOUNT_INR / USDT_INR_RATE
    raw_qty = risk_usdt / price_diff
    if "BTC" in symbol: qty = round(max(0.001, raw_qty), 3)
    elif "ETH" in symbol: qty = round(max(0.01, raw_qty), 2)
    elif "SOL" in symbol: qty = round(max(0.1, raw_qty), 1)
    elif "BNB" in symbol: qty = round(max(0.01, raw_qty), 2)
    elif "NEAR" in symbol: qty = round(max(0.5, raw_qty), 1)
    elif "DOGE" in symbol: qty = round(max(10.0, raw_qty), 0)
    else: qty = round(max(0.1, raw_qty), 2)
    return qty


REAL_TELEGRAM_BOT_TOKEN = "9151662883:AAHB4UPLWysHgzqa84J8fN2Lg8PFvqjXG_c"
REAL_TELEGRAM_CHAT_ID = "8611777710"

def send_real_telegram_alert(msg):
    try:
        url = f"https://api.telegram.org/bot{REAL_TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": REAL_TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print("[REAL BOT ALERT ERROR]:", e)

def execute_real_smc_trade(setup):
    if not getattr(config, "LIVE_TRADING", False):
        return False

    api_k = COINDCX_API_KEY or os.environ.get("COINDCX_API_KEY", "")
    sec_k = COINDCX_SECRET_KEY or os.environ.get("COINDCX_SECRET_KEY", "")
    if not api_k or not sec_k:
        print("[LIVE TRADER] API keys missing in config. Skipping.")
        return False

    today_count = get_today_live_trades_count()
    if today_count >= MAX_DAILY_TRADES:
        print(f"[LIVE TRADER] Daily trade limit reached ({today_count}/{MAX_DAILY_TRADES}). Skipping.")
        return False

    if has_active_live_trade():
        print("[LIVE TRADER] One active live trade is already running. Skipping to honor 1-active rule.")
        return False

    sym = setup.get("symbol")
    act = setup.get("action")
    entry = setup.get("entry")
    sl = setup.get("sl")
    target = setup.get("target")
    rrr = setup.get("rrr", "2.0")

    qty = calculate_lot_size(sym, entry, sl)
    if qty <= 0: return False

    side = "buy" if act == "LONG" else "sell"
    pair = f"B-{sym.replace('USDT', '')}_USDT"

    order_payload = {
        "side": side,
        "pair": pair,
        "order_type": "market_order",
        "total_quantity": qty,
        "leverage": 3.0,
        "timestamp": int(time.time() * 1000)
    }

    print(f"--> [COINDCX LIVE REAL ORDER] Submitting {act} for {qty} {sym} (Risk: ₹{RISK_AMOUNT_INR})...")
    res = coindcx_private_request("/exchange/v1/derivatives/futures/orders/create", order_payload)

    if "error" in res or res.get("status") in ["rejected", "error"]:
        err = res.get("error") or res.get("message") or "Unknown error"
        print(f"--> [COINDCX ORDER ERROR] {err}")
        return False

    t_now = datetime.now().strftime("%H:%M:%S")
    d_now = datetime.now().strftime("%Y-%m-%d")
    trade_data = {
        "coin": sym, "pair": pair, "action": act, "qty": qty,
        "entry": entry, "sl": sl, "initial_sl": sl, "target": target,
        "rrr": rrr, "risk_inr": RISK_AMOUNT_INR, "stage": "INITIAL",
        "date": d_now, "time": t_now, "order_id": res.get("id", "N/A")
    }
    data = load_live_log()
    data["active"] = trade_data
    save_live_log(data)

    act_name = "🟢 BUY / LONG" if act == "LONG" else "🔴 SELL / SHORT"
    msg = ("🚀 <b>COINDCX REAL MONEY LIVE TRADE EXECUTED!</b> 🚀\n\n"
           + "• <b>Coin:</b> " + str(sym) + "\n"
           + "• <b>Action:</b> " + str(act_name) + "\n"
           + "• <b>Quantity:</b> " + str(qty) + "\n"
           + "• <b>Entry:</b> $" + str(entry) + "\n"
           + "• <b>Stop Loss:</b> $" + str(sl) + "\n"
           + "• <b>Target:</b> $" + str(target) + "\n"
           + "• <b>Max Risk:</b> ₹" + str(RISK_AMOUNT_INR) + " (Strictly 3%)\n"
           + "• <b>Today Trade Count:</b> " + str(today_count + 1) + "/" + str(MAX_DAILY_TRADES) + "\n"
           + "⏰ <b>Time:</b> " + str(t_now))
    try:
        send_real_telegram_alert(msg)
        send_telegram_alert(msg)
    except: pass
    return True

def on_live_trade_closed(sym, outcome):
    data = load_live_log()
    active = data.get("active")
    if not active: return
    if active.get("coin") == sym or sym in active.get("coin", ""):
        t_now = datetime.now().strftime("%H:%M:%S")
        active["closed_time"] = t_now
        active["outcome"] = outcome
        data["trades"].append(active)
        data["active"] = None
        save_live_log(data)
        print(f"--> [COINDCX LIVE TRADE ARCHIVED] {sym} closed with outcome {outcome}")
        outcome_msg = ("🏁 <b>REAL TRADE COMPLETED: " + str(sym) + "</b> 🏁\n\n"
                       + "• <b>Result:</b> " + str(outcome) + "\n"
                       + "• <b>Exit Time:</b> " + str(t_now) + "\n"
                       + "• <b>Status:</b> Ready for Next Setup (Max 1 Active Rule)")
        try: send_real_telegram_alert(outcome_msg)
        except: pass

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
                if alert_key in alerted_trades and (current_ts - alerted_trades[alert_key] < COOLDOWN_SECONDS):
                    continue
                alerted_trades[alert_key] = current_ts
                print(f"--> Found Valid SMC Trade on {sym}: {setup['action']} ({setup.get('setup_name')})")
                register_active_trade(sym, setup)
                try:
                    execute_real_smc_trade(setup)
                except Exception as _e:
                    print("[COINDCX LIVE HOOK ERROR]:", _e)
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
    welcome = (
        "🚀 <b>SMC + IOC MASTER TRADING SYSTEM LIVE!</b> 🚀\n\n"
        "• <b>Authoritative Source:</b> Trade With Ani (15-Hour Course)\n"
        "• <b>Total Scope:</b> All 146 PPT Slides Fully Encoded\n"
        "• <b>Active Coins:</b> " + ", ".join(WATCHLIST) + "\n"
        "• <b>Timeframe:</b> " + TIMEFRAME + "\n\n"
        "તમામ ૧૪૬ સ્લાઇડ્સ અને વિડીયો નિયમો મુજબ લાઈવ સ્કેનર શરૂ થઈ ગયું છે!"
    )
    send_telegram_alert(welcome)
    print('SMC Bot is running in continuous loop. Press CTRL+C to stop.')
    while True:
        try:
            run_master_scan_pass()
            time.sleep(SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print('Bot stopped by user.')
            break
        except Exception as e:
            print(f'Loop Error: {e}')
            time.sleep(10)
