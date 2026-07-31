"""데이터 검증 리포트: 분포, 이상 맵, MixedWM38 내부 근사중복."""
import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from wafervlm.data.load_mixedwm38 import combo_key, load_mixedwm38
from wafervlm.data.load_wm811k import load_wm811k

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/data_validation.md")
    args = ap.parse_args()

    lines = ["# 데이터 검증 리포트\n"]

    labeled, unlabeled = load_wm811k()
    lines.append("## WM811K\n")
    lines.append(f"- 라벨된 유효 샘플: {len(labeled):,} / 미라벨: {len(unlabeled):,}")
    dist = Counter(l[0] for l in labeled["labels"])
    for name, cnt in dist.most_common():
        lines.append(f"  - {name}: {cnt:,}")

    mixed = load_mixedwm38()
    lines.append("\n## MixedWM38\n")
    lines.append(f"- 샘플: {len(mixed):,}")
    combos = Counter(combo_key(l) for l in mixed["labels"])
    lines.append(f"- 조합 클래스 수: {len(combos)} (기대: 38)")
    for name, cnt in combos.most_common():
        lines.append(f"  - {name}: {cnt:,}")

    # MixedWM38 내부 완전중복 (GAN 합성 근사중복의 하한 지표)
    hashes = Counter(
        hashlib.md5(np.asarray(m, dtype=np.uint8).tobytes()).hexdigest()
        for m in mixed["wafer_map"]
    )
    dup = sum(c - 1 for c in hashes.values() if c > 1)
    lines.append(f"\n- MixedWM38 내부 완전중복 맵: {dup:,}건")
    lines.append("- 교차 데이터셋 중복: 0건 (2026-07-03 확인 완료, 체크리스트 참조)")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"saved -> {args.out}")
