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
user_states = {}         # chat_id -> dict

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

        # Format output message
        response = (
            f"📊 **HASIL SCANNING {config.MT5_SYMBOL} (Proyeksi 2-3 Jam)**\n"
            f"Harga Saat Ini: **{current_price:.2f}**\n"
            f"Ditemukan **{len(zones)}** zona entry potensial.\n"
            f"----------------------------------------\n\n"
        )
        
        for idx, zone in enumerate(zones):
            emoji = "🟢" if zone.zone_type == "BUY" else "🔴"
            prob_label = "🔥 High Probability" if zone.score >= config.HIGH_PROBABILITY_SCORE else "⚡ Medium Probability"
            
            response += (
                f"{emoji} **SETUP {idx+1}: {zone.zone_type} AREA**\n"
                f"📍 Zona Entry: **{zone.bottom:.2f} - {zone.top:.2f}**\n"
                f"⭐ Skor: **{zone.score:.1f} / 13.0** ({prob_label})\n\n"
                f"💬 *Detail Konfluensi:*\n"
            )
            for detail in zone.details:
                response += f"• {detail}\n"
                
            response += (
                f"\n🛡️ *Proteksi & Target:*\n"
                f"• SL: **{zone.sl:.2f}**\n"
                f"• TP 1: **{zone.tp1:.2f}**\n"
                f"• TP 2: **{zone.tp2:.2f}**\n"
                f"• Status: **PENDING**\n"
                f"----------------------------------------\n\n"
            )
            
        response += (
            "⚠️ _Not Financial Advice._\n"
            "_Edukasi & Sharing Analisa Pribadi._\n"
            "_Do your own research (DYOR)._"
        )
        
        # Update status and send chart
        await status_message.edit_text("📈 *Analisis selesai. Sedang memproses grafik...*", parse_mode="Markdown")
        
        chart_path = "chart.png"
        chart_generated = False
        try:
            generate_candlestick_chart(
                df=analyzer.df_h1,
                zones=zones,
                current_price=current_price,
                pivots=analyzer.pivots,
                symbol=config.MT5_SYMBOL,
                timeframe="H1",
                save_path=chart_path
            )
            chart_generated = True
        except Exception as chart_err:
            logger.error(f"Failed to generate chart: {chart_err}")
            
        # Show Open Position button
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("💼 Open Position", callback_data="btn_open_position")
        ]])

        if chart_generated and os.path.exists(chart_path):
            try:
                # Delete loading status message to keep chat tidy
                await status_message.delete()
            except Exception:
                pass

            try:
                with open(chart_path, 'rb') as photo:
                    if len(response) <= 1024:
                        # Send chart with full text as caption in a single premium message
                        await update.message.reply_photo(
                            photo=photo,
                            caption=response,
                            parse_mode="Markdown",
                            reply_markup=reply_markup
                        )
                    else:
                        # Caption is too long, send photo first and reply with full text
                        photo_msg = await update.message.reply_photo(
                            photo=photo,
                            caption=f"📈 Chart Analisis {config.MT5_SYMBOL} (H1)"
                        )
                        await photo_msg.reply_text(
                            response,
                            parse_mode="Markdown",
                            reply_markup=reply_markup
                        )
            except Exception as send_err:
                logger.error(f"Failed to send chart photo: {send_err}")
                # Fallback to text message
                await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
            finally:
                # Clean up local file
                if os.path.exists(chart_path):
                    os.remove(chart_path)
        else:
            # Fallback if chart failed to generate
            await status_message.edit_text(response, parse_mode="Markdown", reply_markup=reply_markup)


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
    """Handle button callback queries (e.g. Open Position)."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    zones = last_scanned_zones.get(chat_id, [])
    
    if not zones:
        await query.message.reply_text("❌ *Tidak ditemukan data scan terakhir. Silakan jalankan perintah /scan terlebih dahulu.*", parse_mode="Markdown")
        return
        
    if len(zones) == 1:
        # Only 1 zone, execute immediately
        await execute_trade_for_zone(chat_id, zones[0], query.message)
    else:
        # Multiple zones, ask the user to select one
        user_states[chat_id] = {"action": "waiting_for_zone_number"}
        await query.message.reply_text(
            f"🔍 *Ditemukan {len(zones)} area entry potensial.*\n"
            f"Silakan ketik atau balas pesan ini dengan nomor urutan area entry yang ingin Anda buka (contoh: `1` atau `2`):",
            parse_mode="Markdown"
        )

async def handle_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text responses when the user is prompted to select a zone."""
    chat_id = update.effective_chat.id
    state = user_states.get(chat_id)
    
    if not state or state.get("action") != "waiting_for_zone_number":
        # Ignore random messages
        return
        
    zones = last_scanned_zones.get(chat_id, [])
    if not zones:
        user_states.pop(chat_id, None)
        return
        
    text = update.message.text.strip()
    try:
        num = int(text)
        if 1 <= num <= len(zones):
            selected_zone = zones[num - 1]
            # Clear state
            user_states.pop(chat_id, None)
            # Execute
            await execute_trade_for_zone(chat_id, selected_zone, update.message)
        else:
            await update.message.reply_text(
                f"⚠️ *Nomor tidak valid.* Silakan masukkan angka dari `1` hingga `{len(zones)}` sesuai dengan nomor setup di atas:",
                parse_mode="Markdown"
            )
    except ValueError:
        await update.message.reply_text(
            f"⚠️ *Format salah.* Harap ketikkan angka bulat saja (contoh: `1` atau `{len(zones)}`):",
            parse_mode="Markdown"
        )

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
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="^btn_open_position$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_reply))

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
