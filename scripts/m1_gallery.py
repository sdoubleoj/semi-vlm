"""육안 검수 갤러리: 클래스별 대표 샘플 이미지 + 자동 캡션 대조 HTML."""
import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from wafervlm.data.captions import build_description, build_think

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", default="data/stats.parquet")
    ap.add_argument("--raw-index", default="data/images/raw_index.parquet")
    ap.add_argument("--per-class", type=int, default=10)
    ap.add_argument("--out", default="reports/gallery_v1.html")
    args = ap.parse_args()

    stats = pd.read_parquet(args.stats)
    stats["labels"] = stats["labels"].map(list)
    index = pd.read_parquet(args.raw_index).set_index("id")

    stats["combo"] = stats["labels"].map(lambda l: "+".join(sorted(l)))
    picks = stats.groupby("combo").head(args.per_class)

    cards = []
    for _, row in picks.iterrows():
        img_path = index.loc[row["id"], "image_path"]
        b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
        desc = build_description(row["id"], row["labels"], row.to_dict())
        think = build_think(row["id"], row["labels"], row.to_dict())
        cards.append(
            f"<div class='card'><img src='data:image/png;base64,{b64}' width='224'>"
            f"<div><b>{row['id']}</b> — {row['combo']}<br>"
            f"<i>zone={row['zone']} shape={row['shape']} clock={row['clock']}</i>"
            f"<p>{desc}</p><details><summary>think</summary><p>{think}</p></details>"
            f"</div></div>"
        )

    html = (
        "<meta charset='utf-8'><style>.card{display:flex;gap:12px;margin:12px;"
        "padding:8px;border:1px solid #ccc;max-width:900px}img{image-rendering:pixelated}</style>"
        + "\n".join(cards)
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"{len(cards)} cards -> {args.out}")
