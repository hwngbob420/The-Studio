"""Headless Blender: build one toon actor from a JSON recipe and save it to asset_vault/actors/<id>.blend.
Usage: blender -b --python build_actor.py -- <recipe.json> [out.blend]
Uses MPFB2 (parametric human + default rig w/ face bones) + MakeHuman CC0 assets, restyled with the Master Toon."""
import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
sys.path.insert(0, str(ROOT / "engine"))
import master_toon as toon  # noqa: E402
from studio_paths import script_args  # noqa: E402

from bl_ext.user_default.mpfb.services.humanservice import HumanService  # noqa: E402
from bl_ext.user_default.mpfb.services.locationservice import LocationService  # noqa: E402
from bl_ext.user_default.mpfb.services.targetservice import TargetService  # noqa: E402

FACE_UNITS = {  # shape keys we drive for acting (names resolved per ethnicity below)
    "eyebrows-left-down", "eyebrows-right-down", "eyebrows-left-inner-up", "eyebrows-right-inner-up",
    "eyebrows-left-up", "eyebrows-right-up", "eye-left-closure", "eye-right-closure",
    "mouth-corner-puller", "mouth-depression", "mouth-elevation", "mouth-compression",
}


def asset(kind, name):
    base = Path(LocationService.get_user_data(kind)) if hasattr(LocationService, "get_user_data") else None
    for root in filter(None, [base, Path(LocationService.get_mpfb_data(kind))]):
        hits = list(root.glob(f"{name}/*.mhclo"))
        if hits:
            return str(hits[0])
    raise FileNotFoundError(f"MakeHuman asset not found: {kind}/{name}")


def load_face_units(human, recipe):
    """Load expression face-unit targets as zero-weight shape keys (brows, eye closure, smile/frown...)."""
    race = max(recipe["macro"]["race"].items(), key=lambda kv: kv[1])[0]
    units_dir = Path(LocationService.get_mpfb_data("targets")) / "expression" / "units" / race
    for unit in sorted(FACE_UNITS):
        f = units_dir / f"{unit}.target.gz"
        if f.exists():
            TargetService.load_target(human, str(f), weight=0.0, name=f"face_{unit}")
        else:
            print(f"[build_actor] missing face unit {f.name}")


def build(recipe):
    macro = TargetService.get_default_macro_info_dict()
    macro.update({k: recipe["macro"][k] for k in recipe["macro"] if k != "race"})
    macro["race"] = recipe["macro"]["race"]
    human = HumanService.create_human(mask_helpers=True, detailed_helpers=True, extra_vertex_groups=True,
                                      feet_on_ground=True, scale=0.1, macro_detail_dict=macro)
    human.name = recipe["id"]
    rig = HumanService.add_builtin_rig(human, recipe.get("rig", "default"), import_weights=True)

    attached = []
    for kind, name in [("eyes", recipe.get("eyes", "low-poly")), ("eyebrows", recipe.get("eyebrows", "eyebrow001")),
                       ("eyelashes", recipe.get("eyelashes", "eyelashes02")), ("teeth", "teeth_base"),
                       ("tongue", "tongue01"), ("hair", recipe.get("hair"))]:
        if not name:
            continue
        try:
            obj = HumanService.add_mhclo_asset(asset(kind, name), human, asset_type=kind.capitalize(),
                                               material_type="MAKESKIN")
            attached.append((kind, obj))
        except Exception as exc:  # missing asset must not kill the whole actor
            print(f"[build_actor] skip {kind}/{name}: {exc}")
    for item in recipe.get("clothes", []):
        try:
            obj = HumanService.add_mhclo_asset(asset("clothes", item["asset"]), human, asset_type="Clothes",
                                               material_type="MAKESKIN")
            attached.append(("clothes:" + item.get("color", ""), obj))
            if obj is not None:
                obj["studio_color"] = item.get("color", "#888888")
        except Exception as exc:
            print(f"[build_actor] skip clothes/{item['asset']}: {exc}")
    return human, rig, attached


def optimize(human, attached):
    """Render-speed pass: bake macro shape keys, drop subsurf, decimate heavy clothing (CPU-bound per frame)."""
    from bl_ext.user_default.mpfb.services.targetservice import TargetService as TS
    if human.data.shape_keys:
        TS.bake_targets(human)
    for obj in [human] + [o for _, o in attached if o is not None]:
        for m in list(obj.modifiers):
            if m.type == "SUBSURF":
                obj.modifiers.remove(m)
        if obj.type == "MESH" and obj is not human and len(obj.data.vertices) > 6000:
            dm = obj.modifiers.new("Decimate", "DECIMATE")
            dm.ratio = max(0.08, 5000 / len(obj.data.vertices))
            with bpy.context.temp_override(object=obj, active_object=obj):
                bpy.ops.object.modifier_apply(modifier=dm.name)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def srgb2lin(c):
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def restyle(recipe, human, rig, attached):
    """Replace every material with Master Toon; keep eye textures; add ink hull to body/hair/clothes."""
    skin = srgb2lin(hex_rgb(recipe["skin"]))
    rid = recipe["id"]

    udata = Path(LocationService.get_user_data())

    def swap(obj, color, texture=None, outline=True, key="", **kw):
        if obj is None or obj.type != "MESH":
            return
        obj.data.materials.clear()
        obj.data.materials.append(toon.toon_material(f"{rid}_{key}", (*color, 1), texture=texture, **kw))
        if outline:
            toon.add_outline(obj, 0.0035)

    skin_tex = None
    if recipe.get("skin_tex"):
        hits = list((udata / "skins" / recipe["skin_tex"]).glob("*.png"))
        skin_tex = str(hits[0]) if hits else None
    swap(human, skin, texture=skin_tex, key="skin", posterize=0, saturate=1.05, value=1.35)
    for kind, obj in attached:
        if obj is None:
            continue
        if kind.startswith("clothes:"):
            pm = obj.modifiers.new("Puff", "DISPLACE")   # lift cloth 4 mm so skin never z-fights through it
            pm.strength, pm.mid_level = 0.004, 0.0
            swap(obj, srgb2lin(hex_rgb(obj.get("studio_color", "#888888"))), key=obj.name)
        elif kind == "hair":
            swap(obj, srgb2lin(hex_rgb(recipe.get("hair_color", "#3a2a1e"))), key="hair")
        elif kind == "eyebrows" or kind == "eyelashes":
            swap(obj, srgb2lin(hex_rgb(recipe.get("hair_color", "#2a1d14"))), outline=False, key=kind)
        elif kind == "eyes":
            eye_png = udata / "eyes" / "materials" / f"{recipe.get('eye_tex', 'brown')}_eye.png"
            swap(obj, (1, 1, 1), texture=str(eye_png) if eye_png.exists() else None, outline=False, key="eyes",
                 rim=0.0, bands=2)
        elif kind == "teeth":
            swap(obj, (0.9, 0.88, 0.82), outline=False, key="teeth")
        elif kind == "tongue":
            swap(obj, srgb2lin(hex_rgb("#c0566a")), outline=False, key="tongue")


def main():
    args = script_args()
    recipe = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    out = Path(args[1]) if len(args) > 1 else ROOT / "asset_vault" / "actors" / f"{recipe['id']}.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import addon_utils  # noqa: F401  (MPFB already enabled in user prefs; re-enable after factory reset)
    addon_utils.enable("bl_ext.user_default.mpfb", default_set=False)
    human, rig, attached = build(recipe)
    optimize(human, attached)
    restyle(recipe, human, rig, attached)
    if rig is not None:
        rig["studio_actor"] = recipe["id"]
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("[build_actor] saved", out)


main()
