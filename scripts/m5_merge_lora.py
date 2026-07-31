"""LoRA adapter → base 병합 (vLLM 서빙용 단일 체크포인트)."""
import argparse

import torch
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    base = AutoModelForImageTextToText.from_pretrained(
        args.base, torch_dtype=torch.bfloat16
    )
    model = PeftModel.from_pretrained(base, args.adapter)
    merged = model.merge_and_unload()
    merged.save_pretrained(args.out)
    AutoProcessor.from_pretrained(args.base).save_pretrained(args.out)
    print(f"merged -> {args.out}")
