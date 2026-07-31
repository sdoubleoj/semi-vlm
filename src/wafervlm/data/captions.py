"""기하 통계 → 관측 캡션 + <think> 추론 텍스트 (규칙 기반, 결정적).

원칙: '관측 사실'만 서술한다. 공정/장비 원인 언급은 금지 (시스템 책임 경계).
템플릿 선택은 id의 CRC32로 결정적으로 골라 재현성을 보장함.
"""
from __future__ import annotations

import zlib
from typing import Dict, List

ZONE_KO = {"center": "중심부", "mid": "중간 영역", "edge": "가장자리", "full": "전면"}
SHAPE_KO = {
    "ring": "링 형태",
    "line": "선형(스크래치성) 형태",
    "cluster": "국소 군집 형태",
    "scatter": "산발적 분포",
    "arc": "호(arc) 형태",
    "blob": "넓은 면적의 덩어리 형태",
    "none": "뚜렷한 형상 없음",
}

_DESC_TEMPLATES = [
    "불량 die가 웨이퍼 {zone}에 {shape}로 분포한다. {direction_clause}불량 die 비율은 약 {ratio:.1%}이다.",
    "웨이퍼 {zone}에서 {shape}의 불량 분포가 관측된다. {direction_clause}전체 die 중 약 {ratio:.1%}가 불량이다.",
    "{zone}를 중심으로 {shape}의 불량 밀집이 보이며, {direction_clause}불량률은 약 {ratio:.1%} 수준이다.",
]

_NONE_TEMPLATES = [
    "뚜렷한 공간 패턴 없이 불량 die가 드물게 산재한다(불량률 약 {ratio:.1%}). 정상 웨이퍼로 판독된다.",
    "특정 영역에 밀집되지 않은 미미한 산발 불량만 관측된다(약 {ratio:.1%}). 배경 노이즈 수준이다.",
]


def _pick(templates: List[str], sample_id: str) -> str:
    return templates[zlib.crc32(sample_id.encode()) % len(templates)]


def _direction_clause(feats: Dict[str, object]) -> str:
    clock = feats.get("clock", "전방위")
    if clock == "전방위" or feats.get("angular_concentration", 0.0) < 0.3:
        return ""
    return f"방위상 {clock} 방향에 치우쳐 있다. "


def build_description(sample_id: str, labels: List[str], feats: Dict[str, object]) -> str:
    """관측 중심 자연어 서술 (schema.description 타깃)."""
    if labels == ["None"]:
        return _pick(_NONE_TEMPLATES, sample_id).format(ratio=feats["defect_ratio"])
    return _pick(_DESC_TEMPLATES, sample_id).format(
        zone=ZONE_KO[str(feats["zone"])],
        shape=SHAPE_KO[str(feats["shape"])],
        direction_clause=_direction_clause(feats),
        ratio=feats["defect_ratio"],
    )


def build_think(sample_id: str, labels: List[str], feats: Dict[str, object]) -> str:
    """'공간 관찰 → 패턴 판단' 추론 텍스트 (<think> 블록 내용)."""
    obs = [
        f"불량 die 비율 {feats['defect_ratio']:.1%} ({feats['n_defect']}개).",
        f"정규화 반경 평균 {feats['r_mean']:.2f}, 표준편차 {feats['r_std']:.2f}, "
        f"edge(r≥0.8) 비중 {feats['frac_edge']:.0%}, center(r≤0.35) 비중 {feats['frac_inner']:.0%}.",
        f"각도 점유율 {feats['angular_coverage']:.0%}, 방향 집중도 {feats['angular_concentration']:.2f} ({feats['clock']}).",
        f"군집 수 {feats['n_clusters']}, 최대 군집 비중 {feats['largest_cluster_frac']:.0%}, "
        f"선형성 {feats['linearity']:.2f}.",
    ]
    zone_ko = ZONE_KO[str(feats["zone"])]
    shape_ko = SHAPE_KO[str(feats["shape"])]
    if labels == ["None"]:
        conclusion = "밀집·형상 신호가 없어 배경 노이즈 수준의 산발 불량으로 판단 → None."
    else:
        conclusion = (
            f"불량이 {zone_ko}에 {shape_ko}로 밀집 → {' + '.join(labels)} 패턴으로 판단."
        )
    return "관찰: " + " ".join(obs) + " 판단: " + conclusion
