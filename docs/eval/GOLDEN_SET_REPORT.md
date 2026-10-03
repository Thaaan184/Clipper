# Golden Set Evaluation & Benchmark Report (ClipForge v2)

## 1. Ground Truth Rules & Invariants

Evaluasi detektor kandidat ClipForge v2 berpedoman pada aturan ketat ground truth (tidak boleh diubah tanpa persetujuan eksplisit owner):

1. **Zero Fabrication**: Tidak ada penambahan timestamp buatan, inferensi end timestamp yang hilang, atau pelabelan gameplay arbitrer sebagai positif.
2. **Preservasi Incomplete Labels (TBD)**: Dua sampel Valorant pada video `RRJ2XZOkUOU` yang belum memiliki end timestamp tetap dipertahankan sebagai `null / TBD` (tidak ditebak).
3. **Source-Only VOD**: VOD ketiga (`3DvqXuKxDHk`) berstatus source VOD unlabelled dan tidak dievaluasi sebagai ground truth.
4. **Negative Samples Status**:
   ```
   BLOCKED — OWNER INPUT REQUIRED
   ```
   Evaluasi False Positive Rate (FPR) dan Rejection Precision empiris untuk filter *talking-only* ditahan sampai dataset negatif ground truth resmi diserahkan oleh owner.

---

## 2. Dataset Inventory

| Video ID | Game | Genre | Highlight Count | Status Ground Truth |
| :--- | :--- | :--- | :---: | :--- |
| `cLhVLsius9w` | Apex Legends | Gaming | 2 Positif | Complete (`5340-5384s`, `5780-5802s`) |
| `RRJ2XZOkUOU` | Valorant | Gaming | 2 Positif | Partial (`6503s-TBD`, `6576s-TBD`) |
| `3DvqXuKxDHk` | - | Gaming | 0 | Source VOD Only (Unlabelled) |

---

## 3. Metodologi Evaluasi

### 3.1. Recall@K
Proporsi highlight ground truth yang tertangkap dalam $K$ kandidat teratas:
$$\text{Recall@K} = \frac{\sum_{i=1}^{M} \mathbb{I}(\text{hit in top } K)}{M}$$
dengan kriteria hit:
- Sampel lengkap: $\text{IoU} \ge 0.30$ antara window kandidat $[s_c, e_c]$ dan ground truth $[s_{gt}, e_{gt}]$.
- Sampel incomplete (end = TBD): Titik mulai kandidat berada dalam rentang toleransi $[s_{gt} - 10\text{s}, s_{gt} + 30\text{s}]$ dan proporsi irisan terhadap durasi kandidat ($\text{IoP}$) $\ge 0.50$.

### 3.2. Mean IoU
Rata-rata Intersection over Union untuk semua ground truth yang berhasil dicocokkan (hit) oleh kandidat.

---

## 4. Hasil Verifikasi Modul Evaluasi

Rangkaian test evaluasi otomatis teruji pada unit test `tests/unit/test_evaluation_metrics.py`:
- `test_evaluate_candidates_exact_hit`: Recall@3 = 100%, Mean IoU = 1.000 (Pass).
- `test_evaluate_candidates_tbd_end`: Deteksi presisi start $6503\text{s}$ pada incomplete label tanpa menebak boundary akhir (Pass).
