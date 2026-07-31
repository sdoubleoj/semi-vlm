"""collator 라벨 마스킹 검증 — 마스킹 버그는 loss 곡선만으로 드러나지 않는다.

실제 Qwen3-VL processor가 필요하므로 모델 미다운로드 환경에서는 skip.
실행: pytest tests/test_collator.py -q  (models/qwen3-vl-4b-thinking 존재 시)
"""
from pathlib import Path

import pytest

MODEL_DIR = Path(__file__).resolve().parents[1] / "models/qwen3-vl-4b-thinking"

pytestmark = pytest.mark.skipif(
    not MODEL_DIR.exists(), reason="모델 미다운로드 (M0-3 이후 실행)"
)


@pytest.fixture(scope="module")
def collator():
    from transformers import AutoProcessor

    from wafervlm.train.collator import SftCollator

    return SftCollator(AutoProcessor.from_pretrained(str(MODEL_DIR)))


@pytest.fixture()
def sample():
    import numpy as np

    from wafervlm.data.render import render_map

    arr = np.ones((30, 30), dtype=np.int32)
    arr[10:15, 10:15] = 2
    return {
        "id": "t",
        "image": render_map(arr).convert("RGB"),
        "messages": [
            {"role": "system", "content": "판독 전문가."},
            {"role": "user", "content": "패턴 판독해줘."},
            {"role": "assistant", "content": "<think>\n관찰: 중앙 군집.\n</think>\n\n{\"answer\": 1}"},
        ],
    }


def test_only_assistant_tokens_learned(collator, sample):
    from wafervlm.train.collator import IGNORE_INDEX

    batch = collator([sample])
    ids, labels = batch["input_ids"][0], batch["labels"][0]
    learned = ids[labels != IGNORE_INDEX]
    text = collator.tokenizer.decode(learned)
    # 학습 대상 텍스트에 assistant 내용은 있고, 프롬프트 내용은 없어야 한다
    assert "관찰: 중앙 군집" in text or '{"answer": 1}' in text
    assert "패턴 판독해줘" not in text
    assert "판독 전문가" not in text
    # 이미지 토큰 구간은 전부 마스킹
    image_token_id = collator.tokenizer.convert_tokens_to_ids("<|image_pad|>")
    if image_token_id is not None and image_token_id >= 0:
        assert (labels[ids == image_token_id] == IGNORE_INDEX).all()


def test_multiturn_masks_each_assistant(collator, sample):
    from wafervlm.train.collator import IGNORE_INDEX

    sample["messages"] += [
        {"role": "user", "content": "어느 영역이야?"},
        {"role": "assistant", "content": "중심부 영역이다."},
    ]
    batch = collator([sample])
    ids, labels = batch["input_ids"][0], batch["labels"][0]
    text = collator.tokenizer.decode(ids[labels != IGNORE_INDEX])
    assert "중심부 영역이다" in text
    assert "어느 영역이야" not in text


def test_batch_padding(collator, sample):
    import copy

    s2 = copy.deepcopy(sample)
    s2["messages"][-1]["content"] += " 추가 텍스트로 길이를 다르게 만든다."
    batch = collator([sample, s2])
    assert batch["input_ids"].shape[0] == 2
    assert batch["input_ids"].shape == batch["labels"].shape
