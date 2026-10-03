# 🎬 ClipForge

Otomatis potong video YouTube panjang (podcast, game, tutorial) menjadi klip vertikal **9:16 ready-to-upload** (TikTok, Reels, Shorts).

AI menemukan momen terbaik (hook kuat, punchline, aksi seru), memotong klip, melakukan auto-reframe 9:16, dan membakar subtitle bergaya kinetic otomatis.

---

## ⚡ Fitur Utama

- **One-Click Pipeline**: Tempel satu URL YouTube → dapatkan 3–8 klip vertikal siap upload.
- **Selective Download**: Menggunakan `yt-dlp --download-sections` — tidak perlu mengunduh video berjam-jam secara penuh.
- **Smart Scouting (LLM)**: Menggunakan model reasoning via OpenAI-compatible API (9Router / OpenAI) untuk menilai momen berdasarkan Hook (0–25), Densitas Konten (0–25), Nilai Mandiri (0–25), dan Potensi Viral (0–25).
- **Audio Energy Spike Detection**: Mendeteksi lonjakan energi audio (teriakan, tawa, reaksi hype pada gameplay/podcast) menggunakan analisis RMS.
- **Auto Reframe 9:16**:
  - `blur`: Layar gameplay/video 16:9 utuh di tengah dengan background blur (aman untuk HUD/minimap game).
  - `center`: Center crop langsung ke 9:16 (cocok untuk game FPS / fokus crosshair).
  - `stacked`: Atas webcam streamer, bawah gameplay aksi.
- **Kinetic Subtitles**: Word-level timestamps via `faster-whisper` dibakar langsung ke video dengan highlight kata aktif warna oranye.
- **Loudnorm Audio**: Audio otomatis dinormalisasi ke standar platform (-14 LUFS).
- **Real-time SSE Timeline**: Monitor proses pemotongan dan transkripsi secara langsung dari browser.
- **Desain Cutting Room**: UI bertema flat hitam-oranye terinspirasi clapper board film, crop marks siku, perforasi pita film, dan skor viralitas raksasa. Tanpa gradient.

---

## 🚀 Quick Start (Self-Host)

### Opsi 1: Docker Compose (Direkomendasikan)

Prasyarat: [Docker](https://docs.docker.com/get-docker/) & Docker Compose terpasang.

```bash
# 1. Clone repository
git clone https://github.com/Thaaan184/Clipper.git
cd Clipper

# 2. Salin dan sesuaikan environment
cp .env.example .env
nano .env   # atau gunakan editor teks favorit kamu
```

Sesuaikan nilai API LLM kamu di `.env`:
```ini
LLM_API_BASE=http://your-9router-or-openai-host/v1
LLM_API_KEY=sk-your-api-key-here
LLM_MODEL=ag/gemini-3.8-flash-medium
```

```bash
# 3. Jalankan container
docker compose up -d

# 4. Buka aplikasi di browser
# http://localhost:8080
```

---

### Opsi 2: Menjalankan Manual (Development)

Prasyarat:
- Python 3.10 atau 3.11
- Node.js 18+ & npm
- FFmpeg (dengan dukungan libass dan libx264)
- yt-dlp

#### 1. Setup Backend

```bash
cd backend

# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependensi
pip install -r requirements.txt

# Buat folder data dan salin env
cd ..
cp .env.example .env
mkdir -p data/raw data/processed
cd backend

# Jalankan backend API
python main.py
```
Backend akan berjalan di `http://localhost:8080`.

#### 2. Setup Frontend

Buka terminal baru:

```bash
cd frontend

# Install packages
npm install

# Jalankan dev server dengan HMR
npm run dev
```
Frontend development akan berjalan di `http://localhost:5173` (ter-proxy otomatis ke backend port 8080).

Untuk production build:
```bash
cd frontend
npm run build
# Hasil build di frontend/dist/ akan otomatis di-serve oleh FastAPI di port 8080
```

---

## ⚙️ Konfigurasi Environment (`.env`)

| Variabel | Default | Keterangan |
|---|---|---|
| `LLM_API_BASE` | `http://100.96.207.8:20128/v1` | Endpoint OpenAI-compatible (9Router / Ollama / OpenAI) |
| `LLM_API_KEY` | `sk-...` | API Key untuk autentikasi LLM |
| `LLM_MODEL` | `ag/gemini-3.8-flash-medium` | Model yang digunakan untuk kurasi momen |
| `PORT` | `8080` | Port HTTP backend server |
| `DATA_DIR` | `./data` | Lokasi penyimpanan database SQLite dan video hasil render |
| `MAX_VIDEO_DURATION` | `10800` | Batas durasi maksimal video sumber dalam detik (10800s = 3 jam) |
| `MAX_CONCURRENT_RENDERS` | `3` | Jumlah proses render video FFmpeg simultan |
| `MAX_PENDING_JOBS` | `5` | Batas antrean scan job sebelum menolak permintaan baru |
| `WHISPER_MODEL` | `large-v3` | Model Whisper fallback (`base`, `small`, `medium`, `large-v3`) |
| `WHISPER_DEVICE` | `cpu` | Device inferensi Whisper (`cpu` atau `cuda`) |
| `RATE_LIMIT_SCANS_PER_HOUR` | `5` | Batas permintaan scan per alamat IP per jam |

---

## 🏗️ Arsitektur Sistem

```
[Browser Client]
       │
       ▼  HTTP / SSE
┌────────────────────────────────────────────────────────┐
│                   FastAPI (Port 8080)                  │
│                                                        │
│  Phase 1: Ingest                                       │
│  ├─ yt-dlp metadata extraction (no download)           │
│  ├─ youtube-transcript-api (fallback: faster-whisper)  │
│  └─ librosa audio RMS energy spike detection           │
│                                                        │
│  Phase 2: Scout Agent                                  │
│  ├─ 9Router / OpenAI Chat Completion                   │
│  ├─ Gemini 3.8 Flash (1M Context)                      │
│  └─ Moment Scoring (Hook, Density, Viral Potential)   │
│                                                        │
│  Phase 3: Editor Agent                                 │
│  ├─ yt-dlp --download-sections (hanya range klip)      │
│  ├─ faster-whisper word-level subtitle (.ass)          │
│  ├─ FFmpeg 9:16 Reframe (Blur / Center / Stacked)      │
│  └─ FFmpeg loudnorm -14 LUFS mastering                 │
└────────────────────────────────────────────────────────┘
       │
       ▼
[SQLite Storage: data/clipforge.db + data/processed/*.mp4]
```

---

## 🔒 Keamanan

- **Zero-Secret Commits**: File `.env` dan token kredensial terdaftar di `.gitignore` dan tidak akan ter-push ke repository publik.
- **Local Storage**: Video yang diproses hanya disimpan di folder lokal mesin host (`data/`). File raw audio/video sementara otomatis dibersihkan setelah render selesai.
- **Rate Limiting**: Dilengkapi rate limit bawaan per IP address untuk mencegah eksploitasi bandwidth dan kuota token LLM.
- **Isolated Execution**: FFmpeg dan yt-dlp dijalankan dengan argumen yang di-sanitize ketat untuk mencegah command injection.

---

## 📄 Lisensi

MIT License © 2026 ClipForge Contributors.
