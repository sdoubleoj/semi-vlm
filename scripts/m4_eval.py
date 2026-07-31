"""전체 평가 오케스트레이션: preds.jsonl → 스키마/분류/서술/calibration/hallucination 리포트."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from wafervlm.eval.calibration import calibration_report
from wafervlm.eval.hallucination import hallucination_report
from wafervlm.eval.metrics import classification_report, confusion_pairs, schema_compliance
from wafervlm.eval.parse import parse_all
from wafervlm.eval.spatial_score import spatial_report


def _fmt(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", required=True)
    ap.add_argument("--manifest", default="data/manifests/v1/test.parquet")
    ap.add_argument("--stats", default="data/stats.parquet")
    ap.add_argument("--track", default=None, help="main / hard_pairs 등 track 필터")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.preds, encoding="utf-8")]
    manifest = pd.read_parquet(args.manifest)
    manifest["labels"] = manifest["labels"].map(list)
    if args.track:
        keep = set(manifest.loc[manifest["track"] == args.track, "id"])
        rows = [r for r in rows if r["id"] in keep]

    truth = dict(zip(manifest["id"], manifest["labels"]))
    parsed = [p for p in parse_all(rows) if p["id"] in truth]

    y_true = [truth[p["id"]] for p in parsed]
    y_pred = [p["readout"].patterns if p["ok"] else [] for p in parsed]

    stats = pd.read_parquet(args.stats)
    report = {
        "preds": args.preds,
        "track": args.track or "all",
        "schema": schema_compliance(parsed),
        "classification": classification_report(y_true, y_pred),
        "confusion_top": confusion_pairs(y_true, y_pred),
        "spatial": spatial_report(parsed, stats),
        "calibration": calibration_report(parsed, truth),
        "hallucination": hallucination_report(parsed),
    }

    text = _fmt(report)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"-> {args.out}")
