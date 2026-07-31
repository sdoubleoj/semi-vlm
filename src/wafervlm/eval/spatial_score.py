"""서술 자동 채점: 예측 spatial(zone/direction/shape)을 기하 통계(stats)와 대조."""
from __future__ import annotations

from typing import Dict, List

import pandas as pd


def _direction_match(pred: str, ref: str) -> bool:
    """시계 방위는 ±1시간까지 정답 인정. '전방위'는 완전 일치만."""
    if pred == ref:
        return True
    if "시" in pred and "시" in ref:
        try:
            a, b = int(pred.rstrip("시")), int(ref.rstrip("시"))
        except ValueError:
            return False
        return min((a - b) % 12, (b - a) % 12) <= 1
    return False


def spatial_report(
    parsed: List[Dict[str, object]], stats: pd.DataFrame
) -> Dict[str, float]:
    """zone/direction/shape 일치율 + severity 오차. 파싱 실패 샘플은 오답 처리."""
    ref = stats.set_index("id")
    n = zone_ok = dir_ok = shape_ok = 0
    sev_err = []
    for p in parsed:
        sid = p["id"]
        if sid not in ref.index:
            continue
        n += 1
        if not p["ok"]:
            continue
        r = ref.loc[sid]
        s = p["readout"].spatial
        zone_ok += int(s.zone == r["zone"])
        dir_ok += int(_direction_match(s.direction, str(r["clock"])))
        shape_ok += int(s.shape == r["shape"])
        sev_err.append(
            abs(p["readout"].severity.defect_die_ratio - float(r["defect_ratio"]))
        )
    return {
        "n": n,
        "zone_acc": zone_ok / n if n else 0.0,
        "direction_acc": dir_ok / n if n else 0.0,
        "shape_acc": shape_ok / n if n else 0.0,
        "severity_mae": float(sum(sev_err) / len(sev_err)) if sev_err else 1.0,
    }
