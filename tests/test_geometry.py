"""합성 맵(정답을 아는 인공 패턴)에 대한 기하 판정 테스트 — 캡션 품질의 전제."""
import numpy as np

from wafervlm.data.geometry import extract_features


def _disk(size=52):
    yy, xx = np.mgrid[:size, :size]
    c = (size - 1) / 2
    r = np.sqrt((yy - c) ** 2 + (xx - c) ** 2) / c
    arr = np.zeros((size, size), dtype=np.int32)
    arr[r <= 1.0] = 1
    return arr, r


def test_edge_ring():
    arr, r = _disk()
    arr[(r >= 0.85) & (r <= 1.0)] = 2
    f = extract_features(arr)
    assert f["zone"] == "edge"
    assert f["shape"] == "ring"
    assert f["angular_coverage"] > 0.9
    assert f["clock"] == "전방위"


def test_center_cluster():
    arr, r = _disk()
    arr[r <= 0.2] = 2
    f = extract_features(arr)
    assert f["zone"] == "center"
    assert f["frac_inner"] == 1.0
    assert f["shape"] in ("cluster", "blob")


def test_scratch_line():
    arr, _ = _disk()
    for i in range(10, 40):
        arr[i, i] = 2
        arr[i, i + 1] = 2
    f = extract_features(arr)
    assert f["linearity"] > 0.92
    assert f["shape"] == "line"


def test_local_cluster_offcenter():
    arr, r = _disk()
    yy, xx = np.mgrid[: arr.shape[0], : arr.shape[1]]
    blob = np.sqrt((yy - 15) ** 2 + (xx - 35) ** 2) <= 4
    arr[blob & (arr > 0)] = 2
    f = extract_features(arr)
    assert f["shape"] == "cluster"
    assert f["largest_cluster_frac"] > 0.9
    assert f["clock"] != "전방위"  # 방향성이 있어야 함


def test_random_scatter():
    arr, _ = _disk()
    rng = np.random.RandomState(0)
    die = np.argwhere(arr == 1)
    picks = die[rng.choice(len(die), 60, replace=False)]
    for y, x in picks:
        arr[y, x] = 2
    f = extract_features(arr)
    assert f["shape"] == "scatter"


def test_no_defect():
    arr, _ = _disk()
    f = extract_features(arr)
    assert f["n_defect"] == 0
    assert f["shape"] == "none"
    assert f["defect_ratio"] == 0.0


def test_near_full():
    arr, r = _disk()
    arr[(arr == 1) & (r <= 0.9)] = 2
    f = extract_features(arr)
    assert f["defect_ratio"] > 0.55
    assert f["zone"] == "full"
