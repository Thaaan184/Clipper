# ADR 0004: Subtitle ASS Generator and Vertical 9:16 Reframe Pipeline

- Status: accepted
- Date: 2026-10-04

## Konteks
Pada ClipForge v1, rendering vertikal dan subtitle mengalami masalah kerapuhan font (font missing pada libass), drift desinkronisasi audio/video akibat pembulatan centisecond karaoke yang salah, dan distorsi rasio aspek. Diperlukan arsitektur rendering deterministik berkualitas tinggi untuk video 9:16 vertikal (1080x1920) dengan kinetic subtitle.

## Keputusan
1. **Timebase Invariant Kanonik**:
   - Seluruh koordinat subtitle dikonversi dari waktu `source_s` ke waktu klip `clip_s` (0.00 = frame pertama klip).
   - Timestamp ASS `H:MM:SS.cc` dibulatkan ke centisecond secara monoton; jika `start_cs >= end_cs`, waktu `end_cs` otomatis dimajukan 1 centisecond.
2. **Generasi Subtitle Kinetic Tanpa Karaoke Tag**:
   - Menggunakan pendekatan satu baris Dialogue per "state kata aktif" (`{\c&H008CFF&}kata_aktif{\r}`).
   - Menghindari kerapuhan tag karaoke `\k`/`\kf` terhadap pembulatan floating point dan bug font caching.
   - Text wrapping diukur dengan metrik font asli menggunakan Pillow (`ImageFont.getlength`).
   - Batas maksimum 4 kata per chunk, diputus pada jeda $\ge 350\text{ms}$ atau tanda baca.
3. **Penyatuan Font Ter-Bundle**:
   - Font OFL (Liberation Sans Bold / Regular) dibundel langsung di `apps/api/assets/fonts/` dan disalin ke `fonts/` per folder klip.
   - FFmpeg dipanggil dengan parameter `ass=subs.ass:fontsdir=fonts` dengan `cwd` di folder klip untuk menghilangkan ketergantungan path absolut dan kegagalan font system.
4. **Reframe 9:16 (1080x1920)**:
   - Mode `blur` (default): Latar belakang video diskalakan ke 1080x1920, diberi gaussian blur (`gblur=sigma=30`) dan digelapkan (`eq=brightness=-0.08`). Gameplay 16:9 dipusatkan dengan skala `1080:-2` lanczos.
   - Mode `center`: Pemotongan tengah tajam (`crop=1080:1920`).
5. **Normalisasi Audio Loudnorm Dua-Pass**:
   - Pass 1 mengukur parameter audio (`I=-14`, `TP=-1.5`, `LRA=11`).
   - Pass 2 menerapkan nilai terukur untuk loudness broadcast standar TikTok/Reels/Shorts.
6. **WYSIWYG Frame Preview**:
   - Endpoint `/api/clips/{id}/subtitles/preview` merender frame PNG pada waktu `t` menggunakan filtergraph dan file ASS yang identik, menjamin preview sama persis dengan video final.
7. **Automated QA Check**:
   - Setiap klip diuji dengan FFprobe (dimensi 1080x1920, yuv420p, fps konstan, selisih A/V < 40ms) sebelum ditandai sukses.

## Konsekuensi
- **Positif**:
  - Eliminasi bug subtitle hancur atau font hilang.
  - Video 1080x1920 standar Shorts/Reels/TikTok tanpa distorsi aspek rasio.
  - Suara jernih dan konsisten dengan target loudness -14 LUFS.
