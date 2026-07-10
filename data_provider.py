import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging
from datetime import datetime
import config

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class MT5DataProvider:
    def __init__(self):
        self.symbol = config.MT5_SYMBOL
        self.terminal_path = config.MT5_TERMINAL_PATH
        self.connected = False

    def connect(self) -> bool:
        """Initialize connection to MetaTrader 5."""
        if self.connected:
            return True

        logger.info("Initializing connection to MetaTrader 5...")
        
        # Initialize MT5. If path is specified, use it. Otherwise, MT5 finds it automatically.
        if self.terminal_path:
            init_success = mt5.initialize(path=self.terminal_path)
        else:
            init_success = mt5.initialize()

        if not init_success:
            logger.error(f"Failed to initialize MT5. Error code: {mt5.last_error()}")
            self.connected = False
            return False

        # Check if the symbol is available and select it
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logger.error(f"Symbol {self.symbol} not found in MT5.")
            mt5.shutdown()
            self.connected = False
            return False

        if not symbol_info.visible:
            logger.info(f"Selecting symbol {self.symbol} in Market Watch...")
            if not mt5.symbol_select(self.symbol, True):
                logger.error(f"Failed to select symbol {self.symbol}.")
                mt5.shutdown()
                self.connected = False
                return False

        self.connected = True
        logger.info(f"Successfully connected to MT5. Symbol {self.symbol} is ready.")
        return True

    def disconnect(self):
        """Shutdown MT5 connection."""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MetaTrader 5.")

    def get_timeframe_constant(self, tf_str: str):
        """Map string timeframe to MT5 constant."""
        tf_mapping = {
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1
        }
        return tf_mapping.get(tf_str.upper(), mt5.TIMEFRAME_H1)

    def fetch_rates(self, timeframe_str: str, count: int = 500) -> pd.DataFrame:
        """Fetch historical candle rates from MT5."""
        if not self.connect():
            raise ConnectionError("MetaTrader 5 terminal is not running or could not be initialized.")

        tf_const = self.get_timeframe_constant(timeframe_str)
        logger.info(f"Fetching {count} bars for {self.symbol} on {timeframe_str}...")
        
        rates = mt5.copy_rates_from_pos(self.symbol, tf_const, 0, count)
        if rates is None or len(rates) == 0:
            error_code = mt5.last_error()
            logger.error(f"Failed to fetch rates for {self.symbol} on {timeframe_str}. Error: {error_code}")
            raise ValueError(f"Could not retrieve rates from MT5. Error code: {error_code}")

        # Convert numpy structured array to pandas DataFrame
        df = pd.DataFrame(rates)
        # Convert time to datetime object
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Ensure correct column casing and types
        df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']]
        return df

    def get_current_price(self) -> float:
        """Get the latest tick close price."""
        if not self.connect():
            raise ConnectionError("MetaTrader 5 terminal is not running.")
            
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            # Fallback to copy last rate
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, 1)
            if rates is not None and len(rates) > 0:
                return float(rates[0]['close'])
            raise ValueError(f"Failed to get tick or price for {self.symbol}")
            
        return float(tick.bid + tick.ask) / 2.0  # Middle price

    def place_limit_order(self, order_type: str, price: float, sl: float, tp: float, volume: float = None) -> tuple[bool, str]:
        """Place a pending Buy/Sell Limit order on MT5 with SL and TP."""
        if not self.connect():
            return False, "MetaTrader 5 terminal is not running or could not be initialized."

        if volume is None:
            volume = config.DEFAULT_LOT

        # Determine order type
        if order_type.upper() == "BUY":
            mt5_order_type = mt5.ORDER_TYPE_BUY_LIMIT
        elif order_type.upper() == "SELL":
            mt5_order_type = mt5.ORDER_TYPE_SELL_LIMIT
        else:
            return False, f"Invalid order type: {order_type}"

        # Get symbol details to determine filling mode
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            return False, f"Symbol {self.symbol} not found in MT5."

        # Default filling mode is RETURN, but check broker supported options
        # In python MT5 package, SYMBOL_FILLING_FOK (1) and SYMBOL_FILLING_IOC (2) constants are not exposed.
        filling = mt5.ORDER_FILLING_RETURN
        if symbol_info.filling_mode & 1:  # SYMBOL_FILLING_FOK
            filling = mt5.ORDER_FILLING_FOK
        elif symbol_info.filling_mode & 2:  # SYMBOL_FILLING_IOC
            filling = mt5.ORDER_FILLING_IOC


        # Build trade request
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": self.symbol,
            "volume": float(volume),
            "type": mt5_order_type,
            "price": float(round(price, 2)),
            "sl": float(round(sl, 2)),
            "tp": float(round(tp, 2)),
            "deviation": 20,
            "magic": 223344,
            "comment": "XauScan Bot Limit",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        logger.info(f"Sending order request: {request}")
        result = mt5.order_send(request)

        if result is None:
            err_code = mt5.last_error()
            logger.error(f"mt5.order_send returned None. Error: {err_code}")
            return False, f"Otorisasi/koneksi MT5 gagal atau order_send mengembalikan None (Error: {err_code})"

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order failed. Retcode: {result.retcode}, Comment: {result.comment}")
            return False, f"Order ditolak oleh broker. Kode: {result.retcode}, Keterangan: {result.comment}"

        logger.info(f"Order placed successfully! Order ticket ID: {result.order}")
        return True, f"Berhasil memasang pending order! Tiket ID: {result.order}"

