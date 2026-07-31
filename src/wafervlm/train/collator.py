"""Qwen3-VL SFT collator: chat template 적용 + assistant 응답만 label로 남기는 마스킹.

구현 원칙(버그 최다 발생 지점이므로 단순·검증가능하게):
  - Qwen3 Thinking 템플릿은 슬라이스 렌더가 전체 렌더의 prefix가 아니다
    (마지막이 아닌 assistant 턴의 <think> 제거, 마지막 턴에 빈 <think> 삽입).
    따라서 전체 렌더 문자열 하나에서 assistant 블록의 문자 위치를 찾고,
    특수 토큰 경계(<|im_start|>/<|im_end|>)에서 자른 prefix를 인코딩해 토큰
    길이를 잰다 — 특수 토큰은 BPE 병합 경계라 슬라이스 토큰화 = 전체의 prefix.
  - 중간 assistant 턴의 <think>는 추론 시에도 컨텍스트에서 제거되므로(템플릿
    정책과 동일) 학습 타깃에서도 미리 제거한다. think는 마지막 턴만 학습.
  - 이미지 토큰 확장은 processor가 처리하므로 prefix/full 모두 동일 이미지로 처리한다.
tests/test_collator.py에서 디코딩 왕복으로 검증한다.
"""
from __future__ import annotations

import re
from typing import Dict, List

import torch

IGNORE_INDEX = -100

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_IM_START = "<|im_start|>"
_IM_END = "<|im_end|>"
_ASSISTANT_HEADER = _IM_START + "assistant"


class SftCollator:
    def __init__(self, processor, max_length: int = 4096):
        self.processor = processor
        self.tokenizer = processor.tokenizer
        self.max_length = max_length

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _to_template_format(messages: List[Dict]) -> List[Dict]:
        """텍스트 content → Qwen3-VL 템플릿 형식. 첫 user 턴에 이미지 슬롯 삽입.

        마지막이 아닌 assistant 턴의 <think>는 템플릿이 어차피 제거하므로
        여기서 미리 제거해 렌더 결과를 예측 가능하게 만든다.
        """
        asst_idx = [i for i, m in enumerate(messages) if m["role"] == "assistant"]
        last_asst = asst_idx[-1] if asst_idx else -1
        out, image_inserted = [], False
        for i, m in enumerate(messages):
            text = m["content"]
            if m["role"] == "assistant" and i != last_asst:
                text = _THINK_RE.sub("", text).lstrip()
            if m["role"] == "user" and not image_inserted:
                content = [
                    {"type": "image"},
                    {"type": "text", "text": text},
                ]
                image_inserted = True
            else:
                content = [{"type": "text", "text": text}]
            out.append({"role": m["role"], "content": content})
        return out

    def _encode(self, text: str, image) -> Dict[str, torch.Tensor]:
        return self.processor(
            text=[text], images=[image], return_tensors="pt", padding=False
        )

    def _build_one(self, messages: List[Dict], image) -> Dict[str, torch.Tensor]:
        full_text = self.processor.apply_chat_template(
            self._to_template_format(messages),
            tokenize=False,
            add_generation_prompt=False,
        )
        enc = self._encode(full_text, image)
        input_ids = enc["input_ids"][0]
        labels = torch.full_like(input_ids, IGNORE_INDEX)

        # assistant 블록마다: <|im_start|> 직후("assistant\n...")부터 <|im_end|>까지 학습.
        # 경계가 전부 특수 토큰이라 문자 슬라이스 인코딩 길이 = 전체 인코딩의 prefix 길이.
        pos = 0
        while True:
            s = full_text.find(_ASSISTANT_HEADER, pos)
            if s == -1:
                break
            e = full_text.find(_IM_END, s)
            if e == -1:
                break
            learn_start = s + len(_IM_START)
            learn_end = e + len(_IM_END)
            n_prefix = self._encode(full_text[:learn_start], image)["input_ids"].shape[1]
            n_upto = self._encode(full_text[:learn_end], image)["input_ids"].shape[1]
            labels[n_prefix:n_upto] = input_ids[n_prefix:n_upto]
            pos = learn_end

        out = {
            "input_ids": input_ids[: self.max_length],
            "attention_mask": enc["attention_mask"][0][: self.max_length],
            "labels": labels[: self.max_length],
        }
        for k in ("pixel_values", "image_grid_thw"):
            if k in enc:
                out[k] = enc[k]
        return out

    # ------------------------------------------------------------------ collate
    def __call__(self, batch: List[Dict]) -> Dict[str, torch.Tensor]:
        items = [self._build_one(b["messages"], b["image"]) for b in batch]
        pad_id = self.tokenizer.pad_token_id or self.tokenizer.eos_token_id
        max_len = max(x["input_ids"].shape[0] for x in items)

        def _pad(seq: torch.Tensor, value: int) -> torch.Tensor:
            n = max_len - seq.shape[0]
            return torch.nn.functional.pad(seq, (0, n), value=value)

        out = {
            "input_ids": torch.stack([_pad(x["input_ids"], pad_id) for x in items]),
            "attention_mask": torch.stack(
                [_pad(x["attention_mask"], 0) for x in items]
            ),
            "labels": torch.stack([_pad(x["labels"], IGNORE_INDEX) for x in items]),
        }
        if "pixel_values" in items[0]:
            out["pixel_values"] = torch.cat([x["pixel_values"] for x in items], dim=0)
        if "image_grid_thw" in items[0]:
            out["image_grid_thw"] = torch.cat(
                [x["image_grid_thw"] for x in items], dim=0
            )
        return out
