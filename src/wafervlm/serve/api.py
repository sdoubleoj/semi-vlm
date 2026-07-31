"""추론 API 래퍼 (M5): 웨이퍼맵 입력 → 렌더링 → vLLM 추론 → 스키마 검증 → 구조화 응답.

vLLM OpenAI 호환 서버(별도 기동)를 백엔드로 호출한다.
스키마 위반 시 1회 재시도, 재실패 시 에러 규약(JSON)으로 응답 (Critic 재검증 트리거).

기동:
  conda activate sem-vllm
  python -m wafervlm.serve.api --port 8080 --vllm http://localhost:8000/v1 --model merged-4b
"""
from __future__ import annotations

import argparse
import base64
import io
from typing import List, Optional

import numpy as np
import requests
from fastapi import FastAPI
from pydantic import BaseModel

from ..constants import CHAT_SYSTEM_PROMPT
from ..data.render import render_map
from ..eval.parse import parse_prediction

app = FastAPI(title="wafervlm readout API")
_settings = {"vllm": "http://localhost:8000/v1", "model": "merged-4b"}


class ReadRequest(BaseModel):
    question: str = "이 웨이퍼맵의 결함 패턴을 판독해줘."
    wafer_map: Optional[List[List[int]]] = None   # 0/1/2 2D 배열
    image_b64: Optional[str] = None               # 또는 렌더링된 PNG base64


class ReadResponse(BaseModel):
    ok: bool
    readout: Optional[dict] = None
    error: Optional[str] = None
    raw_answer: Optional[str] = None


def _to_data_url(req: ReadRequest) -> str:
    if req.wafer_map is not None:
        img = render_map(np.asarray(req.wafer_map, dtype=np.int32))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        payload = base64.b64encode(buf.getvalue()).decode()
    elif req.image_b64:
        payload = req.image_b64
    else:
        raise ValueError("wafer_map 또는 image_b64 중 하나는 필수")
    return f"data:image/png;base64,{payload}"


def _call_vllm(data_url: str, question: str, temperature: float = 0.6) -> str:
    resp = requests.post(
        f"{_settings['vllm']}/chat/completions",
        json={
            "model": _settings["model"],
            "temperature": temperature,
            "top_p": 0.95,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": question},
                    ],
                },
            ],
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


@app.post("/read", response_model=ReadResponse)
def read_wafer(req: ReadRequest) -> ReadResponse:
    try:
        data_url = _to_data_url(req)
    except ValueError as e:
        return ReadResponse(ok=False, error=str(e))

    # 스키마 위반 시 1회 재시도 (온도 낮춰 재샘플)
    last_error = None
    for temperature in (0.6, 0.1):
        raw = _call_vllm(data_url, req.question, temperature)
        parsed = parse_prediction(raw)
        if parsed["ok"]:
            return ReadResponse(
                ok=True,
                readout=parsed["readout"].model_dump(),
                raw_answer=parsed["answer_text"],
            )
        last_error = parsed["error"]
    return ReadResponse(
        ok=False,
        error=f"schema violation after retry: {last_error}",
        raw_answer=raw,
    )


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--vllm", default=_settings["vllm"])
    ap.add_argument("--model", default=_settings["model"])
    args = ap.parse_args()
    _settings.update(vllm=args.vllm, model=args.model)
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
