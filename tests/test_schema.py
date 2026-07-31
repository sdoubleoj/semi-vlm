"""출력 계약(schema) 테스트: 통제 어휘 강제, 관측/원인 규약, 파싱."""
import pytest
from pydantic import ValidationError

from wafervlm.schema import WaferReadout, parse_readout

VALID = {
    "patterns": ["Edge-Ring"],
    "spatial": {"zone": "edge", "direction": "전방위", "shape": "ring"},
    "description": "가장자리를 따라 링 형태 불량 밀집.",
    "severity": {"defect_die_ratio": 0.18},
    "confidence": "high",
    "ambiguity": None,
}


def test_valid_readout():
    r = WaferReadout.model_validate(VALID)
    assert r.patterns == ["Edge-Ring"]


def test_rejects_unknown_pattern():
    bad = dict(VALID, patterns=["EdgeRing"])  # 통제 어휘 위반
    with pytest.raises(ValidationError):
        WaferReadout.model_validate(bad)


def test_rejects_none_with_defect():
    bad = dict(VALID, patterns=["None", "Center"])
    with pytest.raises(ValidationError):
        WaferReadout.model_validate(bad)


def test_rejects_bad_zone_and_confidence():
    with pytest.raises(ValidationError):
        WaferReadout.model_validate(dict(VALID, spatial={**VALID["spatial"], "zone": "middle"}))
    with pytest.raises(ValidationError):
        WaferReadout.model_validate(dict(VALID, confidence="아주높음"))


def test_ambiguity_candidates_validated():
    amb = {"candidates": ["Loc", "Edge-Loc"], "reason": "반경 경계 사례"}
    r = WaferReadout.model_validate(dict(VALID, ambiguity=amb, confidence="medium"))
    assert r.ambiguity.candidates == ["Loc", "Edge-Loc"]
    with pytest.raises(ValidationError):
        WaferReadout.model_validate(
            dict(VALID, ambiguity={"candidates": ["Blob"], "reason": "x"})
        )


def test_parse_readout_from_text():
    text = "판독 결과는 다음과 같습니다.\n" + WaferReadout.model_validate(VALID).to_json()
    r = parse_readout(text)
    assert r.spatial.shape == "ring"
    with pytest.raises(ValueError):
        parse_readout("JSON 없음")
