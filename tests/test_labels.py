"""라벨 매핑·어휘 고정 테스트: 데이터셋 표기 ↔ 확정 어휘 불일치를 여기서 잡는다."""
import numpy as np

from wafervlm.constants import MIXEDWM38_LABEL_ORDER, PATTERNS, RAW_LABEL_MAP
from wafervlm.data.load_mixedwm38 import combo_key, decode_multihot
from wafervlm.data.load_wm811k import _norm_failure_type


def test_patterns_fixed_9():
    assert PATTERNS == (
        "Center", "Donut", "Edge-Loc", "Edge-Ring", "Loc",
        "Near-Full", "Scratch", "Random", "None",
    )


def test_raw_map_covers_wm811k_notation():
    # 데이터셋 원본 표기 → 확정 어휘 (none/Near-full 정규화가 핵심)
    assert RAW_LABEL_MAP["none"] == "None"
    assert RAW_LABEL_MAP["Near-full"] == "Near-Full"
    assert set(RAW_LABEL_MAP.values()) == set(PATTERNS)


def test_norm_failure_type():
    assert _norm_failure_type("Edge-Ring") == "Edge-Ring"
    assert _norm_failure_type("none") == "None"
    assert _norm_failure_type(np.array(["Near-full"])) == "Near-Full"
    assert _norm_failure_type(np.array([0, 0])) is None  # 미라벨


def test_mixedwm38_decode():
    assert MIXEDWM38_LABEL_ORDER[0] == "Center"
    assert MIXEDWM38_LABEL_ORDER[5] == "Near-Full"
    hot = np.array([1, 0, 1, 0, 0, 0, 1, 0])
    assert decode_multihot(hot) == ["Center", "Edge-Loc", "Scratch"]
    assert decode_multihot(np.zeros(8, dtype=int)) == ["None"]


def test_combo_key_sorted():
    assert combo_key(["Scratch", "Center"]) == "Center+Scratch"
