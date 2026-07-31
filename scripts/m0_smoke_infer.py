"""모델 로딩 + 웨이퍼맵 1장 추론 스모크: <think> 태그 출력과 VRAM 점유 확인."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

from wafervlm.constants import CHAT_SYSTEM_PROMPT
from wafervlm.data.render import render_map


def synthetic_edge_ring(size: int = 52) -> np.ndarray:
    """Edge-Ring 합성 맵 (데이터 로딩 없이 스모크 가능)."""
    yy, xx = np.mgrid[:size, :size]
    c = (size - 1) / 2
    r = np.sqrt((yy - c) ** 2 + (xx - c) ** 2) / c
    arr = np.zeros((size, size), dtype=np.int32)
    arr[r <= 1.0] = 1
    arr[(r >= 0.85) & (r <= 1.0)] = 2
    return arr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    # Thinking 모델은 zero-shot에서 thinking 길이 편차가 커서 넉넉히 잡는다
    ap.add_argument("--max-new-tokens", type=int, default=4096)
    ap.add_argument("--out", default="reports/smoke_infer.md")
    args = ap.parse_args()

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda:0"
    )
    print(f"모델 로드 VRAM: {torch.cuda.memory_allocated(0) / 1024**3:.1f} GiB")

    img = render_map(synthetic_edge_ring())
    # processor.apply_chat_template은 모든 content가 dict 리스트여야 한다
    messages = [
        {"role": "system", "content": [{"type": "text", "text": CHAT_SYSTEM_PROMPT}]},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": "이 웨이퍼맵의 결함 패턴과 위치를 서술해줘."},
            ],
        },
    ]
    inputs = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=True,
        return_dict=True, return_tensors="pt",
    ).to(model.device)
    out = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
    gen_ids = out[0][inputs["input_ids"].shape[1]:]
    text = processor.decode(gen_ids, skip_special_tokens=True)
    print("---- output ----")
    print(text)
    print("----------------")
    n_gen = int(gen_ids.shape[0])
    truncated = n_gen >= args.max_new_tokens
    token_line = f"생성 토큰: {n_gen}/{args.max_new_tokens}" + (
        " (한도 도달 — 출력 잘림!)" if truncated else " (정상 종료)"
    )
    load_vram = torch.cuda.memory_allocated(0) / 1024**3
    peak_vram = torch.cuda.max_memory_allocated(0) / 1024**3
    print(token_line)
    print("`</think>` 닫힘 여부:", "</think>" in text)
    print(f"추론 후 VRAM: {peak_vram:.1f} GiB")

    lines = [
        "# 스모크 추론 리포트\n",
        f"- 모델: `{args.model}`",
        f"- 입력: 합성 Edge-Ring 맵 (52×52)",
        f"- {token_line}",
        f"- `</think>` 닫힘 여부: {'</think>' in text}",
        f"- VRAM: 로드 {load_vram:.1f} GiB / 추론 피크 {peak_vram:.1f} GiB\n",
        f"## 출력\n\n```\n{text}\n```\n",
    ]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"saved -> {args.out}")
