# ==============================================================================
#                      SMC TRADING BOT - CONFIGURATION
# ==============================================================================

TELEGRAM_BOT_TOKEN = "9005788701:AAE-kGlVndkg5TqvUKEeOo91kNM2npV7X_w"
TELEGRAM_CHAT_ID = "8611777710"

# CoinDCX ના ઓફિશિયલ ફ્યુચર્સ કોઈન્સની લિસ્ટ
WATCHLIST = [
    "B-BTC_USDT",
    "B-ETH_USDT",
    "B-SOL_USDT",
    "B-XRP_USDT",
    "B-BNB_USDT",
    "B-DOGE_USDT",
    "B-AVAX_USDT",
    "B-NEAR_USDT"
]

TIMEFRAME = "15m"           # 15 મિનિટ કેન્ડલ્સ
SCAN_INTERVAL_SECONDS = 30  # દરેક સ્કેન રાઉન્ડ વચ્ચેનો સમય

# પેપર ટ્રેડિંગ મોડ
PAPER_TRADING_MODE = True
MIN_RISK_REWARD = 2.0
RISK_PER_TRADE_PERCENT = 1.0

# ભવિષ્યમાં લાઈવ ટ્રેડિંગ માટે:
LIVE_TRADING = True
COINDCX_API_KEY = "65f045449b7822403d277a39ee93fb9ce4e973883709a062"
COINDCX_SECRET_KEY = "17217d4a50946a171f6ab075e5d11b3972c5149a2c66c9a9e3d87d409c6f012b"
