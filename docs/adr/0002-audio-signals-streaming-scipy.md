# ADR 0002: Audio Signal Extraction via FFmpeg Streaming and NumPy/SciPy

- Status: accepted
- Date: 2026-10-04

## Konteks
VOD siaran langsung gaming berdurasi 3 hingga 5 jam membutuhkan ekstraksi fitur audio (RMS loudness, surge, spectral onset flux, high-frequency energy ratio, crest factor, dan nonspeech loudness).
Memuat seluruh audio mentah (misal PCM float32 16kHz selama 4 jam = ~921 MB uncompressed) ke dalam memori RAM sekaligus menggunakan library seperti Librosa berpotensi menyebabkan Out-Of-Memory (OOM) pada host dengan batas memori terbatas. Librosa juga memiliki waktu cold-start import yang lambat (~2-4 detik) karena dependensi berat (numba, soundfile, pooch).

## Opsi yang Dipertimbangkan
1. **Librosa**: Fitur audio sangat lengkap, namun import lambat, memuat data besar ke memori, dan menambah rantai dependensi yang rentan terhadap versi compiler LLVM/Numba.
2. **PyDub / SoundFile**: Mudah digunakan tetapi memerlukan pemuatan buffer audio besar dan fitur analisis frekuensi (STFT) terbatas.
3. **FFmpeg Subprocess Pipe + NumPy / SciPy Streaming**:
   - Audio di-decode langsung lewat standard output pipe FFmpeg (`-f f32le -ac 1 -ar 16000 pipe:1`) dalam blok streaming jendela waktu (mis. 60 detik per iterasi).
   - Analisis energi, RMS, rolling median, STFT spectral flux, dan filtering dilakukan secara murni menggunakan NumPy dan SciPy (`scipy.signal`).
   - Jejak memori RAM konstan (< 50 MB) terlepas dari apakah durasi VOD adalah 15 menit atau 8 jam.

## Keputusan
Memilih **Opsi 3 (FFmpeg Pipe + NumPy/SciPy Streaming)**.
Silero VAD diakses melalui modul bawaan `faster_whisper.vad` yang efisien dan berjalan di CPU tanpa alokasi memori berlebih.

## Konsekuensi
- **Positif**:
  - Waktu startup proses sub-detik (zero delay).
  - Konsumsi RAM konstan dan sangat hemat (< 50 MB) untuk VOD panjang.
  - Zero dependensi eksternal baru; memanfaatkan FFmpeg dan `numpy`/`scipy` yang sudah terpasang.
- **Negatif**:
  - Diperlukan implementasi kalkulasi spectral flux dan rolling baseline sendiri berbasis SciPy (telah teruji dan terverifikasi).
- **Rollback**:
  - Jika diperlukan fitur akustik tingkat lanjut, modul dapat diperluas atau dibungkus ulang tanpa mengubah antarmuka `AudioSignalExtractor`.
