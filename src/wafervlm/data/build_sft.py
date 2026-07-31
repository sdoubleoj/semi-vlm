"""Task A~E instruction 샘플 생성 (SFT jsonl).

샘플 포맷 (train/dataset.py가 소비):
{
  "id": ..., "task": "A", "image": "<png path>",
  "messages": [{"role":"system","content":...},
               {"role":"user","content":...},          # 텍스트만 (이미지는 image 필드)
               {"role":"assistant","content":...}],    # <think>...</think>\n\n{json}
  "followup": [...]                                    # Task D multi-turn용 (선택)
}
관측/원인 분리: assistant 답변은 관측 사실만 담는다.
"""
from __future__ import annotations

import json
import zlib
from typing import Dict, List, Optional

import pandas as pd

from ..constants import CHAT_SYSTEM_PROMPT, THINK_CLOSE, THINK_OPEN
from ..schema import Ambiguity, Severity, Spatial, WaferReadout
from .captions import build_description, build_think

_PROMPTS_A = [
    "이 웨이퍼맵의 결함 패턴을 판독해줘.",
    "이 웨이퍼에서 관측되는 불량 패턴을 분류해줘.",
    "웨이퍼맵을 보고 결함 유형을 판정해줘.",
]
_PROMPTS_B = [
    "이 웨이퍼맵의 불량 분포를 공간적으로 자세히 서술해줘.",
    "불량 die가 어디에 어떤 형상으로 분포하는지 설명해줘.",
]
_PROMPT_C = "이 웨이퍼맵이 {a} 패턴인지 {b} 패턴인지 판별하고, 그렇게 판단한 기하학적 근거를 설명해줘."
_PROMPTS_D = [
    "이 웨이퍼 어떤 불량이야?",
    "이 맵에서 뭔가 이상한 게 보여?",
    "이 웨이퍼맵 {label} 패턴 맞아?",
    "혼합 패턴인지 단일 패턴인지 확인해줘.",
]
_PROMPT_E = (
    "라벨이 없는 웨이퍼맵이야. 결함 패턴을 판독하고 신뢰도를 함께 제시해줘. "
    "애매하면 후보와 이유를 ambiguity에 남겨줘."
)
_FOLLOWUPS_D = [
    "그 패턴이 웨이퍼 어느 영역에 있어?",
    "불량 비율은 어느 정도야?",
]


def _crc(s: str) -> int:
    return zlib.crc32(s.encode())


def _confidence(feats: Dict[str, object], is_hard: bool) -> str:
    if is_hard:
        return "medium"
    if feats["defect_ratio"] == 0 or feats["n_defect"] < 5:
        return "medium"
    return "high"


def build_readout(
    sample_id: str,
    labels: List[str],
    feats: Dict[str, object],
    ambiguity: Optional[Ambiguity] = None,
    confidence: Optional[str] = None,
) -> WaferReadout:
    """라벨 + 기하 통계 → 출력 계약 객체 (SFT 타깃의 JSON 부분)."""
    return WaferReadout(
        patterns=list(labels),
        spatial=Spatial(
            zone=str(feats["zone"]),
            direction=str(feats["clock"]),
            shape=str(feats["shape"]),
        ),
        description=build_description(sample_id, labels, feats),
        severity=Severity(defect_die_ratio=round(float(feats["defect_ratio"]), 4)),
        confidence=confidence or _confidence(feats, is_hard=ambiguity is not None),
        ambiguity=ambiguity,
    )


def _assistant_text(
    readout: WaferReadout,
    think: str,
    think_mode: str,
    extra_think: str = "",
) -> str:
    body = readout.to_json()
    if think_mode == "reasoning":
        content = (think + " " + extra_think).strip()
        return f"{THINK_OPEN}\n{content}\n{THINK_CLOSE}\n\n{body}"
    if think_mode == "empty":
        return f"{THINK_OPEN}\n\n{THINK_CLOSE}\n\n{body}"
    raise ValueError(f"unknown think_mode: {think_mode}")


def _sample(
    row: pd.Series,
    task: str,
    user_text: str,
    assistant: str,
    followup: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, object]:
    rec: Dict[str, object] = {
        "id": row["id"],
        "task": task,
        "image": row["image_path"],
        "messages": [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant},
        ],
    }
    if followup:
        rec["followup"] = followup
    return rec


def build_samples(
    manifest: pd.DataFrame,
    stats: pd.DataFrame,
    hard_pairs: Optional[pd.DataFrame],
    ratios: Dict[str, int],
    think_mode: str = "reasoning",
) -> List[Dict[str, object]]:
    """manifest × stats → task 비율에 따른 instruction 샘플 리스트.

    task 배정은 id 해시로 결정적으로 이뤄진다. Task C는 hard_pairs에 있는 id에만 생성.
    """
    feats_by_id = stats.set_index("id").to_dict("index")
    hard_by_id: Dict[str, pd.Series] = {}
    if hard_pairs is not None and len(hard_pairs):
        hard_by_id = {r["id"]: r for _, r in hard_pairs.iterrows()}

    # A/B/D/E 누적 비율 (C는 hard pair 별도 트랙)
    keys = [k for k in ("A", "B", "D", "E") if ratios.get(k, 0) > 0]
    total = sum(ratios[k] for k in keys)
    cum, acc = [], 0
    for k in keys:
        acc += ratios[k]
        cum.append((acc / total, k))

    out: List[Dict[str, object]] = []
    for _, row in manifest.iterrows():
        sid = row["id"]
        feats = feats_by_id.get(sid)
        if feats is None:
            continue
        labels = list(row["labels"])
        think = build_think(sid, labels, feats)

        # ---- Task C: hard pair 샘플 (해당 id면 항상 추가 생성)
        if sid in hard_by_id and ratios.get("C", 0) > 0:
            hp = hard_by_id[sid]
            readout = build_readout(sid, labels, feats, confidence="medium")
            assistant = _assistant_text(
                readout, think, think_mode, extra_think=str(hp["rationale"])
            )
            a, b = sorted([hp["label"], hp["other"]])
            out.append(
                _sample(row, "C", _PROMPT_C.format(a=a, b=b), assistant)
            )

        # ---- A/B/D/E 중 하나를 해시로 배정
        u = (_crc("task:" + sid) % 10_000) / 10_000
        task = next(k for edge, k in cum if u < edge or (edge, k) == cum[-1])
        readout = build_readout(sid, labels, feats)
        assistant = _assistant_text(readout, think, think_mode)

        if task == "A":
            prompt = _PROMPTS_A[_crc("pa" + sid) % len(_PROMPTS_A)]
            out.append(_sample(row, "A", prompt, assistant))
        elif task == "B":
            prompt = _PROMPTS_B[_crc("pb" + sid) % len(_PROMPTS_B)]
            out.append(_sample(row, "B", prompt, assistant))
        elif task == "D":
            prompt = _PROMPTS_D[_crc("pd" + sid) % len(_PROMPTS_D)]
            prompt = prompt.format(label=labels[0])
            follow_q = _FOLLOWUPS_D[_crc("fd" + sid) % len(_FOLLOWUPS_D)]
            follow_a = build_description(sid, labels, feats)
            out.append(
                _sample(
                    row, "D", prompt, assistant,
                    followup=[
                        {"role": "user", "content": follow_q},
                        {"role": "assistant", "content": follow_a},
                    ],
                )
            )
        else:  # E: auto-labeling 포맷 (라벨된 데이터로 응답 형식을 학습)
            out.append(_sample(row, "E", _PROMPT_E, assistant))
    return out


def write_jsonl(samples: List[Dict[str, object]], path: str) -> None:
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for s in samples:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
