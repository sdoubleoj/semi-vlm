"""모델 출력 파싱: <think> 제거 → 출력 계약 JSON 검증. 파싱 실패도 메트릭으로 기록."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from ..schema import WaferReadout, parse_readout

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    """<think>...</think> 블록 제거. 닫히지 않은 <think>는 열림 지점 이후를 버린다."""
    out = _THINK_RE.sub("", text)
    if "<think>" in out:
        out = out.split("<think>")[0]
    return out.strip()


def parse_prediction(raw: str) -> Dict[str, object]:
    """반환: {ok, readout(WaferReadout|None), error(str|None), answer_text}."""
    answer = strip_think(raw)
    try:
        readout: Optional[WaferReadout] = parse_readout(answer)
        return {"ok": True, "readout": readout, "error": None, "answer_text": answer}
    except Exception as e:  # 파싱/스키마 위반 자체가 1급 메트릭
        return {"ok": False, "readout": None, "error": str(e), "answer_text": answer}


def parse_all(rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    """[{id, raw_output}] → 파싱 결과 리스트 (id 보존)."""
    out = []
    for r in rows:
        p = parse_prediction(r["raw_output"])
        p["id"] = r["id"]
        out.append(p)
    return out
