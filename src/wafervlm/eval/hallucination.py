"""원인 추정 hallucination 검출: 서술에 공정/장비 원인이 새어 나오는지 검사.

VLM은 '관측 사실'까지만 담당한다 — description에 공정 원인 언급 비율은 0이어야 한다.
1차: 금지어 사전 스캔 (빠르고 결정적). LLM-judge 보조는 리포트 단계에서 선택 적용.
"""
from __future__ import annotations

from typing import Dict, List

# 공정/장비/원인 추정 어휘 (소문자 비교)
CAUSE_LEXICON = (
    # 공정명
    "cmp", "에칭", "etch", "포토", "litho", "노광", "증착", "deposition", "확산",
    "이온주입", "implant", "세정", "cleaning", "산화", "어닐", "anneal",
    # 장비/설비
    "장비", "챔버", "chamber", "노즐", "레시피", "recipe", "설비",
    # 원인 추정 표현
    "원인으로", "원인은", "때문에 발생", "공정 이상", "공정 문제", "불균일로 인해",
    "이상으로 보임", "추정된다", "추정됨",
)


def scan_text(text: str) -> List[str]:
    low = text.lower()
    return [w for w in CAUSE_LEXICON if w in low]


def hallucination_report(parsed: List[Dict[str, object]]) -> Dict[str, object]:
    n = hits = 0
    offenders = []
    for p in parsed:
        if not p["ok"]:
            continue
        n += 1
        found = scan_text(p["readout"].description)
        if found:
            hits += 1
            offenders.append({"id": p["id"], "terms": found})
    return {
        "n": n,
        "cause_mention_rate": hits / n if n else 0.0,  # 목표: 0
        "offenders": offenders[:50],
    }
