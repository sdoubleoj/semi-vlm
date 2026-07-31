"""chat template 직렬화 검증: 샘플 N개를 토크나이즈→디코딩 왕복해 눈으로 확인."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--n", type=int, default=5)
    args = ap.parse_args()

    from transformers import AutoProcessor

    from wafervlm.train.collator import IGNORE_INDEX, SftCollator
    from wafervlm.train.dataset import SftDataset

    processor = AutoProcessor.from_pretrained(args.model)
    collator = SftCollator(processor)
    ds = SftDataset(f"{args.dataset}/train.jsonl", cache_images=False, limit=args.n)

    for i in range(min(args.n, len(ds))):
        item = ds[i]
        batch = collator([item])
        ids = batch["input_ids"][0]
        labels = batch["labels"][0]
        learned = ids[labels != IGNORE_INDEX]
        print("=" * 80)
        print(f"[{i}] id={item['id']}  seq_len={len(ids)}  learned_tokens={len(learned)}")
        print("---- 학습 대상(디코딩) — assistant 응답만 남아야 정상 ----")
        print(processor.tokenizer.decode(learned))
