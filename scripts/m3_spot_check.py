"""중간 체크포인트 정성 점검: val N개 추론 → 스키마 준수 여부 + 출력 샘플."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import torch
from transformers import AutoModelForImageTextToText, AutoProcessor

from wafervlm.eval.parse import parse_prediction
from wafervlm.train.dataset import SftDataset

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--val-jsonl", default="data/sft/v1_think/val.jsonl")
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()

    processor = AutoProcessor.from_pretrained(args.ckpt)
    model = AutoModelForImageTextToText.from_pretrained(
        args.ckpt, dtype=torch.bfloat16, device_map="cuda:0"
    )
    ds = SftDataset(args.val_jsonl, cache_images=False, limit=args.n)

    ok = 0
    for i in range(len(ds)):
        item = ds[i]
        # 마지막 assistant 턴 제거 → 생성으로 대체
        messages = [m for m in item["messages"] if m["role"] != "assistant"][:2]
        content = [
            {"type": "image", "image": item["image"]},
            {"type": "text", "text": messages[-1]["content"]},
        ]
        system = {
            "role": "system",
            "content": [{"type": "text", "text": messages[0]["content"]}],
        }
        chat = [system, {"role": "user", "content": content}]
        inputs = processor.apply_chat_template(
            chat, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)
        out = model.generate(**inputs, max_new_tokens=1024)
        text = processor.decode(
            out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
        )
        parsed = parse_prediction(text)
        ok += int(parsed["ok"])
        status = "OK " if parsed["ok"] else f"FAIL({parsed['error'][:60]})"
        print(f"[{i}] {item['id']}: {status}")
        if i < 3:
            print(text[:500], "\n---")
    print(f"\n스키마 준수: {ok}/{len(ds)}")
