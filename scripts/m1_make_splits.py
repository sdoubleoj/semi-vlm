"""분할 CLI: raw_index + hard pairs → train/val/test manifest (+ track 컬럼)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from wafervlm.data.split import (
    make_manifest,
    save_splits,
    split_mixed38,
    split_wm811k,
    wm811k_derived_mask,
)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-index", default="data/images/raw_index.parquet")
    ap.add_argument("--hard-pairs", default="data/hard_pairs/v1.parquet")
    ap.add_argument("--image-dir", default="data/images/v1")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data/manifests/v1")
    args = ap.parse_args()

    index = pd.read_parquet(args.raw_index)
    index = index[index["labels"].notna()].copy()
    index["labels"] = index["labels"].map(list)

    derived = wm811k_derived_mask(index)
    if derived.any():
        print(f"MixedWM38 단독 Random/Near-Full {int(derived.sum()):,}건 제외 (WM811K 유래 — 누수 방지)")
        index = index[~derived].copy()

    wm = split_wm811k(index[index["source"] == "wm811k"], salt=args.seed)
    mx = split_mixed38(index[index["source"] == "mixed38"], salt=args.seed)
    manifest = make_manifest(pd.concat([wm, mx], ignore_index=True), args.image_dir)

    # hard pair id는 test에서 별도 track으로 표시 (구분 능력 전용 평가셋)
    manifest["track"] = "main"
    if Path(args.hard_pairs).exists():
        hard_ids = set(pd.read_parquet(args.hard_pairs)["id"])
        is_hard = manifest["id"].isin(hard_ids)
        manifest.loc[is_hard & (manifest["split"] == "test"), "track"] = "hard_pairs"

    n_train, n_val, n_test = save_splits(manifest, args.out)
    print(f"train {n_train:,} / val {n_val:,} / test {n_test:,} -> {args.out}")
    print(manifest.groupby(["split", "track"]).size())
