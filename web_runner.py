import os, threading, time
from flask import Flask
import smc_bot

app = Flask(__name__)

@app.route('/')
def home():
    return {
        "status": "ONLINE",
        "system": "StockMindset SMC 146-Slide Engine",
        "author": "ANKIT RABARI (Rajkot, Gujarat)",
        "message": "Bot is actively scanning 24/7 on Cloud!"
    }

def start_bot():
    while True:
        try:
            smc_bot.run_master_scan_pass()
            time.sleep(smc_bot.SCAN_INTERVAL_SECONDS)
        except Exception as e:
            time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=start_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
