# Personal MT5 Multi-Pair SMC Scanner & Telegram Execution Bot

Asisten personal Telegram trading yang terhubung langsung ke terminal MetaTrader 5 (MT5). Bot ini memindai struktur pasar berdasarkan **Smart Money Concepts (SMC)** secara real-time pada 5 pasang instrumen keuangan utama dan memungkinkan eksekusi pending order langsung dengan sekali klik dari pesan Telegram.

---

## 📂 Struktur Proyek (Standard Profesional)

Proyek ini disusun menggunakan standar struktur pengembangan Python modular yang bersih dan teratur:

```text
Xau_Scan/
├── scanner/                 # Package Utama Aplikasi
│   ├── __init__.py          # Menandai folder sebagai package
│   ├── config.py            # Konfigurasi sistem dan parameter dinamis
│   ├── data_provider.py     # Integrasi API MetaTrader 5 & fungsi order
│   ├── analyzer.py          # Logika analisa SMC & kalkulator SL/TP
│   └── chart_generator.py   # Pembuat grafik candlestick TradingView-style
├── tests/                   # Package Unit Testing
│   ├── __init__.py
│   └── test_analyzer.py     # Simulasi analisis menggunakan mock data
├── .env                     # File konfigurasi sensitif (Token, ID, Path)
├── .gitignore               # Daftar berkas yang diabaikan oleh Git
├── bot.py                   # Berkas peluncur utama (Entry Point)
├── requirements.txt         # Daftar dependensi modul Python
└── README.md                # Dokumentasi proyek (File Ini)
```

---

## ✨ Fitur Utama

1. **Pemindaian Struktur SMC Multi-Pair**:
   * Deteksi otomatis *Order Blocks* (OB) H1/H4 segar yang belum termitigasi.
   * Deteksi *Fair Value Gaps* (FVG) sebagai area konfluensi tambahan.
   * Perhitungan kedekatan dengan *Daily Pivot Points* dan *VWAP*.
   * Konfirmasi pergeseran arah tren menggunakan *Multi-Timeframe Trend Alignment* (EMA 200 H4, EMA 50 H1 & M15).
   * Deteksi pembersihan likuiditas sesi Asia (*Asia Session Liquidity Sweep*).
   * Konfirmasi struktur patahan tren di chart M15 (*MSS / CHoCH / BOS*).

2. **Skala Harga Dinamis (Dynamic Scale Mapping)**:
   * Parameter toleransi dan kekuatan impulsif secara cerdas beradaptasi dengan skala masing-masing pair (Forex, Gold, Kripto) sehingga tidak mengalami cacat logika deteksi.
   * Pembulatan harga desimal presisi disesuaikan otomatis (5 angka untuk Forex, 2 angka untuk Gold/BTC).

3. **Peleburan Area & Refinement (MTF Refinement)**:
   * Menggabungkan area H1 dan H4 yang bertumpang tindih (overlap > 50%) agar Telegram tidak mengirimkan sinyal berulang yang membingungkan.
   * Memberikan poin bonus **+1.0** untuk setup konfirmasi multi-timeframe.

4. **Eksekusi Sekali Klik (Instant Telegram Trading)**:
   * Grafik TradingView-style dikirimkan secara terpisah untuk setiap area setup yang ideal.
   * Tombol **"💼 Open Setup X"** di bawah gambar mengirimkan order limit pending (`Buy Limit` atau `Sell Limit`) langsung ke terminal MT5 Anda lengkap dengan SL & TP yang proporsional.

5. **Auto-Register Commands Menu**:
   * Ketika bot dijalankan, bot secara otomatis mendaftarkan daftar fungsinya ke server Telegram. Pengguna hanya perlu mengetik `/` untuk memunculkan semua menu perintah.

---

## 🔧 Persiapan & Instalasi

### 1. Kebutuhan Sistem
* Windows OS (karena pustaka `MetaTrader5` hanya kompatibel dengan Windows).
* Aplikasi **MetaTrader 5 Desktop** terinstal dan telah masuk ke akun broker aktif (Demo/Real).

### 2. Instalasi Modul
Buka CMD/PowerShell di folder proyek lalu jalankan:
```bash
pip install -r requirements.txt
```

### 3. Konfigurasi Lingkungan (`.env`)
Buat berkas bernama `.env` di folder root dan isi variabel berikut:
```env
TELEGRAM_TOKEN=8766527408:AAE9dMk5CRiiKlTKEwgSIoGgO6k977Vdn-A
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
MT5_TERMINAL_PATH=
MT5_SYMBOL=XAUUSDm
DEFAULT_LOT=0.01
```
*(Catatan: Kosongkan `MT5_TERMINAL_PATH` jika MT5 terpasang di direktori default komputer Anda).*

---

## 🚀 Cara Menjalankan

### Running Bot
Jalankan berkas peluncur utama dari folder root:
```bash
python bot.py
```

### Perintah Telegram
Ketik karakter `/` di obrolan bot Telegram Anda untuk melihat menu perintah:
* `/start` - Menampilkan panduan bot.
* `/scan_xau` - Pindai pasar Emas (`XAUUSDm`).
* `/scan_eur` - Pindai pasar Euro (`EURUSDm`).
* `/scan_gbp` - Pindai pasar Poundsterling (`GBPUSDm`).
* `/scan_jpy` - Pindai pasar Yen Jepang (`USDJPYm`).
* `/scan_btc` - Pindai pasar Bitcoin (`BTCUSDm`).

### Running Tests
Untuk memverifikasi logika kalkulator analisis SMC berjalan tanpa harus menghubungkan MT5 (menggunakan data simulasi), jalankan:
```bash
python tests/test_analyzer.py
```
