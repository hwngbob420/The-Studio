"""Runs INSIDE Blender. Two modes (sequential over many .blend files in one process = no repeated startup):
  still : blender -b --python render_worker.py -- still <out_dir> <res_pct> <frac> shot1.blend shot2.blend ...
  frames: blender -b --python render_worker.py -- frames <out_dir> <samples> shot.blend [start end]"""
import sys
import time
from pathlib import Path

import bpy


def args():
    return sys.argv[sys.argv.index("--") + 1:]


def pick_gpu():
    """EEVEE Next renders on the GPU through the GPU backend; just report what Blender sees."""
    try:
        import gpu
        return f"{gpu.platform.renderer_get()} [{gpu.platform.backend_type_get()}]"
    except Exception:
        return "unknown"


def main():
    a = args()
    mode, out_dir = a[0], Path(a[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if mode == "still":
        pct, frac, files = int(a[2]), float(a[3]), a[4:]
        for f in files:
            bpy.ops.wm.open_mainfile(filepath=f)
            scn = bpy.context.scene
            scn.render.resolution_percentage = pct
            scn.eevee.taa_render_samples = 16
            frame = int(scn.frame_start + (scn.frame_end - scn.frame_start) * frac)
            scn.frame_set(frame)
            scn.render.filepath = str(out_dir / (Path(f).stem + ".png"))
            bpy.ops.render.render(write_still=True)
            print("[render_worker] still", Path(f).stem, "frame", frame)
    else:
        samples, f = int(a[2]), a[3]
        bpy.ops.wm.open_mainfile(filepath=f)
        scn = bpy.context.scene
        if len(a) > 5:
            scn.frame_start, scn.frame_end = int(a[4]), int(a[5])
        scn.eevee.taa_render_samples = samples
        scn.render.use_overwrite = False        # resumable: existing frames are skipped
        scn.render.use_placeholder = True
        scn.render.filepath = str(out_dir / "f_")
        t = time.time()
        print("[render_worker] GPU:", pick_gpu())
        bpy.ops.render.render(animation=True)
        n = scn.frame_end - scn.frame_start + 1
        print(f"[render_worker] {Path(f).stem}: {n} frames in {time.time() - t:.1f}s ({(time.time() - t) / n:.2f}s/frame)")


main()
