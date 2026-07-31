"""confidence calibration: 신뢰도 구간별 실제 정확도 + ECE.

'high 신뢰'가 실제로 믿을 만한지가 Auto-Labeling·self-training의 전제 조건.
"""
from __future__ import annotations

from typing import Dict, List

from ..constants import CONFIDENCES

# 이산 신뢰도 → 명목 확률 (ECE 계산용)
NOMINAL = {"high": 0.95, "medium": 0.7, "low": 0.4}


def calibration_report(
    parsed: List[Dict[str, object]], truth: Dict[str, List[str]]
) -> Dict[str, object]:
    bins: Dict[str, List[int]] = {c: [] for c in CONFIDENCES}
    for p in parsed:
        if not p["ok"] or p["id"] not in truth:
            continue
        correct = int(sorted(p["readout"].patterns) == sorted(truth[p["id"]]))
        bins[p["readout"].confidence].append(correct)

    per_bin, ece_num, total = {}, 0.0, 0
    for c in CONFIDENCES:
        n = len(bins[c])
        acc = sum(bins[c]) / n if n else None
        per_bin[c] = {"n": n, "accuracy": acc}
        if n:
            ece_num += n * abs((acc or 0.0) - NOMINAL[c])
            total += n
    return {"per_confidence": per_bin, "ece": ece_num / total if total else None}
