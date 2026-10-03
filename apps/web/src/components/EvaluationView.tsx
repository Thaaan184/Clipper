import React from "react";
import { Award, Database, ShieldAlert } from "lucide-react";

export const EvaluationView: React.FC = () => {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <Award className="w-5 h-5 text-orange-500" />
          <h3 className="font-bold text-white text-base">
            Golden Set Benchmark & Evaluation (Recall@K & Mean IoU)
          </h3>
        </div>
        <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-zinc-800 text-zinc-300">
          Strict Ground Truth Rules
        </span>
      </div>

      {/* Dataset Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* VOD 1 */}
        <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white text-xs">cLhVLsius9w</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30">
              2 HIGHLIGHTS
            </span>
          </div>
          <div className="text-[11px] text-zinc-400">Apex Legends Squad Combat</div>
          <div className="flex flex-col gap-1 text-[10px] text-zinc-400 pt-2 border-t border-zinc-900 font-mono">
            <div className="flex justify-between">
              <span>H1: Squad Wipe</span>
              <span className="text-white">5340s - 5384s (44s)</span>
            </div>
            <div className="flex justify-between">
              <span>H2: Team Fight</span>
              <span className="text-white">5780s - 5802s (22s)</span>
            </div>
          </div>
        </div>

        {/* VOD 2 */}
        <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white text-xs">RRJ2XZOkUOU</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-bold border border-amber-500/30">
              2 INCOMPLETE (TBD)
            </span>
          </div>
          <div className="text-[11px] text-zinc-400">Valorant Stream Clutches</div>
          <div className="flex flex-col gap-1 text-[10px] text-zinc-400 pt-2 border-t border-zinc-900 font-mono">
            <div className="flex justify-between">
              <span>H1: Aim Fail</span>
              <span className="text-amber-300">6503s - [TBD]</span>
            </div>
            <div className="flex justify-between">
              <span>H2: Angle Hold</span>
              <span className="text-amber-300">6576s - [TBD]</span>
            </div>
          </div>
        </div>

        {/* VOD 3 */}
        <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="font-bold text-white text-xs">3DvqXuKxDHk</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-bold">
              SOURCE ONLY
            </span>
          </div>
          <div className="text-[11px] text-zinc-400">Unlabelled Livestream VOD</div>
          <div className="text-[10px] text-zinc-500 pt-2 border-t border-zinc-900">
            Source VOD unlabelled. Menunggu anotasi manusia.
          </div>
        </div>
      </div>

      {/* Rules & Invariants Notice */}
      <div className="p-4 bg-zinc-950 rounded-xl border border-zinc-800 flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2 font-bold text-zinc-300">
          <Database className="w-4 h-4 text-orange-400" />
          <span>Ground Truth & Evaluation Invariants</span>
        </div>
        <ul className="list-disc list-inside text-zinc-400 flex flex-col gap-1 text-[11px]">
          <li>
            <strong className="text-zinc-200">Preservasi Label TBD:</strong> Timestamp end yang belum ditentukan pada VOD Valorant dipertahankan secara utuh tanpa inferensi tebakan.
          </li>
          <li>
            <strong className="text-zinc-200">Zero Fabricated Ground Truth:</strong> Tidak ada penambahan timestamp buatan atau pelabelan gameplay arbitrer sebagai positif.
          </li>
          <li>
            <strong className="text-zinc-200">Toleransi Match IoU:</strong> Hit dianggap valid jika kandidat bertumpang tindih dengan ground truth dengan $IoU \ge 0.3$ (atau $IoP \ge 0.5$ untuk end TBD).
          </li>
        </ul>
      </div>

      {/* Blocked State Notice */}
      <div className="p-4 bg-amber-950/20 border border-amber-900/40 rounded-xl flex items-start gap-3 text-xs text-amber-300">
        <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <div className="font-bold text-amber-200 uppercase tracking-wide">
            BLOCKED — OWNER INPUT REQUIRED
          </div>
          <div className="text-[11px] mt-1 text-amber-300/90 leading-relaxed">
            Label negatif ground truth (segmen purely talking-only tanpa gameplay action) belum disediakan oleh owner. Evaluasi kuantitatif empiris False Positive Rate / Rejection Precision untuk talking-only filter di-block hingga label negatif resmi diserahkan.
          </div>
        </div>
      </div>
    </div>
  );
};
