import React from "react";
import { Award, Database, ShieldAlert } from "lucide-react";

export const EvaluationView: React.FC = () => {
  return (
    <div className="marked-frame border border-line bg-surface p-6 shadow-2xl flex flex-col gap-6">
      <i className="crop-mark crop-tl" />
      <i className="crop-mark crop-tr" />
      <i className="crop-mark crop-bl" />
      <i className="crop-mark crop-br" />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-action" />
          <h3 className="font-extrabold text-copy text-base uppercase tracking-wider">
            GOLDEN SET BENCHMARK & EVALUASI EMPIRIS
          </h3>
        </div>
        <span className="text-xs px-2.5 py-0.5 border border-line bg-card font-mono text-muted">
          STRICT GROUND TRUTH RULES
        </span>
      </div>

      {/* Dataset Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* VOD 1 */}
        <div className="marked-card bg-card p-4 border border-line flex flex-col gap-2 relative">
          <i className="crop-mark crop-tl" />
          <i className="crop-mark crop-tr" />
          <i className="crop-mark crop-bl" />
          <i className="crop-mark crop-br" />

          <div className="flex items-center justify-between">
            <span className="font-bold text-copy text-xs font-mono">cLhVLsius9w</span>
            <span className="text-[10px] px-2 py-0.5 border border-green-500/40 bg-green-500/10 text-green-400 font-bold uppercase">
              2 HIGHLIGHTS
            </span>
          </div>
          <div className="text-[11px] text-muted">Apex Legends Squad Combat (Full Stream)</div>
          <div className="flex flex-col gap-1 text-[10px] text-muted pt-2 border-t border-line font-mono">
            <div className="flex justify-between">
              <span>H1: Squad Wipe</span>
              <span className="text-copy font-bold">5340s - 5384s (44s)</span>
            </div>
            <div className="flex justify-between">
              <span>H2: Team Fight</span>
              <span className="text-copy font-bold">5780s - 5802s (22s)</span>
            </div>
          </div>
        </div>

        {/* VOD 2 */}
        <div className="marked-card bg-card p-4 border border-line flex flex-col gap-2 relative">
          <i className="crop-mark crop-tl" />
          <i className="crop-mark crop-tr" />
          <i className="crop-mark crop-bl" />
          <i className="crop-mark crop-br" />

          <div className="flex items-center justify-between">
            <span className="font-bold text-copy text-xs font-mono">RRJ2XZOkUOU</span>
            <span className="text-[10px] px-2 py-0.5 border border-amber-500/40 bg-amber-500/10 text-amber-400 font-bold uppercase">
              2 INCOMPLETE (TBD)
            </span>
          </div>
          <div className="text-[11px] text-muted">Valorant Stream Clutches</div>
          <div className="flex flex-col gap-1 text-[10px] text-muted pt-2 border-t border-line font-mono">
            <div className="flex justify-between">
              <span>H1: Aim Fail</span>
              <span className="text-amber-300 font-bold">6503s - [TBD]</span>
            </div>
            <div className="flex justify-between">
              <span>H2: Angle Hold</span>
              <span className="text-amber-300 font-bold">6576s - [TBD]</span>
            </div>
          </div>
        </div>

        {/* VOD 3 */}
        <div className="marked-card bg-card p-4 border border-line flex flex-col gap-2 relative">
          <i className="crop-mark crop-tl" />
          <i className="crop-mark crop-tr" />
          <i className="crop-mark crop-bl" />
          <i className="crop-mark crop-br" />

          <div className="flex items-center justify-between">
            <span className="font-bold text-copy text-xs font-mono">3DvqXuKxDHk</span>
            <span className="text-[10px] px-2 py-0.5 border border-line bg-surface text-muted font-bold uppercase">
              SOURCE ONLY
            </span>
          </div>
          <div className="text-[11px] text-muted">Unlabelled Livestream VOD</div>
          <div className="text-[10px] text-muted pt-2 border-t border-line">
            Source VOD unlabelled. Menunggu anotasi manusia resmi.
          </div>
        </div>
      </div>

      {/* Rules & Invariants Notice */}
      <div className="p-4 bg-card border border-line flex flex-col gap-2 text-xs">
        <div className="flex items-center gap-2 font-bold text-copy uppercase tracking-wider">
          <Database className="w-4 h-4 text-action" />
          <span>GROUND TRUTH & EVALUATION INVARIANTS</span>
        </div>
        <ul className="list-disc list-inside text-muted flex flex-col gap-1 text-[11px]">
          <li>
            <strong className="text-copy">Preservasi Label TBD:</strong> Timestamp end yang belum ditentukan pada VOD Valorant dipertahankan utuh tanpa rekayasa.
          </li>
          <li>
            <strong className="text-copy">Zero Fabricated Ground Truth:</strong> Tidak ada penambahan timestamp buatan atau pelabelan gameplay arbitrer sebagai positif.
          </li>
          <li>
            <strong className="text-copy">Toleransi Match IoU:</strong> Hit dianggap valid jika kandidat bertumpang tindih dengan ground truth dengan IoU &ge; 0.3.
          </li>
        </ul>
      </div>

      {/* Blocked State Notice */}
      <div className="p-4 bg-amber-950/20 border border-amber-900/40 flex items-start gap-3 text-xs text-amber-300">
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
