"""MixedWM38 npz 로더: multi-hot → 확정 어휘 리스트."""
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from ..constants import MIXEDWM38_LABEL_ORDER, MIXEDWM38_NPZ


def decode_multihot(row: np.ndarray) -> List[str]:
    """(8,) multi-hot → 패턴명 리스트. 전부 0이면 ['None']."""
    names = [MIXEDWM38_LABEL_ORDER[i] for i in range(len(row)) if row[i] == 1]
    return names if names else ["None"]


def load_mixedwm38(npz_path: Path = MIXEDWM38_NPZ) -> pd.DataFrame:
    """컬럼: id, source, wafer_map, labels(list[str]), lot(None)."""
    data = np.load(npz_path)
    maps, hots = data["arr_0"], data["arr_1"]
    records = {
        "id": [f"mixed38_{i}" for i in range(len(maps))],
        "source": "mixed38",
        "wafer_map": list(maps),
        "labels": [decode_multihot(h) for h in hots],
        "lot": None,
    }
    return pd.DataFrame(records)


def combo_key(labels: List[str]) -> str:
    """38조합 층화 분할용 키 (정렬된 라벨 조인)."""
    return "+".join(sorted(labels))
