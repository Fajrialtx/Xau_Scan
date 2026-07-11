import pandas as pd
import numpy as np
import pytz
from datetime import datetime, time
import logging
import config

logger = logging.getLogger(__name__)

class TradingZone:
    def __init__(self, zone_type: str, top: float, bottom: float, timeframe: str, decimals: int = 2):
        self.zone_type = zone_type  # "BUY" or "SELL"
        self.decimals = decimals
        self.top = round(top, decimals)
        self.bottom = round(bottom, decimals)
        self.timeframe = timeframe
        self.score = 0.0
        self.details = []
        self.sl = 0.0
        self.tp1 = 0.0
        self.tp2 = 0.0

    def to_dict(self):
        return {
            "type": self.zone_type,
            "top": self.top,
            "bottom": self.bottom,
            "timeframe": self.timeframe,
            "score": round(self.score, 2),
            "details": self.details,
            "sl": round(self.sl, self.decimals),
            "tp1": round(self.tp1, self.decimals),
            "tp2": round(self.tp2, self.decimals)
        }

class XAUAnalyzer:
    def __init__(self, data_provider):
        self.dp = data_provider
        self.tz = pytz.timezone(config.TIMEZONE_STR)
        self.params = self.get_symbol_params(self.dp.symbol)

    def get_symbol_params(self, symbol: str) -> dict:
        sym = symbol.upper()
        if "XAU" in sym or "GOLD" in sym:
            return {
                "impulsive_threshold": 5.0,
                "zone_limit_range": 30.0,
                "buffer": 3.5,
                "decimals": 2
            }
        elif "EUR" in sym:
            return {
                "impulsive_threshold": 0.0015,
                "zone_limit_range": 0.0150,
                "buffer": 0.0010,
                "decimals": 5
            }
        elif "GBP" in sym:
            return {
                "impulsive_threshold": 0.0020,
                "zone_limit_range": 0.0200,
                "buffer": 0.0012,
                "decimals": 5
            }
        elif "JPY" in sym:
            return {
                "impulsive_threshold": 0.25,
                "zone_limit_range": 2.50,
                "buffer": 0.15,
                "decimals": 3
            }
        elif "BTC" in sym:
            return {
                "impulsive_threshold": 150.0,
                "zone_limit_range": 1500.0,
                "buffer": 100.0,
                "decimals": 2
            }
        else:
            return {
                "impulsive_threshold": 5.0,
                "zone_limit_range": 30.0,
                "buffer": 3.5,
                "decimals": 2
            }


    def calculate_ema(self, df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return df['close'].ewm(span=period, adjust=False).mean()

    def get_swings(self, df: pd.DataFrame, window: int = 5):
        """Identify swing highs and swing lows."""
        highs = []
        lows = []
        for i in range(window, len(df) - window):
            # Check swing high
            is_high = True
            for w in range(1, window + 1):
                if df['high'].iloc[i] <= df['high'].iloc[i - w] or df['high'].iloc[i] <= df['high'].iloc[i + w]:
                    is_high = False
                    break
            if is_high:
                highs.append((df['time'].iloc[i], df['high'].iloc[i], i))

            # Check swing low
            is_low = True
            for w in range(1, window + 1):
                if df['low'].iloc[i] >= df['low'].iloc[i - w] or df['low'].iloc[i] >= df['low'].iloc[i + w]:
                    is_low = False
                    break
            if is_low:
                lows.append((df['time'].iloc[i], df['low'].iloc[i], i))
                
        return highs, lows

    def detect_order_blocks(self, df: pd.DataFrame, timeframe: str):
        """
        Detect fresh (unmitigated) Order Blocks.
        Bullish OB: Last bearish candle before a strong bullish impulsive move.
        Bearish OB: Last bullish candle before a strong bearish impulsive move.
        """
        obs = []
        n = len(df)
        if n < 10:
            return obs

        # Threshold for strong impulsive move (in points/pips)
        impulsive_threshold = self.params["impulsive_threshold"]
        decimals = self.params["decimals"]

        for i in range(2, n - 4):
            # Bullish OB Check
            # 1. Candle i is bearish
            is_bearish = df['close'].iloc[i] < df['open'].iloc[i]
            if is_bearish:
                # 2. Strong bullish move in the next 3 candles
                price_change = df['close'].iloc[i+3] - df['high'].iloc[i]
                if price_change >= impulsive_threshold:
                    ob_top = df['high'].iloc[i]
                    ob_bottom = df['low'].iloc[i]
                    
                    # 3. Check if it's unmitigated (fresh) from i+4 to latest candle
                    mitigated = False
                    for j in range(i + 4, n):
                        if df['low'].iloc[j] <= ob_top:
                            mitigated = True
                            break
                    
                    if not mitigated:
                        obs.append(TradingZone("BUY", ob_top, ob_bottom, timeframe, decimals))

            # Bearish OB Check
            # 1. Candle i is bullish
            is_bullish = df['close'].iloc[i] > df['open'].iloc[i]
            if is_bullish:
                # 2. Strong bearish move in the next 3 candles
                price_change = df['low'].iloc[i] - df['close'].iloc[i+3]
                if price_change >= impulsive_threshold:
                    ob_top = df['high'].iloc[i]
                    ob_bottom = df['low'].iloc[i]
                    
                    # 3. Check if it's unmitigated from i+4 to latest candle
                    mitigated = False
                    for j in range(i + 4, n):
                        if df['high'].iloc[j] >= ob_bottom:
                            mitigated = True
                            break
                            
                    if not mitigated:
                        obs.append(TradingZone("SELL", ob_top, ob_bottom, timeframe, decimals))
                        
        return obs


    def detect_fvgs(self, df: pd.DataFrame, timeframe: str):
        """
        Detect fresh (unmitigated) Fair Value Gaps (FVG).
        Bullish FVG: Low of candle i > High of candle i-2 (where candle i-1 is large bullish)
        Bearish FVG: High of candle i < Low of candle i-2 (where candle i-1 is large bearish)
        """
        fvgs = []
        n = len(df)
        if n < 5:
            return fvgs

        decimals = self.params["decimals"]

        for i in range(2, n):
            # Bullish FVG
            if df['close'].iloc[i-1] > df['open'].iloc[i-1]:  # Candle i-1 is bullish
                fvg_bottom = df['high'].iloc[i-2]
                fvg_top = df['low'].iloc[i]
                if fvg_top > fvg_bottom:
                    # Check if unmitigated
                    mitigated = False
                    for j in range(i + 1, n):
                        if df['low'].iloc[j] <= fvg_bottom:
                            mitigated = True
                            break
                    if not mitigated:
                        fvgs.append(TradingZone("BUY", fvg_top, fvg_bottom, timeframe, decimals))

            # Bearish FVG
            if df['close'].iloc[i-1] < df['open'].iloc[i-1]:  # Candle i-1 is bearish
                fvg_top = df['low'].iloc[i-2]
                fvg_bottom = df['high'].iloc[i]
                if fvg_top > fvg_bottom:
                    # Check if unmitigated
                    mitigated = False
                    for j in range(i + 1, n):
                        if df['high'].iloc[j] >= fvg_top:
                            mitigated = True
                            break
                    if not mitigated:
                        fvgs.append(TradingZone("SELL", fvg_top, fvg_bottom, timeframe, decimals))

        return fvgs


    def get_asia_session_range(self, df_m15: pd.DataFrame):
        """
        Find highest high and lowest low of Asia session.
        Time: 07:00 to 15:00 WIB (Jakarta Time).
        """
        # Convert df timestamps to Jakarta timezone
        df = df_m15.copy()
        df['time_local'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(self.tz)
        
        # Filter all historical bars that fall into the Asia session hour range
        asia_hours_df = df[
            (df['time_local'].dt.hour >= config.ASIA_START_HOUR) & 
            (df['time_local'].dt.hour < config.ASIA_END_HOUR)
        ]
        
        if len(asia_hours_df) > 0:
            # Get the latest date that actually has Asia session data
            last_asia_date = asia_hours_df['time_local'].dt.date.max()
            asia_df = asia_hours_df[asia_hours_df['time_local'].dt.date == last_asia_date]
            
            asia_high = asia_df['high'].max()
            asia_low = asia_df['low'].min()
            return asia_high, asia_low
            
        return None, None

    def check_choch_bos(self, df_m15: pd.DataFrame, zone_type: str) -> bool:
        """
        Check if there's a recent Market Structure Shift / CHoCH or BOS on M15.
        For BUY: latest Close breaks above the recent swing high (CHoCH / BOS).
        For SELL: latest Close breaks below the recent swing low.
        """
        if len(df_m15) < 30:
            return False

        highs, lows = self.get_swings(df_m15, window=5)
        if not highs or not lows:
            return False

        latest_close = df_m15['close'].iloc[-1]
        
        # Look at the last 2 swing highs/lows
        if zone_type == "BUY":
            # Bullish CHoCH: price breaks recent swing high
            recent_swing_high = highs[-1][1] if len(highs) > 0 else float('inf')
            if latest_close > recent_swing_high:
                return True
        else:
            # Bearish CHoCH: price breaks recent swing low
            recent_swing_low = lows[-1][1] if len(lows) > 0 else float('-inf')
            if latest_close < recent_swing_low:
                return True

        return False

    def calculate_pivot_points(self, df_d1: pd.DataFrame):
        """Calculate daily pivot points based on yesterday's daily candle."""
        if len(df_d1) < 2:
            return None
            
        # Yesterday's candle is the second to last index (-2) because -1 is the current unclosed day
        yesterday = df_d1.iloc[-2]
        h, l, c = yesterday['high'], yesterday['low'], yesterday['close']
        
        pp = (h + l + c) / 3.0
        r1 = (2.0 * pp) - l
        s1 = (2.0 * pp) - h
        r2 = pp + (h - l)
        s2 = pp - (h - l)
        
        return {
            "PP": pp,
            "R1": r1,
            "S1": s1,
            "R2": r2,
            "S2": s2
        }

    def calculate_vwap_today(self, df_m15: pd.DataFrame) -> float:
        """Calculate simple intraday VWAP for today's bars."""
        df = df_m15.copy()
        df['time_local'] = df['time'].dt.tz_localize('UTC').dt.tz_convert(self.tz)
        today = datetime.now(self.tz).date()
        
        today_df = df[df['time_local'].dt.date == today]
        if len(today_df) == 0:
            today_df = df.tail(24) # Fallback to last 24 bars
            
        tp = (today_df['high'] + today_df['low'] + today_df['close']) / 3.0
        vol = today_df['tick_volume']
        
        if vol.sum() == 0:
            return df['close'].iloc[-1]
            
        vwap = (tp * vol).sum() / vol.sum()
        return vwap

    def analyze(self) -> list:
        """Run the multi-timeframe scoring analysis and return valid entry zones."""
        # 1. Fetch historical rates for H4, H1, M30, M15, Daily
        df_h4 = self.dp.fetch_rates("H4", 300)
        df_h1 = self.dp.fetch_rates("H1", 300)
        self.df_h1 = df_h1
        df_m30 = self.dp.fetch_rates("M30", 300)
        df_m15 = self.dp.fetch_rates("M15", 300)
        df_d1 = self.dp.fetch_rates("D1", 10)
        
        current_price = self.dp.get_current_price()
        
        # Calculate EMA for trend filters
        df_h4['ema_200'] = self.calculate_ema(df_h4, config.EMA_SLOW)
        df_h1['ema_50'] = self.calculate_ema(df_h1, config.EMA_FAST)
        df_h1['ema_200'] = self.calculate_ema(df_h1, config.EMA_SLOW)
        df_m15['ema_50'] = self.calculate_ema(df_m15, config.EMA_FAST)
        
        # Get latest EMA values
        h4_ema200 = df_h4['ema_200'].iloc[-1]
        h1_ema50 = df_h1['ema_50'].iloc[-1]
        h1_ema200 = df_h1['ema_200'].iloc[-1]
        m15_ema50 = df_m15['ema_50'].iloc[-1]
        
        # Fetch pivot levels & VWAP
        pivots = self.calculate_pivot_points(df_d1)
        self.pivots = pivots
        vwap = self.calculate_vwap_today(df_m15)
        
        # Fetch Asia Session range
        asia_high, asia_low = self.get_asia_session_range(df_m15)
        
        # Detect Swing High/Low for Fibonacci on H1 and M30
        h1_highs, h1_lows = self.get_swings(df_h1, window=10)
        m30_highs, m30_lows = self.get_swings(df_m30, window=10)
        
        # Find latest H1/M30 swing high and low to draw Fibonacci
        swing_high = None
        swing_low = None
        if len(h1_highs) > 0 and len(h1_lows) > 0:
            # Get latest swing high and low
            swing_high = h1_highs[-1][1]
            swing_low = h1_lows[-1][1]
        elif len(m30_highs) > 0 and len(m30_lows) > 0:
            swing_high = m30_highs[-1][1]
            swing_low = m30_lows[-1][1]

        # 2. Scan H1 & H4 for Order Blocks (Core Zones)
        h1_obs = self.detect_order_blocks(df_h1, "H1")
        h4_obs = self.detect_order_blocks(df_h4, "H4")
        all_obs = h1_obs + h4_obs
        
        # Detect FVGs on H1 & H4
        h1_fvgs = self.detect_fvgs(df_h1, "H1")
        h4_fvgs = self.detect_fvgs(df_h4, "H4")
        all_fvgs = h1_fvgs + h4_fvgs
        
        valid_zones = []
        
        # We only consider zones within range of current price to be realistic
        zone_limit_range = self.params["zone_limit_range"]
        fvg_overlap_tol = 0.6 * self.params["buffer"]
        fib_tol = 0.3 * self.params["buffer"]
        pivot_tol = 0.4 * self.params["buffer"]
        
        for zone in all_obs:
            # Filter by distance
            if zone.zone_type == "BUY" and zone.top > current_price:
                continue  # Buy zone must be below current price
            if zone.zone_type == "SELL" and zone.bottom < current_price:
                continue  # Sell zone must be above current price
                
            distance = abs(current_price - (zone.top + zone.bottom) / 2.0)
            if distance > zone_limit_range:
                continue

            # --- PILAR 1: Penentu Area Inti ---
            # OB is core: starts with +3 points
            zone.score = 3.0
            zone.details.append(f"Fresh {zone.timeframe} Order Block (+3.0)")
            
            # Check for overlapping FVG (+2 or +5 combo)
            has_overlapping_fvg = False
            for fvg in all_fvgs:
                if fvg.zone_type == zone.zone_type and fvg.timeframe == zone.timeframe:
                    # Check overlap: if FVG top/bottom is close to OB top/bottom
                    # Bullish overlap: FVG bottom is near OB top
                    if zone.zone_type == "BUY":
                        if abs(fvg.bottom - zone.top) <= fvg_overlap_tol or (fvg.bottom <= zone.top and fvg.top >= zone.bottom):
                            has_overlapping_fvg = True
                            break
                    # Bearish overlap: FVG top is near OB bottom
                    elif zone.zone_type == "SELL":
                        if abs(fvg.top - zone.bottom) <= fvg_overlap_tol or (fvg.top >= zone.bottom and fvg.bottom <= zone.top):
                            has_overlapping_fvg = True
                            break
            
            if has_overlapping_fvg:
                # Add +2 points for FVG, making it +5.0 combo total
                zone.score += 2.0
                zone.details.append("Fair Value Gap (FVG) Confluence (+2.0)")
            
            # --- PILAR 2: Konfluensi ---
            # Fibonacci Retracement
            if swing_high and swing_low and swing_high > swing_low:
                fib_range = swing_high - swing_low
                if zone.zone_type == "BUY":
                    # Pull Fibonacci Low to High (for uptrend buy entries)
                    fib_618 = swing_high - 0.618 * fib_range
                    fib_786 = swing_high - 0.786 * fib_range
                    
                    # Check if fib levels lie inside or close to the OB zone
                    if (zone.bottom - fib_tol <= fib_618 <= zone.top + fib_tol) or (zone.bottom - fib_tol <= fib_786 <= zone.top + fib_tol):
                        zone.score += 2.0
                        zone.details.append("Fibonacci Retracement (61.8% / 78.6%) overlap (+2.0)")
                else:
                    # Pull Fibonacci High to Low (for downtrend sell entries)
                    fib_618 = swing_low + 0.618 * fib_range
                    fib_786 = swing_low + 0.786 * fib_range
                    
                    if (zone.bottom - fib_tol <= fib_618 <= zone.top + fib_tol) or (zone.bottom - fib_tol <= fib_786 <= zone.top + fib_tol):
                        zone.score += 2.0
                        zone.details.append("Fibonacci Retracement (61.8% / 78.6%) overlap (+2.0)")
            
            # Pivot Points & VWAP
            near_pivot_or_vwap = False
            if pivots:
                # Check proximity to daily PP, S1 (for BUY), R1 (for SELL)
                target_pivot = pivots["S1"] if zone.zone_type == "BUY" else pivots["R1"]
                if abs((zone.top + zone.bottom)/2.0 - pivots["PP"]) <= pivot_tol or abs((zone.top + zone.bottom)/2.0 - target_pivot) <= pivot_tol:
                    near_pivot_or_vwap = True
            
            if vwap:
                if abs((zone.top + zone.bottom)/2.0 - vwap) <= pivot_tol:
                    near_pivot_or_vwap = True
                    
            if near_pivot_or_vwap:
                zone.score += 1.0
                zone.details.append("Daily Pivot or VWAP proximity (+1.0)")
                
            # --- PILAR 3: Keselarasan Tren MTF ---
            if zone.zone_type == "BUY":
                if current_price > h4_ema200:
                    zone.score += 1.0
                    zone.details.append("H4 Trend Bullish (Price > EMA 200) (+1.0)")
                if current_price > h1_ema50:
                    zone.score += 1.0
                    zone.details.append("H1 Trend Bullish (Price > EMA 50) (+1.0)")
                if current_price > m15_ema50:
                    zone.score += 0.5
                    zone.details.append("M15 Trend Bullish (Price > EMA 50) (+0.5)")
            else:
                if current_price < h4_ema200:
                    zone.score += 1.0
                    zone.details.append("H4 Trend Bearish (Price < EMA 200) (+1.0)")
                if current_price < h1_ema50:
                    zone.score += 1.0
                    zone.details.append("H1 Trend Bearish (Price < EMA 50) (+1.0)")
                if current_price < m15_ema50:
                    zone.score += 0.5
                    zone.details.append("M15 Trend Bearish (Price < EMA 50) (+0.5)")
                    
            # --- PILAR 4: Konteks Sesi & Likuiditas ---
            # Asia Session Sweep
            is_asia_sweep = False
            if zone.zone_type == "BUY" and asia_low:
                # Buy zone is slightly below Asia Low (liquidity hunt)
                if zone.top <= asia_low and (asia_low - zone.top) <= self.params["buffer"]:
                    is_asia_sweep = True
            elif zone.zone_type == "SELL" and asia_high:
                # Sell zone is slightly above Asia High
                if zone.bottom >= asia_high and (zone.bottom - asia_high) <= self.params["buffer"]:
                    is_asia_sweep = True
                    
            if is_asia_sweep:
                zone.score += 1.5
                zone.details.append("Asia Session Liquidity Sweep Zone (+1.5)")
                
            # CHoCH/BOS check on M15
            if self.check_choch_bos(df_m15, zone.zone_type):
                zone.score += 2.0
                zone.details.append("M15 CHoCH/BOS Market Structure Shift (+2.0)")

            # Check if zone meets minimum score threshold
            if zone.score >= config.MIN_SCORE_SHOW:
                # Calculate SL & TP
                buffer = self.params["buffer"]
                if zone.zone_type == "BUY":
                    zone.sl = zone.bottom - buffer
                    risk = zone.top - zone.sl
                    zone.tp1 = zone.top + 1.5 * risk
                    zone.tp2 = zone.top + 3.0 * risk
                else:
                    zone.sl = zone.top + buffer
                    risk = zone.sl - zone.bottom
                    zone.tp1 = zone.bottom - 1.5 * risk
                    zone.tp2 = zone.bottom - 3.0 * risk
                    
                valid_zones.append(zone)


        # Sort zones by score descending
        valid_zones.sort(key=lambda z: z.score, reverse=True)
        return valid_zones
