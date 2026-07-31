"""렌더링 테스트: nearest 보간(중간색 미발생), 가변 크기, 종횡비."""
import numpy as np
import pytest

from wafervlm.constants import RENDER_PALETTE
from wafervlm.data.render import render_map


def test_nearest_no_intermediate_colors():
    arr = np.zeros((10, 10), dtype=np.int32)
    arr[2:8, 2:8] = 1
    arr[4:6, 4:6] = 2
    img = np.array(render_map(arr, size=430))
    palette = {tuple(c) for c in RENDER_PALETTE.values()}
    observed = {tuple(px) for px in img.reshape(-1, 3)}
    assert observed <= palette  # bilinear였으면 중간색이 생긴다


def test_aspect_ratio_preserved():
    arr = np.ones((30, 60), dtype=np.int32)
    img = render_map(arr, size=448)
    assert img.size == (448, 224)  # (w, h)


def test_variable_input_sizes():
    for shape in [(25, 27), (32, 29), (52, 52), (49, 39)]:
        arr = np.ones(shape, dtype=np.int32)
        img = render_map(arr)
        assert max(img.size) == 448


def test_rejects_non_2d():
    with pytest.raises(ValueError):
        render_map(np.ones((3, 3, 3), dtype=np.int32))
