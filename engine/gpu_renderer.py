"""Local GPU render orchestrator (EEVEE Next). 0 API tokens. Resumable; splits every shot into frame chunks and
renders them with N parallel Blender workers (one Blender process is CPU-bound on modifier/animation evaluation,
so several workers keep the GPU fed).
Usage: python gpu_renderer.py <episode_dir> [--workers 4] [--samples 8] [shot_id ...]"""
import argparse
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_paths import find_blender  # noqa: E402

WORKER = Path(__file__).resolve().parent / "render_worker.py"
FPS = 60


def gpu_report():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return out or "no NVIDIA GPU detected (EEVEE will use whatever GPU/driver Blender finds)"
    except Exception:
        return "nvidia-smi not found (EEVEE will use whatever GPU/driver Blender finds)"


def chunk_job(blender, shot_blend, out_dir, samples, a, b):
    cmd = [blender, "-b", "--python", str(WORKER), "--", "frames", str(out_dir), str(samples),
           str(shot_blend), str(a), str(b)]
    t = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return a, b, time.time() - t, r.returncode, r.stdout[-300:] if r.returncode else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("shots", nargs="*")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=120, help="frames per job")
    a = ap.parse_args()
    ep_dir = Path(a.episode_dir).resolve()
    ep = json.loads((ep_dir / "episode_shotlist.json").read_text(encoding="utf-8"))
    samples = a.samples or ep.get("samples", 8)
    blender = find_blender()
    print("[gpu_renderer] GPU:", gpu_report(), "| workers:", a.workers, "| samples:", samples)
    jobs = []
    total = 0
    for s in ep["shots"]:
        if a.shots and s["id"] not in a.shots:
            continue
        n = int(round(s["dur"] * FPS))
        out_dir = ep_dir / "render" / s["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        blend = ep_dir / "shots" / f"{s['id']}.blend"
        for st in range(1, n + 1, a.chunk):
            en = min(n, st + a.chunk - 1)
            if all((out_dir / f"f_{f:04d}.png").exists() for f in range(st, en + 1)):
                continue
            jobs.append((blend, out_dir, st, en))
        total += n
    print(f"[gpu_renderer] {total} frames, {len(jobs)} jobs to run")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(chunk_job, blender, b, o, samples, st, en) for b, o, st, en in jobs]
        for f in futs:
            st, en, dt, rc, tail = f.result()
            print(f"  frames {st}-{en}: {dt:.0f}s rc={rc}{' ' + tail if rc else ''}")
    wall = time.time() - t0
    print(f"[gpu_renderer] done in {wall:.0f}s wall ({wall / max(total, 1):.2f}s/frame effective)")
    (ep_dir / "render_stats.json").write_text(json.dumps({"frames": total, "wall_s": round(wall, 1),
                                                          "s_per_frame": round(wall / max(total, 1), 3),
                                                          "workers": a.workers, "samples": samples, "gpu": gpu_report()}))


if __name__ == "__main__":
    main()
