"""python engine/cast.py <actor_id> - rebuild one actor from its recipe and refresh the catalog."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from studio_paths import ROOT, run_blender  # noqa: E402

run_blender(ROOT / "engine/build_actor.py", [ROOT / "vault_config/presets/actors" / f"{sys.argv[1]}.json"])
subprocess.run([sys.executable, "-I", str(ROOT / "engine/catalog_gen.py")], check=True)
