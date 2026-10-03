# ClipForge v2

> **Signal-First, LLM-Last Gaming Video Clipper**

ClipForge v2 adalah sistem otomatis pemotong video vertikal (9:16) untuk highlight gaming dan livestream VOD YouTube, dirancang dengan filosofi **signal-first, LLM-last**:
- Sinyal objektif murah (Audio Energy Surge, Onset Density, VAD, Chat Velocity, Replay Heatmap) mendeteksi kandidat momen tanpa ketergantungan pada transkrip/CC.
- Whisper ASR hanya berjalan pada segmen kandidat terpilih.
- LLM bertindak sebagai verifikator berbasis bukti terstruktur (menolak segmen *talking-only* dan memberi metadata hook/judul).
- Subtitle kinetic deterministik dengan metrik font terukur dan QA render otomatis.

---

## ⚠️ Arsip Kode Legacy (v1)

Kode v1 ClipForge telah diarsipkan secara permanen dan dapat diakses melalui:
* Branch: `legacy/v1` (`git checkout legacy/v1`)
* Tag: `legacy-v1-final` (`git checkout tags/legacy-v1-final`)
* Dokumentasi Audit & Pembelajaran: `docs/legacy/LEGACY_AUDIT.md` dan `docs/legacy/LEARNINGS.md`
* Peta Pakai Ulang Modul: `docs/legacy/REUSE_MAP.md`

---

## 🏗️ Struktur Repositori Monorepo

```
.
├── apps/
│   ├── api/                      # Backend FastAPI (src-layout)
│   │   ├── src/clipforge/        # Core, DB, Jobs, Ingest, Signals, Fusion, Render
│   │   └── tests/                # Unit & Integration Tests (Pytest)
│   └── web/                      # Frontend (React 18 + TS strict + Vite + Tailwind)
├── docker/                       # Dockerfile.api, Dockerfile.web, nginx.conf
├── docs/
│   ├── adr/                      # Architecture Decision Records
│   ├── legacy/                   # Audit dan baseline v1
│   └── references/               # Analisis repo referensi & lisensi
├── eval/
│   └── golden/                   # Dataset evaluasi VOD nyata
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Memulai (Lokal)

### Prasyarat
- Python 3.11+
- Node.js 20+
- FFmpeg 4.4+ (dengan dukungan `--enable-libass`)
- `uv` (rekomendasi manajer paket Python)

### 1. Menjalankan Backend API
```bash
cd apps/api
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn clipforge.api.app:app --reload --port 8000
```
Periksa liveness & readiness:
```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

### 2. Menjalankan Frontend Web
```bash
cd apps/web
npm install
npm run dev
```
Buka browser di `http://localhost:5173`.

### 3. Menjalankan via Docker Compose
```bash
docker compose up --build
```
Web UI dapat diakses di port `8080`, API di port `8000`.

---

## 🧪 Pengujian & Kualitas Kode

```bash
cd apps/api
source .venv/bin/activate
# Lint & Format
ruff check .
ruff format --check .

# Type Check
mypy src/clipforge/core src/clipforge/jobs src/clipforge/db src/clipforge/api

# Test Suite
pytest -v
```

---

## 📄 Lisensi

MIT License.
