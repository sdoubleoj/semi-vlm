"""데이터 분할: WM811K는 lot 그룹 분할(누수 방지), MixedWM38은 38조합 층화 분할.

CRC32 해시 기반 결정적 분할 — 시드(salt)만 고정하면 어디서 돌려도 동일 결과.
"""
from __future__ import annotations

import zlib
from typing import Tuple

import pandas as pd

from .load_mixedwm38 import combo_key

VAL_PCT = 10
TEST_PCT = 10


def _bucket(key: str, salt: int) -> int:
    return zlib.crc32(f"{salt}:{key}".encode()) % 100


def _assign(bucket: int) -> str:
    if bucket < TEST_PCT:
        return "test"
    if bucket < TEST_PCT + VAL_PCT:
        return "val"
    return "train"


def split_wm811k(df: pd.DataFrame, salt: int = 42) -> pd.DataFrame:
    """lot 단위 그룹 분할 — 동일 lot의 웨이퍼가 두 split에 걸치지 않는다."""
    out = df.copy()
    out["split"] = out["lot"].map(lambda lot: _assign(_bucket(str(lot), salt)))
    _assert_no_lot_leak(out)
    return out


def split_mixed38(df: pd.DataFrame, salt: int = 42) -> pd.DataFrame:
    """맵 내용 해시 버킷 분할 — 완전중복 맵(1,024건 확인)이 라벨과 무관하게
    항상 같은 split에 모인다 (id 기준이면 중복이 train/test에 갈라져 누수).
    해시가 균등하므로 조합 클래스별 비율도 기대값으로 유지된다."""
    out = df.copy()
    out["split"] = [_assign(_bucket(str(h), salt)) for h in out["map_hash"]]
    return out


def wm811k_derived_mask(df: pd.DataFrame) -> pd.Series:
    """MixedWM38 단독 Random/Near-Full 판별 — 수량 지문(866/149)이 WM811K와
    일치해 동일 웨이퍼 유래로 판단, 누수 방지 위해 전 용도(학습/평가)에서 제외."""
    singles = df["labels"].map(lambda l: list(l) in (["Random"], ["Near-Full"]))
    return (df["source"] == "mixed38") & singles


def _assert_no_lot_leak(df: pd.DataFrame) -> None:
    by_split = {
        s: set(df.loc[df["split"] == s, "lot"]) for s in ("train", "val", "test")
    }
    assert not (by_split["train"] & by_split["test"]), "lot leak: train ∩ test"
    assert not (by_split["train"] & by_split["val"]), "lot leak: train ∩ val"
    assert not (by_split["val"] & by_split["test"]), "lot leak: val ∩ test"


def summarize_split(df: pd.DataFrame) -> pd.DataFrame:
    """split × 라벨 조합 분포 요약 (리포트용)."""
    tmp = df.copy()
    tmp["combo"] = tmp["labels"].map(combo_key)
    return tmp.groupby(["split", "combo"]).size().unstack(fill_value=0).T


def make_manifest(df: pd.DataFrame, image_dir: str) -> pd.DataFrame:
    """학습/평가 공용 manifest 스키마로 정리 (wafer_map 제외 — parquet 저장용)."""
    out = pd.DataFrame(
        {
            "id": df["id"],
            "source": df["source"],
            "labels": df["labels"].map(list),
            "lot": df["lot"],
            "split": df["split"],
            "image_path": df["id"].map(lambda i: f"{image_dir}/{i}.png"),
        }
    )
    return out


def load_split(manifest_dir: str, split: str) -> pd.DataFrame:
    return pd.read_parquet(f"{manifest_dir}/{split}.parquet")


def save_splits(manifest: pd.DataFrame, out_dir: str) -> Tuple[int, int, int]:
    from pathlib import Path

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    counts = []
    for split in ("train", "val", "test"):
        part = manifest[manifest["split"] == split].reset_index(drop=True)
        part.to_parquet(f"{out_dir}/{split}.parquet", index=False)
        counts.append(len(part))
    return tuple(counts)  # type: ignore[return-value]
