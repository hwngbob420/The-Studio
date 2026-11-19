"""python engine/cast.py <variant_id> - (re)build one actor from vault_config/presets/actor_variants.json and refresh the catalog.
Add a new person = add a variant entry (base rig + skin/hair/eye/palette/accessories/height), then run this."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_paths import ROOT, run_blender  # noqa: E402

run_blender(ROOT / "engine/ingest_actor.py", [sys.argv[1]])
subprocess.run([sys.executable, "-I", str(ROOT / "engine/catalog_gen.py")], check=True)
