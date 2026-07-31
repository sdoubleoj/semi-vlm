"""SFT jsonl + 사전 렌더링 이미지 Dataset.

CPU 32코어 병목 대응: cache_images=True면 PNG 바이트를 RAM에 전량 상주시켜
학습 중 디스크 I/O를 제거한다 (RAM 955GiB 여유 활용).
"""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image
from torch.utils.data import Dataset


class SftDataset(Dataset):
    def __init__(self, jsonl_path: str, cache_images: bool = True, limit: Optional[int] = None):
        self.samples: List[Dict] = []
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                self.samples.append(json.loads(line))
                if limit and len(self.samples) >= limit:
                    break
        self._cache: Dict[str, bytes] = {}
        if cache_images:
            for s in self.samples:
                p = s["image"]
                if p not in self._cache:
                    self._cache[p] = Path(p).read_bytes()

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict:
        s = self.samples[idx]
        raw = self._cache.get(s["image"])
        img = Image.open(io.BytesIO(raw)) if raw else Image.open(s["image"])
        messages = list(s["messages"])
        if s.get("followup"):
            messages = messages + list(s["followup"])
        return {"messages": messages, "image": img.convert("RGB"), "id": s["id"]}
