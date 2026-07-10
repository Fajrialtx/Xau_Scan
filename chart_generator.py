import matplotlib
# Use non-interactive Agg backend to run without GUI window
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np
import os
import logging

# Setup logging
logger = logging.getLogger(__name__)


def generate_candlestick_chart(df: pd.DataFrame, zones: list, current_price: float, pivots: dict, symbol: str, timeframe: str = "H1", save_path: str = "chart.png"):
    """
    Generate a beautiful TradingView-style dark-themed candlestick chart.
    Highlights Order Blocks, EMA lines, Pivot Points, and current price.
    """
    # Limit to last 60 candles for clarity
    plot_len = min(60, len(df))
    df_plot = df.tail(plot_len).copy().reset_index(drop=True)

    # Figure setup
    fig, ax = plt.subplots(figsize=(12, 6.5), facecolor='#131722')
    ax.set_facecolor('#131722')

    # Calculate EMA lines for plotting
    # Make sure EMA is calculated on the full df first, then sliced
    if 'ema_50' not in df_plot.columns:
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    if 'ema_200' not in df_plot.columns:
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        
    df_plot = df.tail(plot_len).copy().reset_index(drop=True)

    # Plot Candlesticks
    for i in range(len(df_plot)):
        row = df_plot.iloc[i]
        is_bullish = row['close'] >= row['open']
        color = '#089981' if is_bullish else '#f23645'  # TradingView green & red
        
        # Wick
        ax.plot([i, i], [row['low'], row['high']], color=color, linewidth=1.3)
        
        # Body
        body_bottom = min(row['open'], row['close'])
        body_height = max(abs(row['open'] - row['close']), 0.05) # Min height to show flat candles
        rect = patches.Rectangle(
            (i - 0.3, body_bottom), 0.6, body_height,
            facecolor=color, edgecolor=color, linewidth=1, zorder=3
        )
        ax.add_patch(rect)

    # Plot EMAs
    ax.plot(df_plot['ema_50'], color='#f2994a', label='EMA 50', linewidth=1.2, alpha=0.9, zorder=4)
    ax.plot(df_plot['ema_200'], color='#9b51e0', label='EMA 200', linewidth=1.5, alpha=0.9, zorder=4)

    # Draw current price line
    ax.axhline(current_price, color='#2962ff', linestyle='--', linewidth=1.2, alpha=0.8, zorder=5)
    ax.text(plot_len - 1, current_price, f" Live: {current_price:.2f}", color='#ffffff', 
            bbox=dict(facecolor='#2962ff', alpha=0.8, edgecolor='none', boxstyle='round,pad=0.2'),
            fontsize=8, va='center', zorder=6)

    # Draw Daily Pivot levels if available
    if pivots:
        pivot_colors = {
            "PP": ("#787b86", "Pivot"),
            "S1": ("#089981", "S1 Support"),
            "R1": ("#f23645", "R1 Resistance")
        }
        for key, (color, name) in pivot_colors.items():
            level = pivots.get(key)
            if level and (df_plot['low'].min() * 0.99 <= level <= df_plot['high'].max() * 1.01):
                ax.axhline(level, color=color, linestyle=':', linewidth=1.0, alpha=0.6, zorder=2)
                ax.text(0.5, level, f" {name}: {level:.2f}", color=color, alpha=0.8,
                        fontsize=7.5, va='bottom', ha='left', zorder=2)

    # Highlight entry zones
    for zone in zones:
        # Check if zone is within the chart price range to avoid stretching y-axis
        if not (df_plot['low'].min() * 0.95 <= zone.bottom <= df_plot['high'].max() * 1.05):
            continue
            
        is_buy = zone.zone_type == "BUY"
        zone_color = '#089981' if is_buy else '#f23645'
        label_text = f"Demand/OB Zone (BUY)" if is_buy else f"Supply/OB Zone (SELL)"
        
        # Shade the zone area
        rect = patches.Rectangle(
            (0, zone.bottom), plot_len - 1, zone.top - zone.bottom,
            facecolor=zone_color, alpha=0.12, edgecolor=zone_color, linestyle='--', linewidth=0.8, zorder=1
        )
        ax.add_patch(rect)
        
        # Text label inside the zone
        y_text = (zone.top + zone.bottom) / 2.0
        ax.text(5, y_text, f" {label_text} [{zone.bottom:.1f} - {zone.top:.1f}]", 
                color=zone_color, fontsize=8.5, fontweight='bold', va='center', alpha=0.85, zorder=2)

    # Watermark text (Timeframe & Symbol) in background
    fig.text(0.5, 0.55, f"{symbol}  {timeframe}", color='#2a2e39', fontsize=55, fontweight='bold',
             ha='center', va='center', alpha=0.25, zorder=0)

    # Custom styling
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(True)
    ax.spines['right'].set_color('#2a2e39')
    ax.spines['bottom'].set_color('#2a2e39')
    ax.spines['left'].set_visible(False)
    
    ax.tick_params(axis='x', colors='#787b86', labelsize=9)
    ax.tick_params(axis='y', colors='#787b86', labelsize=9)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    
    ax.grid(True, color='#2a2e39', linestyle=':', linewidth=0.5, alpha=0.5)

    # Set x-ticks to display dates nicely
    x_indices = np.linspace(0, plot_len - 1, 5, dtype=int)
    x_labels = [df_plot['time'].iloc[idx].strftime('%d %b %H:%M') for idx in x_indices]
    ax.set_xticks(x_indices)
    ax.set_xticklabels(x_labels)

    # Labels and Legend
    plt.title(f"XAU/USD Analytical Chart ({timeframe})", color='#ffffff', fontsize=12, pad=15, loc='left', fontweight='bold')
    plt.legend(facecolor='#1e222d', edgecolor='#2a2e39', labelcolor='#ffffff', loc='upper left', fontsize=9)

    # Set tight limits to avoid whitespace
    ax.set_xlim(-1, plot_len)
    
    # Save chart
    plt.tight_layout()
    plt.savefig(save_path, facecolor='#131722', edgecolor='none', dpi=150)
    plt.close()
    
    logger.info(f"Chart generated successfully and saved to {save_path}")
