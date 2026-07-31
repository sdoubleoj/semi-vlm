"""fGPU 실측: GPU별 실가용 VRAM(더미 텐서 점증 할당) + bf16 matmul TFLOPS."""
import time

import torch


def probe_vram(dev: int, step_gb: int = 4) -> int:
    """OOM까지 step_gb 단위로 할당해 실가용 GiB 반환."""
    blocks, allocated = [], 0
    try:
        while True:
            blocks.append(
                torch.empty(step_gb * 1024**3 // 2, dtype=torch.bfloat16, device=f"cuda:{dev}")
            )
            allocated += step_gb
    except torch.cuda.OutOfMemoryError:
        pass
    finally:
        del blocks
        torch.cuda.empty_cache()
    return allocated


def bench_tflops(dev: int, n: int = 8192, iters: int = 30) -> float:
    a = torch.randn(n, n, dtype=torch.bfloat16, device=f"cuda:{dev}")
    b = torch.randn(n, n, dtype=torch.bfloat16, device=f"cuda:{dev}")
    for _ in range(3):
        a @ b
    torch.cuda.synchronize(dev)
    t0 = time.perf_counter()
    for _ in range(iters):
        a @ b
    torch.cuda.synchronize(dev)
    dt = time.perf_counter() - t0
    return 2 * n**3 * iters / dt / 1e12


if __name__ == "__main__":
    for dev in range(torch.cuda.device_count()):
        name = torch.cuda.get_device_name(dev)
        total = torch.cuda.get_device_properties(dev).total_memory / 1024**3
        usable = probe_vram(dev)
        tflops = bench_tflops(dev)
        print(
            f"GPU{dev} {name}: 표기 {total:.0f}GiB / 실가용 ~{usable}GiB / "
            f"bf16 matmul {tflops:.0f} TFLOPS"
        )
