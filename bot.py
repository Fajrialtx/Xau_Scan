import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import config
from data_provider import MT5DataProvider
from analyzer import XAUAnalyzer
from chart_generator import generate_candlestick_chart

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# In-memory storage for scan state
last_scanned_zones = {}  # chat_id -> list of TradingZone


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    welcome_msg = (
        "👋 <b>Halo! Selamat datang di Bot Analisis MT5 Multi-Pair</b>\n\n"
        "Saya adalah bot personal asisten trading Anda. Saya terhubung ke terminal MT5 Anda "
        "untuk menganalisis area entry ideal berdasarkan Smart Money Concepts (OB, FVG) "
        "dan konfluensi teknikal.\n\n"
        "<b>Perintah Tersedia:</b>\n"
        "🔍 /scan_xau - Pemindaian Emas (XAU/USD)\n"
        "🔍 /scan_eur - Pemindaian EUR/USD\n"
        "🔍 /scan_gbp - Pemindaian GBP/USD\n"
        "🔍 /scan_jpy - Pemindaian USD/JPY\n"
        "🔍 /scan_btc - Pemindaian BTC/USD"
    )
    await update.message.reply_text(welcome_msg, parse_mode="HTML")


async def execute_scan_for_pair(update: Update, context: ContextTypes.DEFAULT_TYPE, pair_key: str):
    symbol = config.SUPPORTED_PAIRS.get(pair_key)
    if not symbol:
        await update.message.reply_text("❌ *Pair tidak didukung.*", parse_mode="Markdown")
        return
        
    status_message = await update.message.reply_text(
        f"🔍 *Memulai pemindaian pasar {symbol}... Mohon tunggu.*", 
        parse_mode="Markdown"
    )
    
    dp = MT5DataProvider(symbol=symbol)
    try:
        # Connect to MT5
        connected = dp.connect()
        if not connected:
            await status_message.edit_text(
                "❌ **Gagal Terhubung ke MT5!**\n\n"
                "Pastikan aplikasi MetaTrader 5 Anda sudah terbuka dan berjalan di komputer Anda.",
                parse_mode="Markdown"
            )
            return

        # Fetch current price
        current_price = dp.get_current_price()
        
        # Analyze
        analyzer = XAUAnalyzer(dp)
        zones = analyzer.analyze()
        
        # Get dynamic format string
        decimals = analyzer.params["decimals"]
        f_str = f"{{:.{decimals}f}}"
        
        # Store scanned zones nested under symbol
        if update.effective_chat.id not in last_scanned_zones:
            last_scanned_zones[update.effective_chat.id] = {}
        last_scanned_zones[update.effective_chat.id][symbol] = zones
        
        # Disconnect after fetching/analyzing to be clean
        dp.disconnect()
        
        if not zones:
            await status_message.edit_text(
                f"📊 **HASIL SCANNING {symbol}**\n"
                f"Harga Saat Ini: **{f_str.format(current_price)}**\n\n"
                "⚠️ *Tidak ditemukan area entry yang ideal saat ini yang memenuhi batas minimum skor.*",
                parse_mode="Markdown"
            )
            return

        # Update status message
        await status_message.edit_text(
            f"📊 **HASIL SCANNING {symbol} (Proyeksi 2-3 Jam)**\n"
            f"Harga Saat Ini: **{f_str.format(current_price)}**\n"
            f"Ditemukan **{len(zones)}** zona entry potensial. Mengirim grafik per area...",
            parse_mode="Markdown"
        )
        
        for idx, zone in enumerate(zones):
            # Format report text for this specific zone
            emoji = "🟢" if zone.zone_type == "BUY" else "🔴"
            prob_label = "🔥 High Probability" if zone.score >= config.HIGH_PROBABILITY_SCORE else "⚡ Medium Probability"
            
            zone_text = (
                f"📊 **HASIL SCANNING {symbol}**\n"
                f"Harga Saat Ini: **{f_str.format(current_price)}**\n"
                f"----------------------------------------\n\n"
                f"{emoji} **SETUP {idx+1}: {zone.zone_type} AREA**\n"
                f"📍 Zona Entry: **{f_str.format(zone.bottom)} - {f_str.format(zone.top)}**\n"
                f"⭐ Skor: **{zone.score:.1f} / 13.0** ({prob_label})\n\n"
                f"💬 *Detail Konfluensi:*\n"
            )
            for detail in zone.details:
                zone_text += f"• {detail}\n"
                
            zone_text += (
                f"\n🛡️ *Proteksi & Target:*\n"
                f"• SL: **{f_str.format(zone.sl)}**\n"
                f"• TP 1: **{f_str.format(zone.tp1)}**\n"
                f"• TP 2: **{f_str.format(zone.tp2)}**\n"
                f"• Status: **PENDING**\n"
                f"----------------------------------------\n\n"
                f"⚠️ _Not Financial Advice. DYOR._"
            )

            
            # Setup specific button for this zone, encoding symbol name in callback_data
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"💼 Open Setup {idx+1}", callback_data=f"place_order_{symbol}_{idx}")
            ]])
            
            chart_path = f"chart_{pair_key}_{idx}.png"
            chart_generated = False
            try:
                # Generate chart containing only this single zone
                generate_candlestick_chart(
                    df=analyzer.df_h1,
                    zones=[zone],
                    current_price=current_price,
                    pivots=analyzer.pivots,
                    symbol=symbol,
                    timeframe="H1",
                    save_path=chart_path,
                    decimals=decimals
                )
                chart_generated = True
            except Exception as chart_err:
                logger.error(f"Failed to generate chart for {symbol} zone {idx+1}: {chart_err}")
                
            if chart_generated and os.path.exists(chart_path):
                try:
                    with open(chart_path, 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=zone_text,
                            parse_mode="Markdown",
                            reply_markup=reply_markup
                        )
                except Exception as send_err:
                    logger.error(f"Failed to send {symbol} zone {idx+1} photo: {send_err}")
                    await update.message.reply_text(zone_text, parse_mode="Markdown", reply_markup=reply_markup)
                finally:
                    if os.path.exists(chart_path):
                        os.remove(chart_path)
            else:
                await update.message.reply_text(zone_text, parse_mode="Markdown", reply_markup=reply_markup)
                
        # Update loading message to complete summary
        try:
            await status_message.edit_text(
                f"✅ **Scanning {symbol} Selesai.**\n"
                f"Ditemukan **{len(zones)}** area entry potensial. Silakan periksa detail grafik dan pasang posisi menggunakan tombol di atas.",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Error during scan of {symbol}")
        dp.disconnect()
        await status_message.edit_text(
            f"❌ **Terjadi Kesalahan saat Pemindaian {symbol}!**\n\n"
            f"Error: `{str(e)}`\n"
            f"Pastikan MT5 Anda sudah login ke akun broker dan memiliki chart data {symbol}.",
            parse_mode="Markdown"
        )

# Command-specific callbacks
async def scan_xau(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await execute_scan_for_pair(update, context, "xau")

async def scan_eur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await execute_scan_for_pair(update, context, "eur")

async def scan_gbp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await execute_scan_for_pair(update, context, "gbp")

async def scan_jpy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await execute_scan_for_pair(update, context, "jpy")

async def scan_btc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await execute_scan_for_pair(update, context, "btc")

async def execute_trade_for_zone(chat_id: int, symbol: str, zone, message_object):
    """Connect to MT5 and execute a pending limit order for a given zone."""
    status_msg = await message_object.reply_text(
        f"⏳ *Mengirim order pending {zone.zone_type} Limit {symbol} ke MT5...*",
        parse_mode="Markdown"
    )
    
    # Determine entry price
    entry_price = zone.top if zone.zone_type == "BUY" else zone.bottom
    
    decimals = zone.decimals
    f_str = f"{{:.{decimals}f}}"
    
    dp = MT5DataProvider(symbol=symbol)
    try:
        success, msg = dp.place_limit_order(
            order_type=zone.zone_type,
            price=entry_price,
            sl=zone.sl,
            tp=zone.tp1,
            volume=config.DEFAULT_LOT
        )
        
        emoji = "✅" if success else "❌"
        result_text = (
            f"{emoji} **STATUS EKSEKUSI PENDING ORDER**\n"
            f"----------------------------------------\n"
            f"• Simbol: **{symbol}**\n"
            f"• Tipe: **{zone.zone_type} LIMIT**\n"
            f"• Volume: **{config.DEFAULT_LOT} Lot**\n"
            f"• Price: **{f_str.format(entry_price)}**\n"
            f"• SL: **{f_str.format(zone.sl)}**\n"
            f"• TP: **{f_str.format(zone.tp1)}**\n\n"
            f"💬 *Respon:* {msg}"
        )
        await status_msg.edit_text(result_text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error executing limit order")
        await status_msg.edit_text(f"❌ **Gagal mengeksekusi order!**\nError: `{str(e)}`", parse_mode="Markdown")
    finally:
        dp.disconnect()


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callback queries (e.g. place_order_EURUSDm_0)."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    data = query.data
    
    if data.startswith("place_order_"):
        try:
            parts = data.split("_")
            idx = int(parts[-1])
            symbol = "_".join(parts[2:-1])
            
            # Retrieve zones from storage
            symbol_zones = last_scanned_zones.get(chat_id, {}).get(symbol, [])
            if not symbol_zones or idx < 0 or idx >= len(symbol_zones):
                await query.message.reply_text("❌ *Data scan sudah kedaluwarsa atau tidak valid. Silakan jalankan scan kembali.*", parse_mode="Markdown")
                return
                
            selected_zone = symbol_zones[idx]
            await execute_trade_for_zone(chat_id, symbol, selected_zone, query.message)
        except Exception as e:
            logger.error(f"Error parsing callback data: {e}")
            await query.message.reply_text("❌ *Gagal memproses eksekusi order.*", parse_mode="Markdown")

async def post_init(application: Application) -> None:
    """Register bot commands list dynamically on Telegram servers."""
    commands = [
        BotCommand("start", "Menyapa bot & menampilkan petunjuk awal"),
        BotCommand("scan_xau", "Scan grafik XAU/USD (Emas)"),
        BotCommand("scan_eur", "Scan grafik EUR/USD (Euro)"),
        BotCommand("scan_gbp", "Scan grafik GBP/USD (Pound)"),
        BotCommand("scan_jpy", "Scan grafik USD/JPY (Yen)"),
        BotCommand("scan_btc", "Scan grafik BTC/USD (Bitcoin)")
    ]
    await application.bot.set_my_commands(commands)

def main():
    # Verify token
    if config.TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not config.TELEGRAM_TOKEN:
        print("❌ ERROR: Anda belum mengisi TELEGRAM_TOKEN di file .env!")
        print("Silakan buka file .env dan ganti 'YOUR_TELEGRAM_BOT_TOKEN' dengan token asli dari BotFather.")
        return

    print("🤖 Memulai personal MT5 Multi-Pair Telegram Bot...")
    print("Tekan Ctrl+C untuk menghentikan bot.")

    # Create application with post_init commands registration
    application = Application.builder().token(config.TELEGRAM_TOKEN).post_init(post_init).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("scan_xau", scan_xau))
    application.add_handler(CommandHandler("scan_eur", scan_eur))
    application.add_handler(CommandHandler("scan_gbp", scan_gbp))
    application.add_handler(CommandHandler("scan_jpy", scan_jpy))
    application.add_handler(CommandHandler("scan_btc", scan_btc))
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^place_order_.*_\\d+$"))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()

