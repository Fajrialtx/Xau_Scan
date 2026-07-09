import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import config
from data_provider import MT5DataProvider
from analyzer import XAUAnalyzer

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

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
        
        await status_message.edit_text(response, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Error during /scan command execution")
        dp.disconnect() # Make sure to close MT5 connection
        await status_message.edit_text(
            f"❌ **Terjadi Kesalahan saat Pemindaian!**\n\n"
            f"Error: `{str(e)}`\n"
            "Pastikan MT5 Anda sudah login ke akun broker dan memiliki chart data XAUUSD.",
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

    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
