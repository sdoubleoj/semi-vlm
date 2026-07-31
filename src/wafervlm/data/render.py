"""waferMap 배열 → VLM 입력 PNG. nearest 업스케일로 die 경계 보존 (bilinear 금지)."""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..constants import RENDER_PALETTE, RENDER_SIZE


def render_map(arr: np.ndarray, size: int = RENDER_SIZE) -> Image.Image:
    """0/1/2 웨이퍼맵을 RGB 이미지로 렌더링.

    가로세로 비율을 유지하며 긴 변을 `size`로 nearest 업스케일한다.
    두 데이터셋(가변 크기 / 52x52)에 동일 컬러맵·해상도를 적용해
    분포 차이를 지름길로 학습하는 것을 방지한다.
    """
    if arr.ndim != 2:
        raise ValueError(f"expected 2D wafer map, got shape {arr.shape}")
    h, w = arr.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for value, color in RENDER_PALETTE.items():
        rgb[arr == value] = color
    img = Image.fromarray(rgb)
    scale = size / max(h, w)
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    return img.resize(new_size, resample=Image.NEAREST)
