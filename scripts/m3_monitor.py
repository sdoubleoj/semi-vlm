"""학습 중 GPU util/VRAM 주기 로깅 — util이 낮게 유지되면 dataloader(CPU) 병목 신호."""
import argparse
import csv
import subprocess
import time
from pathlib import Path

QUERY = "index,utilization.gpu,memory.used,memory.total"

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--out", default="logs/gpu_monitor.csv")
    args = ap.parse_args()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "a", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ts", "gpu", "util_pct", "mem_used_mib", "mem_total_mib"])
        while True:
            out = subprocess.run(
                ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader,nounits"],
                capture_output=True, text=True,
            ).stdout
            ts = time.strftime("%Y-%m-%dT%H:%M:%S")
            for line in out.strip().splitlines():
                idx, util, used, total = [x.strip() for x in line.split(",")]
                writer.writerow([ts, idx, util, used, total])
                if int(util) < 50:
                    print(f"[{ts}] GPU{idx} util {util}% — dataloader 병목 의심")
            fh.flush()
            time.sleep(args.interval)
