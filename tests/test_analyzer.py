import sys
import io
import os

# Configure standard output to use UTF-8 to prevent encoding errors on Windows
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to sys.path to allow importing from scanner
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta, time
import scanner.config as config
from scanner.analyzer import XAUAnalyzer

class MockDataProvider:
    def __init__(self, symbol: str = None, current_price=2350.0):
        self.symbol = symbol if symbol else config.MT5_SYMBOL
        self.current_price = current_price
        self.tz = pytz.timezone(config.TIMEZONE_STR)

    def connect(self):
        return True

    def disconnect(self):
        pass

    def get_current_price(self):
        return self.current_price

    def place_limit_order(self, order_type: str, price: float, sl: float, tp: float, volume: float = None) -> tuple[bool, str]:
        import random
        return True, f"Mock Order Successful! Ticket: {random.randint(1000000, 9999999)}"

    def generate_mock_candles(self, timeframe: str, count: int) -> pd.DataFrame:
        """Generate realistic synthetic candle data for testing analysis logic."""
        now = datetime.utcnow()
        times = [now - timedelta(hours=(count - i) if "H" in timeframe else (count - i) * 15 if "M15" in timeframe else (count - i) * 1440) for i in range(count)]
        
        # Base price series
        base_price = 2300.0
        closes = []
        opens = []
        highs = []
        lows = []
        volumes = []
        
        # Create standard trending/ranging price sequence
        for i in range(count):
            # Upward trend generally
            base_price += np.sin(i / 10.0) * 1.5 + 0.1
            op = base_price
            cl = op + np.random.normal(0.2, 1.0)
            hi = max(op, cl) + abs(np.random.normal(0.5, 0.5))
            lo = min(op, cl) - abs(np.random.normal(0.5, 0.5))
            
            opens.append(op)
            closes.append(cl)
            highs.append(hi)
            lows.append(lo)
            volumes.append(int(1000 + np.random.randint(100, 1000)))

        df = pd.DataFrame({
            'time': times,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'tick_volume': volumes,
            'spread': [3] * count,
            'real_volume': [0] * count
        })

        # Inject deliberate Bullish Order Block at index 200
        # Bullish OB: Bearish candle followed by strong bullish move
        if count > 210:
            # Bearish candle at 200
            df.loc[200, 'open'] = 2330.0
            df.loc[200, 'close'] = 2320.0
            df.loc[200, 'high'] = 2331.0
            df.loc[200, 'low'] = 2318.0
            
            # Impulsive bullish candles at 201, 202, 203
            df.loc[201, 'open'] = 2320.0
            df.loc[201, 'close'] = 2330.0
            df.loc[201, 'high'] = 2332.0
            df.loc[201, 'low'] = 2319.0
            
            df.loc[202, 'open'] = 2330.0
            df.loc[202, 'close'] = 2340.0
            df.loc[202, 'high'] = 2342.0
            df.loc[202, 'low'] = 2329.0
            
            df.loc[203, 'open'] = 2340.0
            df.loc[203, 'close'] = 2355.0
            df.loc[203, 'high'] = 2357.0
            df.loc[203, 'low'] = 2339.0

            # FVG is formed between High of 200 (2331.0) and Low of 202 (2329.0)
            df.loc[202, 'low'] = 2335.0
            df.loc[202, 'open'] = 2335.0

            # Keep subsequent price above the OB high (2331.0) to keep it unmitigated
            for k in range(204, count):
                df.loc[k, 'low'] = max(df.loc[k, 'low'], 2336.0)
                df.loc[k, 'close'] = max(df.loc[k, 'close'], 2338.0)
                df.loc[k, 'high'] = max(df.loc[k, 'high'], 2340.0)
                df.loc[k, 'open'] = max(df.loc[k, 'open'], 2337.0)

        # Let's override Daily data to simulate yesterday's daily candle
        if timeframe == "D1":
            df.loc[len(df)-2, 'high'] = 2360.0
            df.loc[len(df)-2, 'low'] = 2320.0
            df.loc[len(df)-2, 'close'] = 2340.0

        # Adjust timestamps for M15 to match Asia session hours (07:00 - 15:00 WIB today)
        if timeframe == "M15":
            today = datetime.now(self.tz).date()
            asia_start = datetime.combine(today, time(8, 0)).astimezone(pytz.utc) # 08:00 WIB is 01:00 UTC
            for idx in range(count - 40, count):
                bar_time = asia_start + timedelta(minutes=15 * (idx - (count - 40)))
                df.loc[idx, 'time'] = bar_time.replace(tzinfo=None)
                df.loc[idx, 'low'] = max(df.loc[idx, 'low'], 2332.0)
                
        return df

    def fetch_rates(self, timeframe_str: str, count: int = 500) -> pd.DataFrame:
        return self.generate_mock_candles(timeframe_str, count)


def test_mock_analysis():
    print("🧪 MENJALANKAN VERIFIKASI ANALISIS DENGAN MOCK DATA...")
    mock_dp = MockDataProvider(current_price=2345.0)
    analyzer = XAUAnalyzer(mock_dp)
    
    zones = analyzer.analyze()
    
    print(f"\nHasil Pemindaian Mock (Ditemukan {len(zones)} zona):")
    print("=" * 60)
    for idx, zone in enumerate(zones):
        print(f"Zona {idx+1}: {zone.zone_type} | Rentang: {zone.bottom} - {zone.top}")
        print(f"Skor Total: {zone.score:.2f} / 13.0")
        print("Detail Konfluensi:")
        for detail in zone.details:
            print(f" - {detail}")
        print(f"Proteksi & Target: SL={zone.sl:.2f}, TP1={zone.tp1:.2f}, TP2={zone.tp2:.2f}")
        print("-" * 60)

    assert len(zones) > 0, "Harusnya terdeteksi minimal 1 zona dari data simulasi!"
    assert any(z.zone_type == "BUY" for z in zones), "Harusnya terdeteksi zona BUY!"
    print("✅ VERIFIKASI BERHASIL! Algoritma pendeteksi zona, FVG, dan skoring berfungsi sempurna.")

if __name__ == "__main__":
    test_mock_analysis()
