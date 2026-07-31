"""SFT 샘플 생성 테스트: 라벨-캡션-스키마 정합성, think 모드, 관측/원인 분리."""
import numpy as np
import pandas as pd
import pytest

from wafervlm.data.build_sft import build_readout, build_samples
from wafervlm.data.geometry import extract_features
from wafervlm.eval.hallucination import scan_text
from wafervlm.eval.parse import parse_prediction


@pytest.fixture(scope="module")
def ring_fixture():
    size = 52
    yy, xx = np.mgrid[:size, :size]
    c = (size - 1) / 2
    r = np.sqrt((yy - c) ** 2 + (xx - c) ** 2) / c
    arr = np.zeros((size, size), dtype=np.int32)
    arr[r <= 1.0] = 1
    arr[(r >= 0.85) & (r <= 1.0)] = 2
    feats = extract_features(arr)
    feats["id"] = "t_0"
    feats["labels"] = ["Edge-Ring"]
    manifest = pd.DataFrame(
        [{"id": "t_0", "source": "test", "labels": ["Edge-Ring"],
          "lot": "L1", "split": "train", "image_path": "data/images/v1/t_0.png"}]
    )
    stats = pd.DataFrame([feats])
    return manifest, stats


def test_readout_matches_geometry(ring_fixture):
    _, stats = ring_fixture
    feats = stats.iloc[0].to_dict()
    r = build_readout("t_0", ["Edge-Ring"], feats)
    assert r.patterns == ["Edge-Ring"]
    assert r.spatial.zone == "edge"
    assert r.spatial.shape == "ring"
    assert scan_text(r.description) == []  # 관측/원인 분리: 원인 어휘 금지


def test_build_samples_reasoning_mode(ring_fixture):
    manifest, stats = ring_fixture
    samples = build_samples(manifest, stats, None, {"A": 100}, think_mode="reasoning")
    assert len(samples) == 1
    assistant = samples[0]["messages"][-1]["content"]
    assert assistant.startswith("<think>\n관찰:")
    parsed = parse_prediction(assistant)  # <think> 제거 후 스키마 파싱까지 왕복
    assert parsed["ok"], parsed["error"]
    assert parsed["readout"].patterns == ["Edge-Ring"]


def test_build_samples_empty_think(ring_fixture):
    manifest, stats = ring_fixture
    samples = build_samples(manifest, stats, None, {"A": 100}, think_mode="empty")
    assistant = samples[0]["messages"][-1]["content"]
    assert assistant.startswith("<think>\n\n</think>")
    assert parse_prediction(assistant)["ok"]


def test_hard_pair_generates_task_c(ring_fixture):
    manifest, stats = ring_fixture
    hard = pd.DataFrame(
        [{"id": "t_0", "pair": "edgeloc-edgering", "label": "Edge-Ring",
          "other": "Edge-Loc", "rationale": "각도 점유율이 둘레 전반 → Edge-Ring."}]
    )
    samples = build_samples(manifest, stats, hard, {"A": 80, "C": 20})
    tasks = {s["task"] for s in samples}
    assert "C" in tasks
    c = next(s for s in samples if s["task"] == "C")
    assert "Edge-Loc" in c["messages"][1]["content"]
    assert "Edge-Ring" in c["messages"][1]["content"]


def test_deterministic(ring_fixture):
    manifest, stats = ring_fixture
    a = build_samples(manifest, stats, None, {"A": 50, "B": 50})
    b = build_samples(manifest, stats, None, {"A": 50, "B": 50})
    assert a == b  # 해시 기반 배정 — 재실행해도 동일
