"""Zero-shot 판독 능력 사전 관찰: 클래스별 실데이터 샘플에 서술 질의 → 리포트 저장."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

from wafervlm.constants import CHAT_SYSTEM_PROMPT
from wafervlm.data.load_wm811k import load_wm811k
from wafervlm.data.render import render_map

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=20)
    # Thinking 모델은 512로는 </think> 전에 잘려 베이스라인으로 못 씀
    ap.add_argument("--max-new-tokens", type=int, default=4096)
    ap.add_argument("--out", default="reports/zeroshot_probe.md")
    args = ap.parse_args()

    labeled, _ = load_wm811k()
    # 클래스별 균등 샘플 (결정적: 각 클래스 앞에서부터)
    per_class = max(1, args.n // labeled["labels"].map(lambda l: l[0]).nunique())
    picks = labeled.groupby(labeled["labels"].map(lambda l: l[0])).head(per_class)

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda:0"
    )

    lines = ["# Zero-shot 판독 프로브\n"]
    for _, row in picks.iterrows():
        img = render_map(row["wafer_map"])
        messages = [
            {"role": "system", "content": [{"type": "text", "text": CHAT_SYSTEM_PROMPT}]},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": "이 웨이퍼맵의 결함 패턴과 공간 분포를 서술해줘."},
                ],
            },
        ]
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)
        out = model.generate(**inputs, max_new_tokens=args.max_new_tokens)
        text = processor.decode(
            out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        lines.append(f"## {row['id']} (정답: {row['labels']})\n\n```\n{text}\n```\n")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"saved -> {args.out}")
