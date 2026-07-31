"""SFT 데이터셋 통계: 태스크별 샘플 수, assistant 텍스트 길이 분포."""
import argparse
import json
from collections import Counter
from pathlib import Path

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    lines = [f"# SFT stats: {args.dataset}\n"]
    for split in ("train", "val"):
        path = Path(args.dataset) / f"{split}.jsonl"
        if not path.exists():
            continue
        tasks, lengths = Counter(), []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                s = json.loads(line)
                tasks[s["task"]] += 1
                lengths.append(len(s["messages"][-1]["content"]))
        lengths.sort()
        n = len(lengths)
        lines.append(f"## {split}: {n:,} samples")
        lines.append(f"- task 분포: {dict(sorted(tasks.items()))}")
        if n:
            lines.append(
                f"- assistant 길이(chars): p50={lengths[n//2]}, "
                f"p90={lengths[int(n*0.9)]}, max={lengths[-1]}\n"
            )
    report = "\n".join(lines)
    print(report)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(report, encoding="utf-8")
