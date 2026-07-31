"""전량 사전 렌더링 (1회성 — CPU 32코어 풀가동 OK).

라벨된 WM811K + MixedWM38 전체를 PNG로 저장하고 raw_index.parquet를 만듦.
학습 중 on-the-fly 렌더링 금지 원칙의 구현부.
"""
import argparse
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from tqdm import tqdm

from wafervlm.data.load_mixedwm38 import load_mixedwm38
from wafervlm.data.load_wm811k import load_wm811k
from wafervlm.data.render import render_map

_out_dir = None
_size = None


def _init(out_dir: str, size: int) -> None:
    global _out_dir, _size
    _out_dir, _size = out_dir, size


def _map_hash(arr) -> int:
    """맵 내용 해시 (shape 포함) — 완전중복 맵의 split 동거 보장용."""
    a = np.ascontiguousarray(arr, dtype=np.uint8)
    return zlib.crc32(f"{a.shape}".encode() + a.tobytes())


def _render_one(item):
    sid, arr = item
    path = Path(_out_dir) / f"{sid}.png"
    if not path.exists():
        render_map(arr, size=_size).save(path)
    return sid


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=448)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--out", default="data/images/v1")
    ap.add_argument("--include-unlabeled", action="store_true",
                    help="미라벨 638k도 렌더링 (Auto-Labeling 실전 시)")
    args = ap.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)

    labeled, unlabeled = load_wm811k()
    mixed = load_mixedwm38()
    frames = [labeled, mixed] + ([unlabeled] if args.include_unlabeled else [])

    index_rows = []
    for df in frames:
        items = list(zip(df["id"], df["wafer_map"]))
        with Pool(args.workers, initializer=_init, initargs=(args.out, args.size)) as pool:
            for _ in tqdm(pool.imap_unordered(_render_one, items, chunksize=256),
                          total=len(items), desc=str(df["source"].iloc[0])):
                pass
        index_rows.append(
            pd.DataFrame(
                {
                    "id": df["id"],
                    "source": df["source"],
                    "labels": df["labels"].map(list) if "labels" in df else None,
                    "lot": df["lot"],
                    "map_hash": [_map_hash(a) for a in df["wafer_map"]],
                    "image_path": df["id"].map(lambda i: f"{args.out}/{i}.png"),
                }
            )
        )

    index = pd.concat(index_rows, ignore_index=True)
    index_path = Path(args.out).parent / "raw_index.parquet"
    index.to_parquet(index_path, index=False)
    print(f"rendered {len(index):,} maps -> {args.out}, index -> {index_path}")
