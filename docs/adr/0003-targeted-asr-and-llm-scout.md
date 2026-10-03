# ADR 0003: Targeted ASR and Evidence-Based LLM Scout

- Status: accepted
- Date: 2026-10-04

## Konteks
Pada ClipForge v1, transkripsi penuh VOD 3+ jam memakan waktu sangat lama dan sering gagal pada VOD > 1.800 detik tanpa CC YouTube. LLM kemudian dipaksa membaca ribuan baris teks transkrip tanpa konteks akustik atau visual yang memadai.

## Keputusan
1. **Gate Heuristik Awal (Pre-ASR Gate)**:
   - Menerapkan filter deterministik untuk mendeteksi `talking_only` (speech_prob tinggi namun energi aksi dan chat rendah) dan `idle_screen` sebelum komputasi berat dijalankan.
   - Kandidat talking-only langsung di-reject pada konten gaming untuk menghemat biaya ASR dan LLM.
2. **Targeted ASR (Faster-Whisper)**:
   - Transkripsi hanya dijalankan pada jendela kandidat lolos gate ([start_s - 1.0s, end_s + 1.0s]).
   - Total audio yang ditranskrip berkurang drastis dari ratusan menit menjadi ~5-15 menit per VOD.
   - Menggunakan model Faster-Whisper dengan flag `word_timestamps=True` untuk menghasilkan timestamp presisi kata dalam koordinat waktu kanonik `source_s`.
3. **Evidence-Based LLM Scout**:
   - LLM bertindak sebagai *verifikator akhir*, bukan pembuat keputusan buta.
   - Prompt LLM menyertakan metrik terstruktur: skor sinyal puncak, rasio bicara, lonjakan chat, densitas onset, dan teks transkrip kata-kata jika ada.
   - Jika konfigurasi LLM (API key/Base URL) tidak diisi, sistem otomatis melakukan graceful fallback ke *Rule-Based Heuristic Scout* tanpa melempar kegagalan sistem.
4. **Sentence Boundary Snapping**:
   - Batas awal dan akhir klip disesuaikan dengan jeda antarkalimat dan batas kata transkrip dengan batasan pergeseran maksimal $[-3.0s, +1.5s]$ untuk start dan $[-1.0s, +3.0s]$ untuk end.

## Konsekuensi
- **Positif**:
  - Penurunan drastis waktu pemrosesan ASR (> 90% lebih cepat dibanding transkripsi penuh VOD).
  - Eliminasi halusinasi LLM pada momen aksi hening (misal: clutch tanpa kata-kata).
  - Konsistensi format kata untuk subtitle downstream Fase 5.
- **Negatif**:
  - Kata-kata di luar jendela kandidat tidak tersimpan (sesuai spesifikasi non-tujuan v2.0).
