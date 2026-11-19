"""Generate vault_config/catalog_manifest.json from what really exists (variants, sets, actions, moods, cameras, Mixamo drops).
The showrunner reads ONLY this file (~800 tokens) to write a shotlist."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "vault_config" / "presets"


def main():
    var = json.loads((CFG / "actor_variants.json").read_text(encoding="utf-8"))
    actors = {v["id"]: v["label"] for v in var["variants"]}
    mx = json.loads((CFG / "mixamo_registry.json").read_text()) if (CFG / "mixamo_registry.json").exists() else {"actors": {}, "actions": {}}
    for k, v in mx["actors"].items():
        actors[k] = f"Mixamo character ({v['rig']})"
    sets = {}
    for f in sorted((CFG / "sets").glob("*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        sets[r["id"]] = {"about": r["label"], "anchors": {k: v.get("kind", "standing") for k, v in r["anchors"].items()},
                         "moods": list(r.get("hdri", {}))}
    src = (ROOT / "engine" / "actions_q.py").read_text(encoding="utf-8")
    upper = sorted(re.findall(r'^T\["(\w+)"\] = dict\(loop=(?:True|False), length=[\d.]+, keys', src, re.M))
    full = sorted(re.findall(r'^T\["(\w+)"\] = dict\(loop=(?:True|False), length=[\d.]+, upper_only=False', src, re.M))
    upper = [a for a in upper if a not in full]
    emotes = re.findall(r'^\s*"(\w+)": \{', src.split("EMOTES = {")[1] if "EMOTES" in src else "", re.M)
    comp = (ROOT / "engine" / "stage_compiler.py").read_text(encoding="utf-8")
    emotes = sorted(set(re.findall(r'"(\w+)": \{(?:[^{}]*)\}', comp.split("EMOTES = {")[1].split("ALIASES")[0])))
    cams = json.loads((CFG / "cameras" / "presets.json").read_text())
    man = {
        "actors": actors,
        "sets": sets,
        "base_clips": ["idle", "walk", "run", "wave", "interact", "sit_idle", "sit_talk"] + sorted(mx["actions"]),
        "upper_body_actions": upper,
        "emotes": emotes,
        "moods": list(json.loads((CFG / "lighting/moods.json").read_text())),
        "cameras": {k: v["kind"] for k, v in cams.items()},
        "camera_notes": {"OTS": "needs over+at actor ids; DoF on speaker eyes", "CloseUp": "focus=actor; flip=-1 mirrors side",
                         "others": "focus=[actors]"},
        "ui_contract": {"subject_zone": ["left_third", "center", "right_third"], "ui_safe_zone": ["right_third", "top_left", "none"],
                        "rule": "callouts have NO x/y - they are auto-placed inside ui_safe_zone; shots with callouts need ui_safe_zone != none"},
        "callouts": ["card", "icon", "stat", "bars", "kinetic", "lower"],
        "voices": ["Zira", "David"],
        "anchor_kinds": ["standing", "sitting", "path"],
        "shot_schema": ".claude/skills/shotlist-schema.md",
    }
    out = ROOT / "vault_config" / "catalog_manifest.json"
    out.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print("[catalog] wrote", out)


if __name__ == "__main__":
    main()
