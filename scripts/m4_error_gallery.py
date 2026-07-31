"""오분류 갤러리: confusion 상위 쌍의 실제 이미지·예측·정답·근거를 HTML로."""
import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from wafervlm.eval.parse import parse_all

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preds", required=True)
    ap.add_argument("--manifest", default="data/manifests/v1/test.parquet")
    ap.add_argument("--max-cards", type=int, default=100)
    ap.add_argument("--out", default="reports/errors.html")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.preds, encoding="utf-8")]
    manifest = pd.read_parquet(args.manifest).set_index("id")
    parsed = parse_all(rows)

    cards = []
    for p in parsed:
        if p["id"] not in manifest.index or len(cards) >= args.max_cards:
            continue
        true = sorted(manifest.loc[p["id"], "labels"])
        pred = sorted(p["readout"].patterns) if p["ok"] else ["<파싱실패>"]
        if pred == true:
            continue
        img_path = manifest.loc[p["id"], "image_path"]
        b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
        desc = p["readout"].description if p["ok"] else (p["error"] or "")
        cards.append(
            f"<div class='card'><img src='data:image/png;base64,{b64}' width='224'>"
            f"<div><b>{p['id']}</b><br>정답: {true} / 예측: <span style='color:red'>{pred}</span>"
            f"<p>{desc}</p></div></div>"
        )

    html = (
        "<meta charset='utf-8'><style>.card{display:flex;gap:12px;margin:12px;"
        "padding:8px;border:1px solid #ccc;max-width:900px}img{image-rendering:pixelated}</style>"
        + "\n".join(cards)
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"{len(cards)} error cards -> {args.out}")
