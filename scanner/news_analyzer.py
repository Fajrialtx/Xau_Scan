import os
import logging
from google import genai
import scanner.config as config

logger = logging.getLogger(__name__)

def is_api_key_valid() -> bool:
    """Check if the Gemini API Key is configured and not a placeholder."""
    key = config.GEMINI_API_KEY
    if not key or key == "YOUR_GEMINI_API_KEY" or len(key) < 10:
        return False
    return True

def analyze_news_with_gemini(event: dict, technical_zones_text: str) -> str:
    """
    Use Google Gemini API to analyze an economic news event using 5 professional trading strategies.
    Returns the markdown formatted analysis.
    """
    if not is_api_key_valid():
        return (
            "❌ **API Key Gemini Belum Dikonfigurasi!**\n\n"
            "Untuk menggunakan fitur analisis AI ini, silakan ikuti langkah berikut:\n"
            "1. Buka [Google AI Studio](https://aistudio.google.com/) dan dapatkan API Key secara gratis.\n"
            "2. Buka file `.env` di folder proyek Anda.\n"
            "3. Ubah nilai `GEMINI_API_KEY` dari `YOUR_GEMINI_API_KEY` menjadi API Key asli Anda.\n"
            "4. Mulai ulang bot Telegram Anda."
        )

    # Configure Gemini API Client using the new google-genai SDK
    try:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
    except Exception as init_err:
        logger.error(f"Failed to initialize Gemini API client: {init_err}")
        return f"❌ **Gagal menginisialisasi client AI:** `{str(init_err)}`"

    # Construct the prompt
    prompt = f"""
Anda adalah seorang analis fundamental forex dan komoditas (khususnya Gold/XAU) profesional yang berpengalaman. Tugas Anda adalah menganalisis sebuah berita ekonomi berdampak tinggi (High Impact News) yang akan dirilis hari ini dan memberikan perkiraan dampaknya pada market secara mendalam.

PENTING: Jaga agar seluruh analisis Anda ringkas, padat, dan langsung pada intinya. Total panjang teks analisis Anda WAJIB di bawah 3000 karakter agar muat dikirimkan dalam satu pesan Telegram. Hindari penjelasan yang terlalu panjang atau bertele-tele.

Informasi Berita Ekonomi Hari Ini:
- Negara / Mata Uang: {event.get('country', 'N/A')}
- Judul Berita: {event.get('title', 'N/A')}
- Perkiraan Forecast: {event.get('forecast') if event.get('forecast') else 'Tidak ada data'}
- Data Sebelumnya (Previous): {event.get('previous') if event.get('previous') else 'Tidak ada data'}
- Waktu Rilis Berita: {event.get('time_str', 'N/A')} WIB

Konteks Area Teknikal Saat Ini pada Chart (Smart Money Concepts - SMC):
{technical_zones_text}

Silakan lakukan analisis komprehensif terhadap berita ini menggunakan 5 Strategi Trader Profesional berikut:
1. Indikator Awal (Leading Indicators): Identifikasi dan jelaskan data pendukung/indikator awal yang relevan (seperti ADP/Unemployment Claims untuk NFP, PPI/Core PPI untuk CPI, dsb.) beserta implikasi historisnya.
2. Kebijakan Bank Sentral (Central Bank Bias): Uraikan posisi bank sentral mata uang terkait saat ini (Hawkish vs Dovish Bias) dan bagaimana angka rilis ini akan memperkuat atau memperlemah bias tersebut.
3. Konfluensi SMC / Liquidity Sweep: Hubungkan berita ini dengan area teknikal (Order Block/FVG) yang kami sediakan di atas. Jelaskan potensi manipulasi harga (Judas Swing / Stop Hunt) ke area tersebut saat berita dirilis sebelum bergerak ke arah utama.
4. Revisi Data Sebelumnya (Previous Data Revision): Jelaskan apa pentingnya revisi data bulan lalu jika disandingkan dengan rilis aktual hari ini.
5. Sentimen Pasar & Nada Bicara (Market Sentiment & Tone): Jelaskan sentimen pelaku pasar saat ini dan apa fokus utama yang mereka cari dari berita ini.

Format Output yang Harus Dihasilkan:
Harap berikan respons dalam Bahasa Indonesia yang sangat rapi, informatif, dan terstruktur dengan format Markdown berikut:

---
### 📊 ANALISIS FUNDAMENTAL AI: {event.get('title')} ({event.get('country')})
*(Dianalisis menggunakan 5 Strategi Profesional)*

#### 🔍 Penjelasan & Makna Berita
[Berikan deskripsi singkat tentang apa itu berita ini dan mengapa berita ini penting untuk mata uang terkait dan XAU/USD]

#### 🛠️ Analisis 5 Strategi Trader Profesional:
1. **Leading Indicators:** [Penjelasan]
2. **Central Bank Bias:** [Penjelasan]
3. **SMC & Liquidity Sweep Confluence:** [Penjelasan detail menghubungkan area OB/FVG di atas dengan potensi stop hunt saat rilis berita]
4. **Previous Revision Importance:** [Penjelasan]
5. **Market Sentiment & Tone:** [Penjelasan]

#### 🔮 Perkiraan Hasil & Kemungkinan Probabilitas:
*   **Bullish USD / Bearish XAU:** `[X]%` (Alasan singkat)
*   **Bearish USD / Bullish XAU:** `[Y]%` (Alasan singkat)
*   **Neutral / Konsolidasi (Whipsaw):** `[Z]%` (Alasan singkat)
*(Catatan: Total X + Y + Z harus 100%)*

#### 💡 Alasan Utama & Kesimpulan:
[Berikan kesimpulan akhir yang tajam dan panduan tindakan bagi trader saat berita rilis]
---
"""

    try:
        logger.info(f"Sending news analysis prompt to Gemini for event: {event.get('title')}")
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt
        )
        return response.text
    except Exception as api_err:
        logger.error(f"Gemini API generation failed: {api_err}")
        return (
            f"❌ **Gagal menghasilkan analisis menggunakan Gemini API.**\n\n"
            f"**Detail Error:** `{str(api_err)}`\n\n"
            f"Pastikan koneksi internet Anda lancar dan API Key yang Anda masukkan valid."
        )

if __name__ == "__main__":
    # Test news analyzer directly
    import sys
    # Avoid UnicodeEncodeError on Windows command line when printing emojis
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(level=logging.INFO)
    
    print("Testing scanner/news_analyzer.py...")
    test_event = {
        "title": "Core CPI m/m",
        "country": "USD",
        "forecast": "0.2%",
        "previous": "0.3%",
        "time_str": "19:30"
    }
    test_zones = "- Setup 1: BUY di area 2315.00 - 2318.50 (Score: 9.5/13.0)\n  • Fresh H1 Order Block\n  • Fibonacci 61.8% overlap\n- Setup 2: SELL di area 2345.00 - 2348.00 (Score: 8.0/13.0)\n  • Fresh H1 Order Block"
    
    if not is_api_key_valid():
        print("API Key Gemini belum diset. Menampilkan pesan panduan:")
        print(analyze_news_with_gemini(test_event, test_zones))
    else:
        print("API Key valid. Memulai permintaan ke Gemini API...")
        result = analyze_news_with_gemini(test_event, test_zones)
        print("\nHasil Analisis:\n")
        print(result)
