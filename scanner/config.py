import os

def load_env():
    """Load environment variables from a local .env file if it exists."""
    paths = [".env", "../.env"]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        val = v.strip()
                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                            val = val[1:-1]
                        os.environ[k.strip()] = val
            break

# Load env variables
load_env()

# Telegram Configuration
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_TELEGRAM_CHAT_ID")

# Gemini AI Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Trading Mode Configuration (swing or scalping)
DEFAULT_TRADING_MODE = os.environ.get("TRADING_MODE", "swing").lower()
if DEFAULT_TRADING_MODE not in ["swing", "scalping", "sniper"]:
    DEFAULT_TRADING_MODE = "swing"
CURRENT_TRADING_MODE = DEFAULT_TRADING_MODE


# MT5 Connection Configuration
# Leave empty for default path, or specify the path to terminal.exe if needed
MT5_TERMINAL_PATH = os.environ.get("MT5_TERMINAL_PATH", "")
DEFAULT_LOT = float(os.environ.get("DEFAULT_LOT", "0.01"))

MT5_SYMBOL = os.environ.get("MT5_SYMBOL", "XAUUSDm")

def get_symbol_suffix():
    symbol = MT5_SYMBOL
    # Strip common base symbols to find suffix
    for base in ["XAUUSD", "GOLD"]:
        if base in symbol:
            return symbol.replace(base, "")
    return ""

SUPPORTED_PAIRS = {
    "xau": MT5_SYMBOL,
    "eur": "EURUSD" + get_symbol_suffix(),
    "gbp": "GBPUSD" + get_symbol_suffix(),
    "jpy": "USDJPY" + get_symbol_suffix(),
    "btc": "BTCUSD" + get_symbol_suffix()
}


# Analysis Configuration
EMA_FAST = 50
EMA_SLOW = 200

# Scoring Thresholds
MIN_SCORE_SHOW = 5.0        # Minimum score to output a signal
HIGH_PROBABILITY_SCORE = 8.5 # Score to classify as High Probability

# Session Configuration (in GMT+7 WIB Timezone)
TIMEZONE_STR = "Asia/Jakarta"

ASIA_START_HOUR = 7     # 07:00 WIB
ASIA_END_HOUR = 15      # 15:00 WIB

LONDON_START_HOUR = 14  # 14:00 WIB
LONDON_END_HOUR = 22    # 22:00 WIB

NY_START_HOUR = 19      # 19:00 WIB
NY_END_HOUR = 3         # 03:00 WIB (keesokan harinya)

# Killzone Hours (WIB)
LONDON_KILLZONE_START = 14
LONDON_KILLZONE_END = 17

NY_KILLZONE_START = 19.5  # 19:30 WIB
NY_KILLZONE_END = 22.5    # 22:30 WIB

# Fibonacci levels to search for overlap
FIBO_LEVELS = [0.618, 0.786]
FIBO_THRESHOLD = 0.001 # 0.1% tolerance for overlap (about 2-3 pips)

# Pivot calculation formula: Standard / Classic
# Pivot Point (PP) = (High + Low + Close) / 3
# Support 1 (S1) = (2 * PP) - High
# Resistance 1 (R1) = (2 * PP) - Low
