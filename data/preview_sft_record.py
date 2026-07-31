"""특정 id의 M2 SFT 레코드를 즉석 생성해 JSON으로 출력.

사용: python data/preview_sft_record.py [--id wm811k_666]
(m2_build_sft.py 실행 전에 개별 샘플의 레코드 구조를 미리 확인하는 용도)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from wafervlm.data.build_sft import build_samples

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="wm811k_666")
    ap.add_argument("--think-mode", default="reasoning", choices=["reasoning", "empty"])
    args = ap.parse_args()

    idx = pd.read_parquet(ROOT / "data/images/raw_index.parquet")
    st = pd.read_parquet(ROOT / "data/stats.parquet")
    hp_path = ROOT / "data/hard_pairs/v1.parquet"
    hp = pd.read_parquet(hp_path) if hp_path.exists() else None

    row = idx[idx["id"] == args.id].copy()
    if row.empty:
        sys.exit(f"id '{args.id}' 가 raw_index에 없습니다")
    row["labels"] = row["labels"].map(list)

    samples = build_samples(
        manifest=row, stats=st, hard_pairs=hp,
        ratios={"A": 30, "B": 30, "C": 20, "D": 15, "E": 5},
        think_mode=args.think_mode,
    )
    print(f"# {args.id} -> 레코드 {len(samples)}개\n")
    for s in samples:
        print(json.dumps(s, ensure_ascii=False, indent=2))
