"""vLLM 오프라인 배치 추론 (sem-vllm 환경에서 실행).

사용:
  conda activate sem-vllm
  CUDA_VISIBLE_DEVICES=3 python -m wafervlm.eval.batch_infer \
      --model outputs/full_ft_4b/merged --manifest data/manifests/v1/test.parquet \
      --out preds/test.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ..constants import CHAT_SYSTEM_PROMPT

DEFAULT_QUESTION = "이 웨이퍼맵의 결함 패턴을 판독해줘."
# Qwen Thinking 계열 권장 샘플링 (모델 카드 재확인 항목)
DEFAULT_TEMPERATURE = 0.6
DEFAULT_TOP_P = 0.95


def build_messages(image_path: str, question: str):
    return [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"file://{Path(image_path).resolve()}"}},
                {"type": "text", "text": question},
            ],
        },
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--question", default=DEFAULT_QUESTION)
    ap.add_argument("--max-new-tokens", type=int, default=1024)
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--top-p", type=float, default=DEFAULT_TOP_P)
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.8)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from vllm import LLM, SamplingParams  # sem-vllm 환경 전용 import

    manifest = pd.read_parquet(args.manifest)
    if args.limit:
        manifest = manifest.head(args.limit)

    llm = LLM(
        model=args.model,
        gpu_memory_utilization=args.gpu_memory_utilization,
        limit_mm_per_prompt={"image": 1},
    )
    sampling = SamplingParams(
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_new_tokens,
    )
    conversations = [
        build_messages(p, args.question) for p in manifest["image_path"]
    ]
    outputs = llm.chat(conversations, sampling)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for sid, o in zip(manifest["id"], outputs):
            fh.write(
                json.dumps(
                    {"id": sid, "raw_output": o.outputs[0].text}, ensure_ascii=False
                )
                + "\n"
            )
    print(f"wrote {len(outputs)} predictions -> {args.out}")


if __name__ == "__main__":
    main()
