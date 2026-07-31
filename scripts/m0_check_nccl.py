"""NCCL all-reduce 스모크: torchrun --nproc_per_node=4 scripts/m0_check_nccl.py"""
import os

import torch
import torch.distributed as dist

if __name__ == "__main__":
    dist.init_process_group("nccl")
    rank = dist.get_rank()
    torch.cuda.set_device(rank)
    x = torch.ones(1024, 1024, device=f"cuda:{rank}") * (rank + 1)
    dist.all_reduce(x)
    expected = sum(range(1, dist.get_world_size() + 1))
    ok = torch.allclose(x, torch.full_like(x, float(expected)))
    print(f"[rank {rank}] all_reduce {'OK' if ok else 'FAIL'} (world={dist.get_world_size()})")
    dist.destroy_process_group()
