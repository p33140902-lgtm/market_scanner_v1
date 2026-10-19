# Market Scanner v1

## Status versi ini
Prototype pertama untuk menguji mesin pemindai dengan data candle publik Binance Spot. Ini **belum** menjadi scanner lengkap untuk seluruh pasar. Belum ada scheduler otomatis atau notifikasi.

## Cara menjalankan di komputer
Perlu Python 3.11 atau lebih baru.

1. Ekstrak ZIP.
2. Buka terminal di folder `market_scanner_v1`.
3. Buat virtual environment:

   ```bash
   python -m venv .venv
   ```

4. Aktifkan environment.

   Windows:
   ```bash
   .venv\Scripts\activate
   ```

   macOS/Linux:
   ```bash
   source .venv/bin/activate
   ```

5. Install dependensi dan jalankan:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

6. Browser akan membuka dashboard lokal. Pilih timeframe dan pasangan, lalu tekan **Jalankan scan**.

## Fitur yang ada
- Timeframe M15, H1, H4, D1.
- Mengambil candle Binance Spot untuk pasangan USDT pilihan awal.
- Mengabaikan candle terakhir jika belum selesai.
- Menghitung EMA20, EMA50, RSI14, ATR% dan rasio volume terhadap rata-rata 20 candle.
- Mengurutkan kandidat berdasarkan 5 kondisi contoh.
- Mengunduh hasil scan sebagai CSV.

## Sumber data awal dan rencana perluasan
- **Crypto:** Binance public market-data endpoint `https://data-api.binance.vision/api/v3/klines`; dokumentasi Binance menyebut endpoint ini tidak membutuhkan API key untuk data pasar publik.
- **Forex:** kandidat uji coba Twelve Data Basic; kuotanya terbatas, jadi mulai dengan beberapa pasangan mayor dan periksa simbol/timeframe yang tersedia sebelum menjadwalkan scan.
- **XAUUSD:** perlu verifikasi simbol spot emas dan aksesnya pada paket gratis yang dipilih. Jangan mengganti diam-diam dengan futures atau instrumen lain karena datanya berbeda.
- **Saham Indonesia:** Yahoo Finance mencatat IDX (`.JK`) sebagai data tertunda sekitar 10 menit. Library pihak ketiga bukan feed resmi yang dijamin stabil; cocok untuk eksperimen saja, bukan produksi tanpa memeriksa ketentuan penggunaan.

## Batasan penting
- Daftar simbol crypto masih dipilih manual, bukan seluruh aset exchange.
- Aturan skor hanyalah contoh teknis, bukan sinyal beli/jual atau jaminan hasil.
- Belum ada database, scheduler, Telegram alert, backtest, atau adapter FX/XAU/IDX.
- API publik dapat berubah, membatasi akses, atau gagal sementara.
- Tidak ada fitur mengirim order dan tidak perlu memasukkan API key trading.

## Roadmap
1. Jalankan prototipe dan pastikan data tampil.
2. Tambahkan adapter data FX dan uji kuota gratis.
3. Validasi adapter XAUUSD secara terpisah.
4. Tambahkan adapter saham `.JK` dan tandai keterlambatan data.
5. Tambahkan SQLite, scheduler yang menghormati batas API, dan notifikasi.
6. Uji strategi di data historis sebelum mempercayai skor.
