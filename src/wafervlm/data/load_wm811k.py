"""WM811K.pkl 로더: 라벨 정규화 + 미라벨 분리 + 이상 맵 필터."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from ..constants import RAW_LABEL_MAP, WM811K_PKL

MIN_MAP_SIDE = 8          # 한 변이 이보다 작은 맵은 제외
MIN_DIE_COUNT = 100       # die(값>0) 수가 이보다 적은 맵은 제외


def _norm_failure_type(v: object) -> Optional[str]:
    """원본 failureType(문자열 또는 [0 0] ndarray) → 확정 어휘. 미라벨이면 None 반환."""
    if isinstance(v, str):
        return RAW_LABEL_MAP.get(v)
    if isinstance(v, np.ndarray):
        if v.size == 0:
            return None
        flat = v.ravel()
        if isinstance(flat[0], str):
            return RAW_LABEL_MAP.get(str(flat[0]))
        return None  # [0 0] 등 숫자 배열 = 미라벨
    return None


def load_wm811k(pkl_path: Path = WM811K_PKL) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """(labeled_df, unlabeled_df) 반환.

    labeled_df 컬럼: id, source, wafer_map, labels(list[str]), lot
    unlabeled_df 컬럼: id, source, wafer_map, lot  (Auto-Labeling 대상 풀)
    """
    df = pd.read_pickle(pkl_path)
    label = df["failureType"].map(_norm_failure_type)

    shapes = df["waferMap"].map(lambda m: m.shape)
    die_counts = df["waferMap"].map(lambda m: int((m > 0).sum()))
    valid = (
        shapes.map(lambda s: min(s) >= MIN_MAP_SIDE)
        & (die_counts >= MIN_DIE_COUNT)
    )

    base = pd.DataFrame(
        {
            "id": [f"wm811k_{i}" for i in df.index],
            "source": "wm811k",
            "wafer_map": df["waferMap"],
            "lot": df["lotName"].astype(str),
            "_label": label,
            "_valid": valid,
        }
    )

    labeled = base[base["_label"].notna() & base["_valid"]].copy()
    labeled["labels"] = labeled["_label"].map(lambda s: [s])
    unlabeled = base[base["_label"].isna() & base["_valid"]].copy()

    labeled = labeled.drop(columns=["_label", "_valid"]).reset_index(drop=True)
    unlabeled = unlabeled.drop(columns=["_label", "_valid"]).reset_index(drop=True)
    return labeled, unlabeled
