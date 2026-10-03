"""Evaluation runner for measuring candidate detector recall and precision against Golden Set."""

import argparse
import json
import sys
from pathlib import Path

# Add apps/api/src to path if run standalone
api_src = Path(__file__).resolve().parent.parent / "apps" / "api" / "src"
if str(api_src) not in sys.path:
    sys.path.insert(0, str(api_src))

from clipforge.eval.evaluate import evaluate_candidates_against_ground_truth

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate ClipForge v2 candidates against Golden Set"
    )
    parser.add_argument(
        "--video-id", type=str, required=True, help="YouTube video ID (e.g. cLhVLsius9w)"
    )
    parser.add_argument(
        "--candidates-file",
        type=str,
        required=True,
        help="Path to candidates JSON or timeline JSON",
    )
    parser.add_argument(
        "--out-report", type=str, default=None, help="Optional output report JSON path"
    )
    args = parser.parse_args()

    golden_file = GOLDEN_DIR / f"{args.video_id}.json"
    if not golden_file.exists():
        raise FileNotFoundError(f"Golden set file not found: {golden_file}")

    golden_data = json.loads(golden_file.read_text(encoding="utf-8"))
    highlights = golden_data.get("highlights", [])

    cands_path = Path(args.candidates_file)
    cands_raw = json.loads(cands_path.read_text(encoding="utf-8"))
    if isinstance(cands_raw, dict) and "candidates" in cands_raw:
        candidates = cands_raw["candidates"]
    elif isinstance(cands_raw, list):
        candidates = cands_raw
    else:
        raise ValueError("Unrecognized candidates format")

    report = evaluate_candidates_against_ground_truth(candidates, highlights)
    print(f"=== Golden Set Evaluation: {args.video_id} ===")
    print(f"Total Ground Truth Positives: {report['total_ground_truth']}")
    for k in (3, 5, 10):
        print(
            f"Recall@{k}: {report['recall_at_k'][k] * 100:.1f}% ({report['hits_at_k'][k]}/{report['total_ground_truth']})"
        )
    print(f"Mean IoU: {report['mean_iou']:.3f}")
    print("\nMatches:")
    for m in report["matches"]:
        status = f"HIT (Rank {m['matched_rank']})" if m["matched"] else "MISS"
        print(
            f"  [{status}] {m['note'] or m['description']}: GT={m['ground_truth']} -> Found={m['matched_window']} (IoU: {m['best_iou']})"
        )

    if args.out_report:
        out_path = Path(args.out_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to: {out_path}")


if __name__ == "__main__":
    main()
