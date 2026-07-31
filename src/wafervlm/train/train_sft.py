"""HF Transformers 직접 구현 SFT 진입점.

사용:
  단일 GPU:  CUDA_VISIBLE_DEVICES=0 python -m wafervlm.train.train_sft --config configs/exp_think.yaml
  분산(DDP): torchrun --nproc_per_node=4 -m wafervlm.train.train_sft --config configs/full_ft_4b.yaml
config yaml 키는 configs/ 예시 참조. 모델 경로는 config로만 주입 (4B→8B 재사용).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
import yaml
from transformers import (
    AutoModelForImageTextToText,
    AutoProcessor,
    Trainer,
    TrainingArguments,
)

from .collator import SftCollator
from .dataset import SftDataset


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def build_model(cfg: dict):
    model = AutoModelForImageTextToText.from_pretrained(
        cfg["model_path"],
        torch_dtype=torch.bfloat16,
        attn_implementation=cfg.get("attn_implementation", "flash_attention_2"),
    )
    if cfg.get("freeze_vision", True):
        vision = getattr(model, "visual", None) or getattr(model, "vision_tower", None)
        if vision is not None:
            for p in vision.parameters():
                p.requires_grad = False

    if cfg.get("lora"):
        from peft import LoraConfig, get_peft_model

        lcfg = cfg["lora"]
        peft_config = LoraConfig(
            r=lcfg.get("r", 32),
            lora_alpha=lcfg.get("alpha", 64),
            lora_dropout=lcfg.get("dropout", 0.05),
            target_modules=lcfg.get(
                "target_modules",
                ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            ),
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
    return model


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    cfg = load_config(args.config)

    processor = AutoProcessor.from_pretrained(cfg["model_path"])
    model = build_model(cfg)

    train_ds = SftDataset(
        cfg["train_jsonl"],
        cache_images=cfg.get("cache_images", True),
        limit=cfg.get("train_limit"),
    )
    eval_ds = (
        SftDataset(cfg["val_jsonl"], cache_images=cfg.get("cache_images", True))
        if cfg.get("val_jsonl")
        else None
    )
    collator = SftCollator(processor, max_length=cfg.get("max_length", 4096))

    out_dir = cfg["output_dir"]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    targs = TrainingArguments(
        output_dir=out_dir,
        per_device_train_batch_size=cfg.get("per_device_batch", 8),
        gradient_accumulation_steps=cfg.get("grad_accum", 1),
        learning_rate=float(cfg.get("lr", 1e-4)),
        num_train_epochs=cfg.get("epochs", 1),
        lr_scheduler_type="cosine",
        warmup_ratio=cfg.get("warmup_ratio", 0.03),
        bf16=True,
        gradient_checkpointing=cfg.get("gradient_checkpointing", False),
        logging_steps=cfg.get("logging_steps", 10),
        save_strategy="steps",
        save_steps=cfg.get("save_steps", 500),
        save_total_limit=cfg.get("save_total_limit", 3),
        eval_strategy="steps" if eval_ds is not None else "no",
        eval_steps=cfg.get("eval_steps", 500),
        load_best_model_at_end=eval_ds is not None,
        dataloader_num_workers=cfg.get("num_workers", 6),
        dataloader_pin_memory=True,
        dataloader_persistent_workers=cfg.get("num_workers", 6) > 0,
        remove_unused_columns=False,
        deepspeed=cfg.get("deepspeed"),
        report_to=cfg.get("report_to", "none"),
        run_name=cfg.get("run_name", Path(args.config).stem),
        seed=cfg.get("seed", 42),
    )

    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=collator,
    )
    trainer.train(resume_from_checkpoint=cfg.get("resume_from_checkpoint"))
    trainer.save_model(f"{out_dir}/final")
    processor.save_pretrained(f"{out_dir}/final")


if __name__ == "__main__":
    main()
