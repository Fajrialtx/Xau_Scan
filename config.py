import os

def load_env():
    """Load environment variables from a local .env file if it exists."""
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

# Load env variables
load_env()

# Telegram Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# MT5 Connection Configuration
# Leave empty for default path, or specify the path to terminal.exe if needed
MT5_TERMINAL_PATH = os.environ.get("MT5_TERMINAL_PATH", "")
MT5_SYMBOL = os.environ.get("MT5_SYMBOL", "XAUUSD")

# Analysis Configuration
EMA_FAST = 50
EMA_SLOW = 200

# Scoring Thresholds
MIN_SCORE_SHOW = 5.0        # Minimum score to output a signal
HIGH_PROBABILITY_SCORE = 8.5 # Score to classify as High Probability

# Asia Session Configuration (in UTC+7 Timezone)
ASIA_START_HOUR = 7    # 07:00 WIB
ASIA_END_HOUR = 15     # 15:00 WIB
TIMEZONE_STR = "Asia/Jakarta"

# Fibonacci levels to search for overlap
FIBO_LEVELS = [0.618, 0.786]
FIBO_THRESHOLD = 0.001 # 0.1% tolerance for overlap (about 2-3 pips)

# Pivot calculation formula: Standard / Classic
# Pivot Point (PP) = (High + Low + Close) / 3
# Support 1 (S1) = (2 * PP) - High
# Resistance 1 (R1) = (2 * PP) - Low
