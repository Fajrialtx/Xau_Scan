import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        "👋 **Halo! Selamat datang di Bot Analisis XAU/USD**\n\n"
        "Saya adalah bot personal asisten trading Anda. Saya terhubung ke terminal MT5 Anda "
        "untuk menganalisis area entry ideal berdasarkan Smart Money Concepts (OB, FVG) "
        "dan konfluensi teknikal.\n\n"
        "**Perintah Tersedia:**\n"
        "🔍 /scan - Memulai pemindaian pergerakan XAU/USD saat ini."
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /scan command."""
    status_message = await update.message.reply_text("🔍 *Memulai pemindaian pasar XAU/USD... Mohon tunggu.*", parse_mode="Markdown")
    
    dp = MT5DataProvider()
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
        
        # Store scanned zones for potential execution
        last_scanned_zones[update.effective_chat.id] = zones
        
        # Disconnect after fetching/analyzing to be clean
        dp.disconnect()
        
        if not zones:
            await status_message.edit_text(
                f"📊 **HASIL SCANNING {config.MT5_SYMBOL}**\n"
                f"Harga Saat Ini: **{current_price:.2f}**\n\n"
                "⚠️ *Tidak ditemukan area entry yang ideal saat ini yang memenuhi batas minimum skor.*",
                parse_mode="Markdown"
            )
            return

        # Update status message
        await status_message.edit_text(
            f"📊 **HASIL SCANNING {config.MT5_SYMBOL} (Proyeksi 2-3 Jam)**\n"
            f"Harga Saat Ini: **{current_price:.2f}**\n"
            f"Ditemukan **{len(zones)}** zona entry potensial. Mengirim grafik per area...",
            parse_mode="Markdown"
        )
        
        for idx, zone in enumerate(zones):
            # Format report text for this specific zone
            emoji = "🟢" if zone.zone_type == "BUY" else "🔴"
            prob_label = "🔥 High Probability" if zone.score >= config.HIGH_PROBABILITY_SCORE else "⚡ Medium Probability"
            
            zone_text = (
                f"📊 **HASIL SCANNING {config.MT5_SYMBOL}**\n"
                f"Harga Saat Ini: **{current_price:.2f}**\n"
                f"----------------------------------------\n\n"
                f"{emoji} **SETUP {idx+1}: {zone.zone_type} AREA**\n"
                f"📍 Zona Entry: **{zone.bottom:.2f} - {zone.top:.2f}**\n"
                f"⭐ Skor: **{zone.score:.1f} / 13.0** ({prob_label})\n\n"
                f"💬 *Detail Konfluensi:*\n"
            )
            for detail in zone.details:
                zone_text += f"• {detail}\n"
                
            zone_text += (
                f"\n🛡️ *Proteksi & Target:*\n"
                f"• SL: **{zone.sl:.2f}**\n"
                f"• TP 1: **{zone.tp1:.2f}**\n"
                f"• TP 2: **{zone.tp2:.2f}**\n"
                f"• Status: **PENDING**\n"
                f"----------------------------------------\n\n"
                f"⚠️ _Not Financial Advice. DYOR._"
            )
            
            # Setup specific button for this zone
            reply_markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"💼 Open Setup {idx+1}", callback_data=f"place_order_{idx}")
            ]])
            
            chart_path = f"chart_{idx}.png"
            chart_generated = False
            try:
                # Generate chart containing only this single zone
                generate_candlestick_chart(
                    df=analyzer.df_h1,
                    zones=[zone],
                    current_price=current_price,
                    pivots=analyzer.pivots,
                    symbol=config.MT5_SYMBOL,
                    timeframe="H1",
                    save_path=chart_path
                )
                chart_generated = True
            except Exception as chart_err:
                logger.error(f"Failed to generate chart for zone {idx+1}: {chart_err}")
                
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
                    logger.error(f"Failed to send zone {idx+1} photo: {send_err}")
                    await update.message.reply_text(zone_text, parse_mode="Markdown", reply_markup=reply_markup)
                finally:
                    if os.path.exists(chart_path):
                        os.remove(chart_path)
            else:
                await update.message.reply_text(zone_text, parse_mode="Markdown", reply_markup=reply_markup)
                
        # Update loading message to complete summary
        try:
            await status_message.edit_text(
                f"✅ **Scanning Selesai.**\n"
                f"Ditemukan **{len(zones)}** area entry potensial. Silakan periksa detail grafik dan pasang posisi menggunakan tombol di atas.",
                parse_mode="Markdown"
            )
        except Exception:
            pass


    except Exception as e:
        logger.exception("Error during /scan command execution")
        dp.disconnect() # Make sure to close MT5 connection
        await status_message.edit_text(
            f"❌ **Terjadi Kesalahan saat Pemindaian!**\n\n"
            f"Error: `{str(e)}`\n"
            "Pastikan MT5 Anda sudah login ke akun broker dan memiliki chart data XAUUSD.",
            parse_mode="Markdown"
        )

async def execute_trade_for_zone(chat_id: int, zone, message_object):
    """Connect to MT5 and execute a pending limit order for a given zone."""
    status_msg = await message_object.reply_text(
        f"⏳ *Mengirim order pending {zone.zone_type} Limit ke MT5...*",
        parse_mode="Markdown"
    )
    
    # Determine entry price
    entry_price = zone.top if zone.zone_type == "BUY" else zone.bottom
    
    dp = MT5DataProvider()
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
            f"• Simbol: **{config.MT5_SYMBOL}**\n"
            f"• Tipe: **{zone.zone_type} LIMIT**\n"
            f"• Volume: **{config.DEFAULT_LOT} Lot**\n"
            f"• Price: **{entry_price:.2f}**\n"
            f"• SL: **{zone.sl:.2f}**\n"
            f"• TP: **{zone.tp1:.2f}**\n\n"
            f"💬 *Respon:* {msg}"
        )
        await status_msg.edit_text(result_text, parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error executing limit order")
        await status_msg.edit_text(f"❌ **Gagal mengeksekusi order!**\nError: `{str(e)}`", parse_mode="Markdown")
    finally:
        dp.disconnect()

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callback queries (e.g. place_order_0)."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    zones = last_scanned_zones.get(chat_id, [])
    
    if not zones:
        await query.message.reply_text("❌ *Tidak ditemukan data scan terakhir. Silakan jalankan perintah /scan terlebih dahulu.*", parse_mode="Markdown")
        return
        
    data = query.data
    if data.startswith("place_order_"):
        try:
            idx = int(data.split("_")[-1])
            if 0 <= idx < len(zones):
                selected_zone = zones[idx]
                await execute_trade_for_zone(chat_id, selected_zone, query.message)
            else:
                await query.message.reply_text("❌ *Indeks zona tidak valid atau data scan sudah usang.*", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error parsing callback data: {e}")
            await query.message.reply_text("❌ *Gagal memproses eksekusi order.*", parse_mode="Markdown")

def main():
    # Verify token
    if config.TELEGRAM_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN" or not config.TELEGRAM_TOKEN:
        print("❌ ERROR: Anda belum mengisi TELEGRAM_TOKEN di file .env!")
        print("Silakan buka file .env dan ganti 'YOUR_TELEGRAM_BOT_TOKEN' dengan token asli dari BotFather.")
        return

    print("🤖 Memulai personal XAU Telegram Bot...")
    print("Tekan Ctrl+C untuk menghentikan bot.")

    # Create application
    application = Application.builder().token(config.TELEGRAM_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("scan", scan))
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^place_order_\\d+$"))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
