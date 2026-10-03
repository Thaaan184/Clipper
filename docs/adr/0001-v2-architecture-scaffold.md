# ADR 0001: ClipForge v2 Architecture & Scaffold

- Status: accepted
- Date: 2026-10-04

## Konteks
ClipForge v1 bekerja dengan paradigma *transcript-first*, memiliki defisiensi struktural pada video gaming tanpa CC, drift subtitle akibat range cut tanpa re-sync, dan ketiadaan checkpoint/recovery saat server restart. Rencana v2 (`PLAN.md`) menetapkan rebuild arsitektur total dengan pendekatan *signal-first, LLM-last*.

## Opsi yang dipertimbangkan
1. In-place refactoring v1 file demi file di `main`.
2. Monorepo scaffold modular (`apps/api` dan `apps/web`) dengan state machine, checkpoint atomic, dan database migrator SQL independen, sementara kode v1 diarsipkan di `legacy/v1`.

## Keputusan
Memilih Opsi 2:
- Memisahkan arsitektur ke monorepo `apps/api` (FastAPI + src-layout) dan `apps/web` (React 18 + TS strict + Vite + Tailwind).
- Kode lama diarsipkan permanen di branch `legacy/v1` dan tag `legacy-v1-final`.
- Memperkenalkan pipeline state machine dengan dukungan checkpoint atomic (`.checkpoint/{stage}.json`), idempotency (skip bila `input_hash` cocok), dan auto-recovery job yatim saat server startup.
- Endpoint API berstandar RFC 7807 (`application/problem+json`) dan SSE stream dengan heartbeat 15s dan dukungan replay `Last-Event-ID`.

## Konsekuensi
- Positif: Sistem deterministik, terisolasi per stage, tahan crash server, dan mudah diuji secara modular.
- Negatif: Memerlukan penulisan ulang modul pipeline secara terpisah per fase (Ingest, Signal, Fusion, Scout, Render).
- Cara Rollback: `git revert` merge PR reset `main`.
