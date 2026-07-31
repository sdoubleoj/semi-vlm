"""VLM 출력 계약 (Output Contract) — pydantic 모델.

데이터 생성(build_sft) / 평가 파싱(eval.parse) / 서빙 검증(serve.api) 3곳에서 공용.
계약 문서: contracts/vlm_output_contract.md
"""
from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .constants import CLOCK_DIRECTIONS, CONFIDENCES, PATTERNS, SHAPES, ZONES


class Spatial(BaseModel):
    zone: str = Field(description="불량 밀집 영역: center/mid/edge/full")
    direction: str = Field(description="시계 방위(예: '3시') 또는 '전방위'")
    shape: str = Field(description="형상: ring/line/cluster/scatter/arc/blob/none")

    @field_validator("zone")
    @classmethod
    def _zone(cls, v: str) -> str:
        if v not in ZONES:
            raise ValueError(f"zone must be one of {ZONES}, got {v!r}")
        return v

    @field_validator("direction")
    @classmethod
    def _direction(cls, v: str) -> str:
        if v not in CLOCK_DIRECTIONS:
            raise ValueError(f"direction must be one of {CLOCK_DIRECTIONS}, got {v!r}")
        return v

    @field_validator("shape")
    @classmethod
    def _shape(cls, v: str) -> str:
        if v not in SHAPES:
            raise ValueError(f"shape must be one of {SHAPES}, got {v!r}")
        return v


class Severity(BaseModel):
    defect_die_ratio: float = Field(ge=0.0, le=1.0)


class Ambiguity(BaseModel):
    candidates: List[str]
    reason: str

    @field_validator("candidates")
    @classmethod
    def _candidates(cls, v: List[str]) -> List[str]:
        bad = [p for p in v if p not in PATTERNS]
        if bad:
            raise ValueError(f"unknown patterns in ambiguity.candidates: {bad}")
        return v


class WaferReadout(BaseModel):
    """VLM 최종 답변의 구조화 출력. GraphRAG 입력 계약."""

    patterns: List[str]
    spatial: Spatial
    description: str
    severity: Severity
    confidence: str
    ambiguity: Optional[Ambiguity] = None

    @field_validator("patterns")
    @classmethod
    def _patterns(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("patterns must not be empty (정상이면 ['None'])")
        bad = [p for p in v if p not in PATTERNS]
        if bad:
            raise ValueError(f"unknown patterns: {bad} (allowed: {PATTERNS})")
        if "None" in v and len(v) > 1:
            raise ValueError("'None' cannot be combined with defect patterns")
        return v

    @field_validator("confidence")
    @classmethod
    def _confidence(cls, v: str) -> str:
        if v not in CONFIDENCES:
            raise ValueError(f"confidence must be one of {CONFIDENCES}, got {v!r}")
        return v

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False)


def parse_readout(text: str) -> WaferReadout:
    """모델 출력 텍스트에서 첫 '{' ~ 마지막 '}' 구간을 JSON으로 파싱해 검증."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object found in output")
    return WaferReadout.model_validate_json(text[start : end + 1])
