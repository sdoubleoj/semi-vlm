"""SFT 데이터셋 생성 CLI.

예:
  python scripts/m2_build_sft.py --tasks A:30 B:30 C:20 D:15 E:5 \
      --think-mode reasoning --cap-none 20000 --out data/sft/v1_think
"""
import argparse
import json
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from wafervlm.data.build_sft import build_samples, write_jsonl

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default="data/manifests/v1")
    ap.add_argument("--stats", default="data/stats.parquet")
    ap.add_argument("--hard-pairs", default="data/hard_pairs/v1.parquet")
    ap.add_argument("--tasks", nargs="+", default=["A:30", "B:30", "C:20", "D:15", "E:5"])
    ap.add_argument("--think-mode", choices=["reasoning", "empty"], default="reasoning")
    ap.add_argument("--cap-none", type=int, default=20000,
                    help="train의 None 클래스 상한 (불균형 대응 다운샘플링)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ratios = {}
    for spec in args.tasks:
        k, v = spec.split(":")
        ratios[k] = int(v)

    stats = pd.read_parquet(args.stats)
    stats["labels"] = stats["labels"].map(list)
    hard = pd.read_parquet(args.hard_pairs) if Path(args.hard_pairs).exists() else None

    meta = {"tasks": ratios, "think_mode": args.think_mode, "cap_none": args.cap_none}
    for split in ("train", "val"):
        manifest = pd.read_parquet(f"{args.manifest}/{split}.parquet")
        manifest["labels"] = manifest["labels"].map(list)
        if split == "train" and args.cap_none:
            is_none = manifest["labels"].map(lambda l: l == ["None"])
            none_part = manifest[is_none]
            if len(none_part) > args.cap_none:
                # 결정적 다운샘플: id 해시 정렬 상위 cap_none
                keep = none_part.assign(
                    _h=none_part["id"].map(lambda s: zlib.crc32(s.encode()))
                ).nsmallest(args.cap_none, "_h").drop(columns="_h")
                manifest = pd.concat([manifest[~is_none], keep], ignore_index=True)
        samples = build_samples(manifest, stats, hard, ratios, args.think_mode)
        write_jsonl(samples, f"{args.out}/{split}.jsonl")
        meta[f"n_{split}"] = len(samples)
        print(f"{split}: {len(samples):,} samples")

    Path(args.out, "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"-> {args.out}")
