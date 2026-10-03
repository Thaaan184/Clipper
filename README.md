# 🎬 ClipForge

**Automated YouTube Long-Form to Viral 9:16 Vertical Shorts Pipeline**

ClipForge adalah platform otomasi self-hosted open-source untuk mengubah video YouTube berdurasi panjang (podcast, livestream game, talkshow, tutorial) menjadi klip vertikal **9:16 siap upload** (TikTok, Instagram Reels, YouTube Shorts). 

Sistem mengeliminasi proses manual editing: menganalisis momen terbaik dengan AI LLM, memotong video secara presisi tanpa mengunduh seluruh file mentah, melakukan visual reframe 9:16 cerdas, membakar subtitle kinetik per kata beranimasi, serta menstandarisasi audio ke standar platform sosial media.

---

## 📑 Daftar Isi
1. [Fitur Utama](#-fitur-utama)
2. [Arsitektur Sistem & Pipeline](#-arsitektur-sistem--pipeline)
3. [Spesifikasi Teknis Layout & Subtitle](#-spesifikasi-teknis-layout--subtitle)
4. [Struktur Direktori](#-struktur-direktori)
5. [Panduan Instalasi & Deployment](#-panduan-instalasi--deployment)
   - [Opsi 1: Docker Compose (Rekomendasi)](#opsi-1-docker-compose-rekomendasi)
   - [Opsi 2: Manual Development (Local)](#opsi-2-manual-development-local)
6. [Konfigurasi Environment (.env)](#-konfigurasi-environment-env)
7. [Dokumentasi API & Integrasi](#-dokumentasi-api--integrasi)
8. [Penanganan Khusus Livestream (Post-Live DVR)](#-penanganan-khusus-livestream-post-live-dvr)
9. [Keamanan & Zero-Secret Policy](#-keamanan--zero-secret-policy)
10. [Lisensi](#-lisensi)

---

## ⚡ Fitur Utama

- **One-Click Ingestion**: Cukup masukkan tautan URL YouTube (VOD standar, premiere, siaran langsung, atau rekaman livestream).
- **Selective Range Download**: Mengunduh hanya fragmen timestamp yang dibutuhkan menggunakan engine `yt-dlp`. Video berdurasi 3 jam tidak perlu diunduh penuh — segmen 30–60 detik selesai diambil dalam hitungan detik.
- **AI Content Intelligence (Scout Engine)**:
  - Menggunakan LLM OpenAI-compatible (9Router, OpenAI, Gemini 3.8 Flash, DeepSeek, Claude) untuk mengevaluasi transkrip.
  - Penilaian multi-kriteria berbasis 4 pilar (Total 100 poin):
    - *Hook Strength* (0–25): Daya tarik 3–5 detik pertama.
    - *Content Density* (0–25): Bobot informasi atau keseruan aksi.
    - *Standalone Value* (0–25): Klip dapat dipahami utuh tanpa menonton video penuh.
    - *Viral Potential* (0–25): Potensi share, komentar, dan retensi penonton.
  - Preset kurasi khusus konten: `gaming`, `podcast`, `tutorial`, `comedy`, dan `general`.
  - Pembuatan otomatis: Judul hook viral bahasa Indonesia, penjelasan kurasi, dan rekomendasi hashtag.
- **Audio Energy Spike Detection**: Analisis energi RMS audio dengan `librosa` dan `numpy` untuk mendeteksi momen reaksi spontan, tawa, teriakan, atau momen aksi menegangkan (*clutch moment*).
- **Smart 9:16 Reframe Engine (FFmpeg)**:
  - `blur`: Video 16:9 utuh di tengah dengan latar belakang blur proporsional. Menjaga seluruh interface, HUD game, minimap, dan teks tetap terbaca tanpa terpotong.
  - `center`: Pemotongan tengah vertikal 9:16 dinamis. Sangat cocok untuk wawancara podcast atau gameplay FPS dengan fokus crosshair.
  - `stacked`: Pembagian layar atas-bawah (webcam streamer di atas, gameplay/layar utama di bawah).
- **Kinetic Karaoke Subtitles**:
  - Transkripsi word-level akurat menggunakan engine `faster-whisper`.
  - Format subtitle ASS tingkat tinggi dengan font tegas, outline kontras, drop shadow, dan penyorotan kata aktif berwarna oranye menyala (*karaoke glow*).
- **In-Browser Subtitle Editor**:
  - Modal editor visual di frontend untuk mengedit langsung teks kata per kata, memperbaiki saltik nama/istilah, dan menyelaraskan timing sebelum diekspor.
- **EBU R128 Audio Loudnorm Mastering**:
  - Normalisasi audio otomatis ke target platform sosial media (-14 LUFS, true-peak -1 dBFS, LRA 11), mencegah video terlalu pelan atau pecah (*clipping*).
- **Real-Time SSE Timeline**:
  - Pelacakan progress bertahap (Ingest ➔ Scout ➔ Render Klip) secara langsung via Server-Sent Events tanpa polling HTTP manual.
- **Fleksibilitas Ekspor**:
  - Unduh MP4 per klip langsung ke komputer.
  - Unduh bundle seluruh klip sekaligus dalam format **ZIP Asinkron**.
  - Ekspor berkas subtitle mentah (.SRT) untuk keperluan caption platform.
  - **QR Code Scan-to-Mobile**: Generate QR code instan di browser untuk mengunduh klip langsung ke ponsel pintar (Android/iOS).
- **Cutting Room Brutalist Interface**:
  - Desain bertema industrial darkroom dengan palet hitam pekat, aksen oranye clapperboard film, indikator visual status, dan badge skor viralitas monolitik.

---

## 🏗️ Arsitektur Sistem & Pipeline

Sistem dirancang modular dengan pemisahan peran yang jelas antara pengambilan metadata, analisis semantik/akustik, dan proses rendering paralel:

```
                                  [ Browser Client (React + Vite) ]
                                                  │
                                     HTTP REST    │   SSE Event Stream
                                     (/api/*)     ▼   (/api/jobs/{id}/stream)
                 ┌─────────────────────────────────────────────────────────────────┐
                 │                       FastAPI Application                       │
                 └────────────────┬───────────────────────────────┬────────────────┘
                                  │                               │
                                  ▼                               ▼
                     ┌─────────────────────────┐     ┌─────────────────────────┐
                     │   SQLite (aiosqlite)    │     │   In-Memory Job Queue   │
                     │    data/clipforge.db    │     │    asyncio.Queue (Scan) │
                     └─────────────────────────┘     └────────────┬────────────┘
                                                                  │
       ┌──────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────┐
       │                                                                                                                      │
       ▼                                                          ▼                                                           ▼
┌──────────────┐                                           ┌──────────────┐                                            ┌──────────────┐
│   PHASE 1    │                                           │   PHASE 2    │                                            │   PHASE 3    │
│    INGEST    │                                           │ AI SCOUTING  │                                            │    EDITOR    │
└──────┬───────┘                                           └──────┬───────┘                                            └──────┬───────┘
       │                                                          │                                                           │
       ├─► yt-dlp metadata probe (Title, Durasi, Format)          ├─► Audio RMS Spike Extractor                               ├─► Selective Segment Download
       │   (Tanpa download video utuh)                            │   (librosa / numpy window analysis)                       │   (yt-dlp download_ranges)
       │                                                          │                                                           │
       ├─► Dual-Route Transcript Extraction                       ├─► LLM Prompting & Scoring                                 ├─► Segment Whisper Engine
       │   ├─ Rute Utama: youtube-transcript-api (id / en)        │   (9Router / Gemini / OpenAI Gateway)                     │   (faster-whisper word-timestamps)
       │   └─ Rute Cadangan: yt-dlp audio + faster-whisper        │   (Hook 25 + Density 25 + Value 25 + Viral 25)            │
       │                                                          │                                                           ├─► Kinetic ASS Subtitle Generation
       └─► Post-Live Manifestless Detection                       └─► Algoritma Cadangan (Tanpa Transkrip)                    │   (Bebas desinkronisasi PTS)
           (Bypass transkripsi audio penuh untuk durasi >1800s)       (Distribusi matematis momen + spike audio)              │
                                                                                                                              ├─► FFmpeg 9:16 Video Reframe
                                                                                                                              │   (Blur / Center / Stacked)
                                                                                                                              │
                                                                                                                              └─► FFmpeg EBU R128 Loudnorm
                                                                                                                                  (Audio mastering -14 LUFS)
                                                                                                                                              │
                                                                                                                                              ▼
                                                                                                                                 [ data/processed/*.mp4 ]
                                                                                                                                 [ Single / ZIP Export  ]
```

### Penjelasan Rinci Pipeline:

1. **Phase 1: Ingest**
   - Mengambil informasi berkas melalui `yt-dlp` tanpa mengunduh stream video.
   - Menarik subtitle resmi atau auto-generated YouTube (`youtube_transcript_api`).
   - Apabila video adalah livestream baru selesai (`post_live`), sistem secara pintar mendeteksi ketiadaan CC dan melewati proses transkripsi 3 jam CPU penuh untuk mencegah container hang atau kehabisan memori.

2. **Phase 2: AI Scouting**
   - Teks transkrip dan array lonjakan audio dimasukkan ke dalam prompt terstruktur.
   - LLM mengekstrak 3–8 segmen terbaik dengan timestamp mulai (`start_time`) dan selesai (`end_time`) yang presisi.
   - Setiap momen diberi judul hook bahasa Indonesia, alasan kurasi, dan skor viralitas (0–100).
   - Apabila transkrip kosong (video musik/gaming/livestream baru usai), sistem menggunakan generator momen terdistribusi matematis dengan menghindari intro/outro mati dan menyelaraskannya pada titik puncak audio.

3. **Phase 3: Editor & Rendering**
   - Worker editor memproses antrean klip secara paralel sesuai batas `MAX_CONCURRENT_RENDERS`.
   - Mengunduh segmen video H.264 MP4 dan audio AAC menggunakan time range download.
   - Menjalankan model `faster-whisper` hanya pada potongan 30–60 detik tersebut untuk menghasilkan word-level timestamps instan.
   - Mengonversi timing kata menjadi berkas format ASS (Advanced SubStation Alpha) lengkap dengan parameter style, shadow, dan tag karaoke `{\c&H0055FF&}`.
   - Menjalankan pipeline multi-pass FFmpeg:
     1. Filter `setpts=PTS-STARTPTS` dan `aresample=async=1000` untuk menyelaraskan base clock timestamp.
     2. Visual filter reframe ke resolusi 1080x1920 (9:16).
     3. Pembakaran subtitle ASS via `libass`.
     4. Audio mastering dua pass EBU R128 `loudnorm` ke -14 LUFS.

---

## 🎨 Spesifikasi Teknis Layout & Subtitle

### Layout Video (Output: 1080 × 1920, 9:16 Vertikal)

| Mode | Deskripsi | Target Konten | Karakteristik FFmpeg |
|---|---|---|---|
| **Blur** *(Default)* | Video 16:9 utuh di tengah; background di-scale dan di-blur | Gameplay, Tutorial, Presentasi | `split [bg][fg]; [bg] scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:5,setsar=1 [bg_blur]; [fg] scale=1080:607:force_original_aspect_ratio=decrease [fg_scaled]; [bg_blur][fg_scaled] overlay=(W-w)/2:(H-h)/2` |
| **Center** | Potong area tengah video langsung memenuhi layar 9:16 | Podcast, Talkshow, FPS Crosshair | `scale=-1:1920, crop=1080:1920:(in_w-1080)/2:0, setsar=1` |
| **Stacked** | Webcam di paruh atas, gameplay/layar aksi di paruh bawah | Streamer reaksi, Gaming reaction | Dua stream crop bertingkat masing-masing 1080×960 |

### Subtitle Kinetik (ASS Style Spec)
- **Font**: Arial Black / Montserrat Bold / Helvetica Neue (Bold Sans-Serif).
- **Ukuran**: 26 pt (terskala proporsional pada kanvas 1080×1920).
- **Warna Teks Primer**: Putih Bersih (`#FFFFFF`).
- **Warna Kata Aktif (Karaoke Highlight)**: Oranye Neon (`#FF5500` / `#FFAA00`).
- **Garis Luar (Outline)**: Hitam Pekat 4px (`#000000`).
- **Bayangan (Shadow)**: 3px depth dengan translusen 40%.
- **Posisi**: Alignment 2 (Tengah Bawah), Margin Vertikal 180px dari batas bawah layar agar tidak tertutup ikon/teks antarmuka TikTok dan Reels.

---

## 📁 Struktur Direktori

```
clipforge/
├── Dockerfile                  # Multi-stage build (Debian Trixie, Node.js 22, Python 3.11, FFmpeg)
├── docker-compose.yml          # Konfigurasi container service & bind mount volume
├── .env.example                # Template variabel konfigurasi environment
├── README.md                   # Dokumentasi teknis proyek
│
├── backend/                    # Core Backend Engine (FastAPI)
│   ├── main.py                 # Router API, Lifecycle Event, SSE Dispatcher, Pipeline Runner
│   ├── config.py               # Pydantic Settings & Environment Parser
│   ├── models.py               # Pydantic Request/Response DTOs & Validation Schemas
│   ├── db.py                   # Inisialisasi Skema SQLite (aiosqlite)
│   ├── requirements.txt        # Dependensi Python Backend
│   │
│   ├── services/               # Layanan Teknis & Algoritma
│   │   ├── llm.py              # LLM Scouting, Prompting, Fallback Moments Generator
│   │   ├── transcript.py       # Ekstraksi Subtitle YouTube API
│   │   ├── subtitles.py        # Faster-Whisper Word Transcriber & ASS Generator
│   │   └── reframe.py          # FFmpeg Command Builder, Canvas Layout, Loudnorm Mastering
│   │
│   └── workers/                # Pipeline Execution Workers
│       ├── ingest.py           # Worker Verifikasi Video, Metadata & Fallback Handling
│       ├── audio_analysis.py   # Worker Ekstraksi Audio & Librosa RMS Spike Scouting
│       ├── scout.py            # Worker Koordinasi Scouting Momen & Evaluasi
│       └── editor.py           # Worker Selective Range Download & Render Video
│
├── frontend/                   # UI Client (React + TypeScript + Vite)
│   ├── index.html              # HTML Shell
│   ├── package.json            # Dependensi Frontend
│   ├── vite.config.ts          # Konfigurasi Vite & Dev Reverse-Proxy
│   │
│   └── src/
│       ├── main.tsx            # Entry Point React
│       ├── App.tsx             # Root Routing & State
│       ├── index.css           # Global Typography & Cutting-Room Tokens
│       │
│       ├── pages/
│       │   ├── Home.tsx        # Halaman Input URL, Preset Konten, Riwayat Proyek
│       │   └── Results.tsx     # Workspace Klip, Video Player, QR Modal, Subtitle Editor
│       │
│       ├── components/
│       │   ├── Header.tsx      # Topbar Navigation & Running Timecode Clapper
│       │   ├── Timeline.tsx    # Live Processing Step Tracker (SSE Stream)
│       │   ├── ClipCard.tsx    # Kartu Klip, Preview Video, Skor Viral, Action Buttons
│       │   └── SubtitleEditorModal.tsx # Editor Interaktif Subtitle Word-by-Word
│       │
│       └── lib/
│           ├── api.ts          # Axios / Fetch HTTP API Client
│           └── sse.ts          # Native EventSource Lifecycle Manager
│
└── data/                       # Persistent Storage (Host Volume)
    ├── clipforge.db            # Database SQLite
    ├── raw/                    # File Audio Sementara & Unduhan Rentang Mentah
    └── processed/              # File Video Klip MP4 Siap Unduh & Berkas Subtitle
```

---

## 🚀 Panduan Instalasi & Deployment

### Opsi 1: Docker Compose (Rekomendasi)

Metode terbaik untuk deployment production di server VPS / VM lokal. Semua dependensi sistem (FFmpeg 7+, libass, Deno JS runtime untuk yt-dlp) sudah terisolasi di dalam container.

1. **Clone repositori**:
   ```bash
   git clone https://github.com/Thaaan184/Clipper.git
   cd Clipper
   ```

2. **Siapkan file konfigurasi `.env`**:
   ```bash
   cp .env.example .env
   nano .env
   ```
   *Pastikan mengisi `LLM_API_BASE` dan `LLM_API_KEY` sesuai provider LLM kamu.*

3. **Jalankan container**:
   ```bash
   docker compose up -d --build
   ```

4. **Akses antarmuka web**:
   Buka browser di `http://localhost:8080` (atau IP server kamu).

5. **Melihat status log**:
   ```bash
   docker logs -f clipforge
   ```

---

### Opsi 2: Manual Development (Local)

Gunakan metode ini jika kamu ingin memodifikasi kode frontend atau backend secara langsung dengan Hot Module Replacement (HMR).

#### Prasyarat Sistem:
- **Python**: Versi 3.10 atau 3.11.
- **Node.js**: Versi 18+ & npm.
- **FFmpeg**: Wajib mendukung `libass` (subtitle rendering) dan `libx264`.
- **Deno** atau **QuickJS**: Disarankan terinstal agar `yt-dlp` dapat mengekstrak stream YouTube 1080p tanpa hambatan n-token challenge.

#### Langkah 1: Setup Backend
```bash
# 1. Masuk ke direktori backend
cd backend

# 2. Buat dan aktifkan virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Pasang dependensi python
pip install -r requirements.txt

# 4. Siapkan direktori penyimpanan data dan environment
cd ..
cp .env.example .env
mkdir -p data/raw data/processed
cd backend

# 5. Jalankan server FastAPI
python main.py
```
*Backend API akan berjalan di port `http://localhost:8080`.*

#### Langkah 2: Setup Frontend
Buka jendela terminal baru:
```bash
# 1. Masuk ke direktori frontend
cd frontend

# 2. Pasang dependensi Node.js
npm install

# 3. Jalankan server development Vite
npm run dev
```
*Antarmuka development akan berjalan di `http://localhost:5173` dan otomatis mengarahkan panggilan API `/api/*` ke backend port 8080.*

#### Langkah 3: Build Frontend untuk Production
Untuk menyatukan build frontend ke dalam server FastAPI:
```bash
cd frontend
npm run build
```
*Hasil bundel di `frontend/dist` akan disajikan secara otomatis oleh FastAPI sebagai root static files.*

---

## ⚙️ Konfigurasi Environment (`.env`)

| Variabel | Tipe | Default | Penjelasan |
|---|---|---|---|
| `PORT` | Integer | `8080` | Port listening HTTP server FastAPI. |
| `DATA_DIR` | String | `./data` | Lokasi direktori penyimpanan SQLite, audio cache, dan video output. |
| `LLM_API_BASE` | URL | `http://localhost:20128/v1` | URL basis endpoint OpenAI-compatible (9Router / OpenAI / vLLM). |
| `LLM_API_KEY` | String | `sk-...` | Token otorisasi API LLM (Bearer token). |
| `LLM_MODEL` | String | `ag/gemini-3.8-flash-medium` | Model reasoning yang bertugas menganalisis transkrip dan kurasi momen. |
| `MAX_VIDEO_DURATION` | Integer | `10800` | Batas durasi maksimal video sumber dalam detik (10800 = 3 jam). |
| `MAX_CONCURRENT_RENDERS` | Integer | `3` | Batas proses rendering video FFmpeg yang berjalan bersamaan. |
| `MAX_PENDING_JOBS` | Integer | `5` | Kapasitas antrean pemrosesan video sebelum menolak permintaan baru. |
| `MAX_DISK_GB` | Float | `10.0` | Ambang batas maksimal penggunaan ruang disk sebelum auto-cleanup. |
| `WHISPER_MODEL` | String | `base` | Model Whisper untuk subtitle klip (`base`, `small`, `medium`, `large-v3`). |
| `WHISPER_DEVICE` | String | `cpu` | Device komputasi inferensi Whisper (`cpu` atau `cuda`). |
| `CORS_ORIGINS` | String | `http://localhost:5173,...` | Daftar origin yang diizinkan untuk request lintas domain. |
| `RATE_LIMIT_SCANS_PER_HOUR` | Integer | `5` | Batasan frekuensi scan video per alamat IP untuk mencegah abuse. |

---

## 📡 Dokumentasi API & Integrasi

Semua respon menggunakan format JSON standar:

### 1. Ingest Video Baru
- **Endpoint**: `POST /api/scan`
- **Body**:
  ```json
  {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "clip_count": 5,
    "duration_target": "30-60",
    "content_type": "gaming",
    "subtitle_lang": "id",
    "layout": "blur"
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "job_id": "7ec0c11d-2f32-407d-a6b3-0712bf8df6c6",
    "video_id": "67aba48f"
  }
  ```

### 2. Live Job Progress Stream (SSE)
- **Endpoint**: `GET /api/jobs/{job_id}/stream`
- **Format**: `text/event-stream`
- **Contoh Event**:
  ```
  event: progress
  data: {"phase": "scout", "progress": 45, "message": "AI sedang menganalisis transkrip..."}
  ```

### 3. Detail Video & Hasil Klip
- **Endpoint**: `GET /api/videos/{video_id}`
- **Response** `200 OK`: Mengembalikan metadata video, status pemrosesan, dan daftar seluruh klip yang dihasilkan lengkap dengan URL berkas MP4, durasi, nilai viralitas, dan data subtitle.

### 4. Re-Scout Klip dengan Parameter Baru
- **Endpoint**: `POST /api/videos/{video_id}/rescout`
- **Body**:
  ```json
  {
    "clip_count": 3,
    "duration_target": "15-30",
    "content_type": "podcast",
    "subtitle_lang": "id",
    "layout": "center"
  }
  ```

### 5. Render Ulang Klip Tertentu
- **Endpoint**: `POST /api/clips/{clip_id}/retry`
- **Deskripsi**: Merender ulang satu klip spesifik (misalnya setelah mengganti layout atau memperbaiki teks subtitle).

### 6. Perbarui & Simpan Subtitle Klip
- **Endpoint**: `PUT /api/clips/{clip_id}/subtitles`
- **Body**: JSON array kata per kata (`word`, `start`, `end`).

### 7. Ekspor Subtitle SRT
- **Endpoint**: `GET /api/clips/{clip_id}/subtitles.srt`
- **Response**: File teks mentah format SubRip (.srt).

### 8. Download Semua Klip (ZIP Asinkron)
- **Endpoint**: `GET /api/videos/{video_id}/download-all`
- **Deskripsi**: Menghasilkan arsip `.zip` berisi seluruh klip MP4 beresolusi penuh menggunakan temporary file stream yang aman dari memory overflow.

---

## 💡 Penanganan Khusus Livestream (Post-Live DVR)

Livestream YouTube yang baru saja selesai siaran memiliki karakteristik teknis khusus:
1. **Manifestless Mode**: Server YouTube memerlukan waktu 1 hingga 12 jam untuk memproses siaran langsung menjadi VOD standar. Selama periode ini, YouTube API belum menyediakan auto-captions/CC.
2. **Post-Live Architecture Workaround**:
   - ClipForge mendeteksi status video `post_live` dan durasi panjang (>1.800 detik).
   - Sistem **melewati transkripsi audio penuh** pada tahap awal yang biasanya memicu container timeout.
   - LLM Scout beralih ke mode **Instant Highlight Scouting** menggunakan analisis sebaran waktu dan deteksi lonjakan audio RMS.
   - Unduhan segmen klip menggunakan `download_ranges` stream copy langsung ke potongan MP4 30–60 detik.
   - Subtitle digenerate secara on-demand via Whisper hanya pada potongan klip pendek tersebut, menghasilkan klip siap tonton dalam hitungan detik.

---

## 🔒 Keamanan & Zero-Secret Policy

- **Zero Secret in Codebase**: Token API, kata sandi, dan kredensial server tidak boleh disimpan ke repositori Git. Seluruh rahasia wajib dimuat melalui variabel environment (`.env`).
- **Sanitized Execution**: Semua argumen yang dikirimkan ke `ffmpeg` dan `yt-dlp` divalidasi dan di-escape secara ketat untuk mencegah serangan *command injection*.
- **Local Isolation**: Berkas video dan audio yang diunduh hanya berada di direktori lokal `./data` dan dibersihkan otomatis dari cache sementara.

---

## 📄 Lisensi

Proyek ini dirilis di bawah lisensi [MIT License](LICENSE).

Dibuat & Dikembangkan untuk Kreator Konten, Streamer, dan Agensi Media Digital.
**ClipForge — Cut What Matters.**
