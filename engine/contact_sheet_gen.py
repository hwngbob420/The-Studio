"""One still per shot -> ONE contact_sheet.jpg the director reads instead of watching video (token-minimal).
Usage: python contact_sheet_gen.py <episode_dir> [--cols 3] [--frac 0.5]"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_paths import run_blender  # noqa: E402

WORKER = Path(__file__).resolve().parent / "render_worker.py"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode_dir")
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--frac", type=float, default=0.5)
    ap.add_argument("--pct", type=int, default=50)
    a = ap.parse_args()
    ep_dir = Path(a.episode_dir).resolve()
    ep = json.loads((ep_dir / "episode_shotlist.json").read_text(encoding="utf-8"))
    ids = [s["id"] for s in ep["shots"]]
    shots = [str(ep_dir / "shots" / f"{i}.blend") for i in ids]
    stills = ep_dir / "cache" / "stills"
    run_blender(WORKER, ["still", stills, a.pct, a.frac, *shots])
    n = len(ids)
    rows = (n + a.cols - 1) // a.cols
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for i in ids:
        cmd += ["-i", str(stills / f"{i}.png")]
    labels = []
    for k, i in enumerate(ids):
        labels.append(f"[{k}:v]drawtext=text='{i}':x=8:y=8:fontsize=26:fontcolor=white:box=1:boxcolor=black@0.6:"
                      f"boxborderw=5[v{k}]")
    layout = "|".join(f"{(k % a.cols)}*w0_{(k // a.cols)}*h0".replace("*", "*") for k in range(n))
    layout = "|".join(f"{'+'.join(['w0'] * (k % a.cols)) or '0'}_{'+'.join(['h0'] * (k // a.cols)) or '0'}"
                      for k in range(n))
    fc = ";".join(labels) + ";" + "".join(f"[v{k}]" for k in range(n))
    fc += f"xstack=inputs={n}:layout={layout}:fill=black[o]" if n > 1 else ""
    if n == 1:
        fc = labels[0].replace("[v0]", "[o]")
    out = ep_dir / "contact_sheet.jpg"
    cmd += ["-filter_complex", fc, "-map", "[o]", "-q:v", "3", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        # drawtext needs a font on some builds: fall back to unlabeled sheet
        fc2 = "".join(f"[{k}:v]" for k in range(n)) + (f"xstack=inputs={n}:layout={layout}:fill=black[o]" if n > 1 else "null[o]")
        cmd2 = ["ffmpeg", "-y", "-loglevel", "error"] + cmd[4:4 + 2 * n] + ["-filter_complex", fc2, "-map", "[o]", "-q:v", "3", str(out)]
        subprocess.run(cmd2, check=True)
    print("[contact_sheet] ", out)


if __name__ == "__main__":
    main()
