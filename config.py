# ==============================================================================
#                      SMC TRADING BOT - CONFIGURATION
#             (તમારા તમામ સેટિંગ્સ - ભવિષ્યમાં અહીંથી જ ફેરફાર કરવો)
# ==============================================================================

# ટેલિગ્રામ વિગતો
TELEGRAM_BOT_TOKEN = "9005788701:AAE-kGlVndkg5TqvUKEeOo91kNM2npV7X_w"
TELEGRAM_CHAT_ID = "8611777710"

# CoinDCX / Binance ના મુખ્ય ફ્યુચર્સ કોઈન્સની લિસ્ટ (તમામ મુખ્ય કોઈન સ્કેન થશે)
WATCHLIST = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "NEARUSDT"
]

# ટાઇમફ્રેમ
TIMEFRAME = "15m"           # 15 મિનિટ કેન્ડલ્સ
SCAN_INTERVAL_SECONDS = 30  # દરેક કોઈનને સ્કેન કરવાનો સમય

# પેપર ટ્રેડિંગ અને રિસ્ક મેનેજમેન્ટ
PAPER_TRADING_MODE = True   # અત્યારે પેપર ટ્રેડિંગ માટે કોઈ લિમિટ લોક નથી
MIN_RISK_REWARD = 2.0       # ઓછામાં ઓછું 1:2 RRR હોવું જોઈએ
RISK_PER_TRADE_PERCENT = 1.0# ટ્રેડ દીઠ 1% રિસ્ક

# ભવિષ્યમાં CoinDCX માં લાઈવ ટ્રેડ કરવા માટે:
LIVE_TRADING = True        # જ્યારે અસલી ઓર્ડર મુકવા હોય ત્યારે True કરવું
COINDCX_API_KEY = "815eace59991bb09e930e3bb5c31f714b12007221dfb9118"
COINDCX_SECRET_KEY = "9cf9b4528c9485ddaaea0a5e9d654a17d64cac2dbdd9c805c8d6580c4bd87ea3"

# રિયલ મની લાઈવ ટ્રેડિંગ ટેલિગ્રામ બોટ (@stockmindset_real_bot)
REAL_TELEGRAM_BOT_TOKEN = "9151662883:AAHB4UPLWysHgzqa84J8fN2Lg8PFvqjXG_c"
REAL_TELEGRAM_CHAT_ID = "8611777710"

COINDCX_API_KEY = "815eace59991bb09e930e3bb5c31f714b12007221dfb9118"
COINDCX_SECRET_KEY = "9cf9b4528c9485ddaaea0a5e9d654a17d64cac2dbdd9c805c8d6580c4bd87ea3"
LIVE_TRADING = True
