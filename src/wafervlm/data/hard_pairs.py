"""Hard pair 마이닝: 유사 패턴 경계 사례 + 구분 근거 텍스트 생성.

최우선 쌍은 Center↔Loc (CNN 한계의 대표 사례). 가성 결함 경계(None+노이즈 vs 약한
Random/Loc)도 여기서 수집한다. 판정 규칙은 geometry 특징만 사용한다.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from ..constants import R_EDGE, R_INNER

# (pair_key, 대상 라벨, 상대 라벨)
PAIRS = {
    "center-loc": ("Center", "Loc"),
    "loc-edgeloc": ("Loc", "Edge-Loc"),
    "donut-center": ("Donut", "Center"),
    "scratch-random": ("Scratch", "Random"),
    "edgeloc-edgering": ("Edge-Loc", "Edge-Ring"),
    "none-noise": ("None", "Random"),  # 가성 결함 경계
}


def _rationale(pair: str, label: str, other: str, f: Dict[str, object]) -> str:
    """기하 통계 차이 기반 구분 근거 (Task C 타깃 텍스트)."""
    if pair == "center-loc":
        if label == "Center":
            return (
                f"불량 군집의 반경 평균이 {f['r_mean']:.2f}로 웨이퍼 중심(r≤{R_INNER})에 "
                f"밀집하고 center 비중이 {f['frac_inner']:.0%}로 우세 → Loc이 아닌 Center."
            )
        return (
            f"군집이 국소적이지만 반경 평균 {f['r_mean']:.2f}로 중심 기준(r≤{R_INNER})을 "
            f"벗어나 있고 center 비중이 {f['frac_inner']:.0%}에 불과 → Center가 아닌 Loc."
        )
    if pair == "loc-edgeloc":
        side = "미달" if label == "Loc" else "충족"
        return (
            f"군집 반경 90분위가 {f['r_p90']:.2f}로 edge 기준(r≥{R_EDGE})을 {side} → {label}."
        )
    if pair == "donut-center":
        if label == "Donut":
            return (
                f"중심부(r≤{R_INNER})가 비어 있고(비중 {f['frac_inner']:.0%}) 중간 반경 대역에 "
                f"환형 분포(반경 std {f['r_std']:.2f}) → Center가 아닌 Donut."
            )
        return (
            f"중심부 비중이 {f['frac_inner']:.0%}로 채워져 있어 환형 공동이 없음 → Donut이 아닌 Center."
        )
    if pair == "scratch-random":
        if label == "Scratch":
            return (
                f"최대 군집 선형성 {f['linearity']:.2f}(≥0.92)로 가늘고 긴 선형 궤적 → Random이 아닌 Scratch."
            )
        return (
            f"선형성 {f['linearity']:.2f}로 방향성 없는 산발 분포(군집 {f['n_clusters']}개) → Scratch가 아닌 Random."
        )
    if pair == "edgeloc-edgering":
        if label == "Edge-Ring":
            return (
                f"가장자리 불량의 각도 점유율이 {f['angular_coverage']:.0%}로 둘레 전반을 덮음 → Edge-Loc이 아닌 Edge-Ring."
            )
        return (
            f"가장자리 불량이 각도 점유율 {f['angular_coverage']:.0%}로 일부 방위({f['clock']})에 국한 → Edge-Ring이 아닌 Edge-Loc."
        )
    if pair == "none-noise":
        if label == "None":
            return (
                f"불량률 {f['defect_ratio']:.1%}에 군집·형상 신호가 없어(최대 군집 비중 "
                f"{f['largest_cluster_frac']:.0%}) 배경 노이즈 수준 → 실제 패턴이 아닌 None."
            )
        return (
            f"산발적으로 보이나 불량률 {f['defect_ratio']:.1%}와 분포 균일성이 노이즈 범위를 "
            f"벗어남 → None이 아닌 {label}."
        )
    return f"기하 통계상 {label}의 전형 특징에 부합 → {other}가 아닌 {label}."


def _is_boundary(pair: str, label: str, f: Dict[str, object]) -> bool:
    """쌍별 '경계 사례' 필터 — 애매한 구간의 샘플만 채택."""
    if pair == "center-loc":
        return 0.15 <= f["r_mean"] <= 0.55
    if pair == "loc-edgeloc":
        return 0.55 <= f["r_p90"] <= 0.9
    if pair == "donut-center":
        return 0.2 <= f["r_mean"] <= 0.6
    if pair == "scratch-random":
        return 0.75 <= f["linearity"] <= 0.97
    if pair == "edgeloc-edgering":
        return 0.3 <= f["angular_coverage"] <= 0.85
    if pair == "none-noise":
        return f["defect_ratio"] <= 0.05
    return False


def mine_hard_pairs(
    stats: pd.DataFrame, pairs: Optional[List[str]] = None, per_pair_cap: int = 2000
) -> pd.DataFrame:
    """stats(id, labels, 기하 특징 컬럼) → hard pair 레코드.

    반환 컬럼: id, pair, label, other, rationale
    """
    pairs = pairs or list(PAIRS)
    records = []
    for pair in pairs:
        a, b = PAIRS[pair]
        subset = stats[stats["labels"].map(lambda ls: ls == [a] or ls == [b])]
        count = 0
        for _, row in subset.iterrows():
            label = row["labels"][0]
            other = b if label == a else a
            f = row.to_dict()
            if not _is_boundary(pair, label, f):
                continue
            records.append(
                {
                    "id": row["id"],
                    "pair": pair,
                    "label": label,
                    "other": other,
                    "rationale": _rationale(pair, label, other, f),
                }
            )
            count += 1
            if count >= per_pair_cap:
                break
    return pd.DataFrame(records)
