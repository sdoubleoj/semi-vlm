"""Hard pair 마이닝 CLI: stats.parquet → hard_pairs parquet."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from wafervlm.data.hard_pairs import PAIRS, mine_hard_pairs

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default="data/stats.parquet")
    ap.add_argument("--pairs", nargs="*", default=list(PAIRS))
    ap.add_argument("--per-pair-cap", type=int, default=2000)
    ap.add_argument("--out", default="data/hard_pairs/v1.parquet")
    args = ap.parse_args()

    stats = pd.read_parquet(args.stats)
    stats["labels"] = stats["labels"].map(list)
    hp = mine_hard_pairs(stats, pairs=args.pairs, per_pair_cap=args.per_pair_cap)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    hp.to_parquet(args.out, index=False)
    print(hp.groupby("pair").size())
    print(f"{len(hp):,} hard-pair records -> {args.out}")
