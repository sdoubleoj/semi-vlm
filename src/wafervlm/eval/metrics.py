"""분류/multi-label 메트릭. macro-F1 중심 (불균형 때문에 accuracy 단독 금지)."""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

from ..constants import PATTERNS


def _to_multihot(labels: Sequence[str]) -> np.ndarray:
    v = np.zeros(len(PATTERNS), dtype=int)
    for l in labels:
        if l in PATTERNS:
            v[PATTERNS.index(l)] = 1
    return v


def schema_compliance(parsed: List[Dict[str, object]]) -> Dict[str, float]:
    n = len(parsed)
    ok = sum(1 for p in parsed if p["ok"])
    return {"n": n, "parse_success_rate": ok / n if n else 0.0}


def classification_report(
    y_true: List[List[str]], y_pred: List[List[str]]
) -> Dict[str, object]:
    """단일/다중 라벨 공용: per-class P/R/F1, macro-F1, exact match, Hamming loss."""
    T = np.stack([_to_multihot(t) for t in y_true])
    P = np.stack([_to_multihot(p) for p in y_pred])

    per_class = {}
    f1s = []
    for i, name in enumerate(PATTERNS):
        tp = int(((T[:, i] == 1) & (P[:, i] == 1)).sum())
        fp = int(((T[:, i] == 0) & (P[:, i] == 1)).sum())
        fn = int(((T[:, i] == 1) & (P[:, i] == 0)).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        support = int(T[:, i].sum())
        per_class[name] = {
            "precision": prec, "recall": rec, "f1": f1, "support": support,
        }
        if support > 0:
            f1s.append(f1)

    return {
        "macro_f1": float(np.mean(f1s)) if f1s else 0.0,
        "exact_match": float((T == P).all(axis=1).mean()),
        "hamming_loss": float((T != P).mean()),
        "per_class": per_class,
    }


def confusion_pairs(
    y_true: List[List[str]], y_pred: List[List[str]], top_k: int = 10
) -> List[Tuple[str, str, int]]:
    """단일 라벨 케이스의 혼동 상위 쌍 (true, pred, count)."""
    counts: Dict[Tuple[str, str], int] = {}
    for t, p in zip(y_true, y_pred):
        if len(t) == 1 and len(p) == 1 and t[0] != p[0]:
            key = (t[0], p[0])
            counts[key] = counts.get(key, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:top_k]
    return [(a, b, n) for (a, b), n in ranked]
