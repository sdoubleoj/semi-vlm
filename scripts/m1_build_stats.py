"""전 맵 기하 통계 추출 → data/stats.parquet (캡션·hard pair·평가 채점 공용 기반)."""
import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from tqdm import tqdm

from wafervlm.data.geometry import extract_features
from wafervlm.data.load_mixedwm38 import load_mixedwm38
from wafervlm.data.load_wm811k import load_wm811k


def _one(item):
    sid, arr, labels = item
    feats = extract_features(arr)
    feats["id"] = sid
    feats["labels"] = labels
    return feats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--out", default="data/stats.parquet")
    args = ap.parse_args()

    labeled, _ = load_wm811k()
    mixed = load_mixedwm38()
    items = [
        (r["id"], r["wafer_map"], list(r["labels"]))
        for df in (labeled, mixed)
        for _, r in df.iterrows()
    ]

    with Pool(args.workers) as pool:
        rows = list(
            tqdm(pool.imap_unordered(_one, items, chunksize=256), total=len(items))
        )

    stats = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    stats.to_parquet(args.out, index=False)
    print(f"stats for {len(stats):,} maps -> {args.out}")
