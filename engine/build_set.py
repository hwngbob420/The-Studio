"""Headless Blender: build a toon open-backlot set from a JSON recipe -> asset_vault/sets/<id>.blend
Usage: blender -b --python build_set.py -- <recipe.json> [out.blend]
Shell (floor/walls/windows/trees) is procedural architecture; props are CC0 Poly Haven glTF restyled with the
Master Toon. Every set exposes Stage_Anchors (empties named ANCHOR_<name>) and a 'SET' collection."""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
sys.path.insert(0, str(ROOT / "engine"))
import master_toon as toon  # noqa: E402
from studio_paths import script_args  # noqa: E402
from fetch_polyhaven import fetch  # noqa: E402


def hexlin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


def col_of(name):
    return bpy.data.collections.get(name) or _mk_col(name)


def _mk_col(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def to_col(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def box(name, size, pos, color, col, outline=True, emission=0.0, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos, rotation=rot)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(toon.toon_material(f"{name}_m", (*hexlin(color), 1), emission=emission))
    if outline:
        toon.add_outline(o, 0.012)
    to_col(o, col)
    return o


def cyl(name, r, h, pos, color, col, verts=12, outline=True):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=verts, location=pos)
    o = bpy.context.object
    o.name = name
    o.data.materials.append(toon.toon_material(f"{name}_m", (*hexlin(color), 1)))
    if outline:
        toon.add_outline(o, 0.012)
    bpy.ops.object.shade_smooth()
    to_col(o, col)
    return o


def blob(name, r, pos, color, col, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=2, location=pos)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    o.data.materials.append(toon.toon_material(f"{name}_m", (*hexlin(color), 1)))
    toon.add_outline(o, 0.015)
    bpy.ops.object.shade_smooth()
    to_col(o, col)
    return o


def tree(name, pos, col, height=4.0, canopy="#4f9a4a", trunk="#6b4a32"):
    cyl(f"{name}_trunk", 0.13 * height / 4, height * 0.5, (pos[0], pos[1], pos[2] + height * 0.25), trunk, col, 8)
    for i, (dx, dy, dz, s) in enumerate([(0, 0, 0.62, 1.0), (0.45, 0.2, 0.5, 0.7), (-0.4, -0.2, 0.55, 0.75)]):
        blob(f"{name}_c{i}", 0.9 * height / 4 * s, (pos[0] + dx * height / 4, pos[1] + dy * height / 4,
                                                   pos[2] + dz * height), canopy, col, (1, 1, 0.85))


def import_prop(spec, col, rid):
    gltf = fetch(spec["asset"])
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(f"{rid}_{spec['asset']}", None)
    col.objects.link(root)
    for o in new:
        if o.parent is None:
            o.parent = root
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    # restyle
    for o in new:
        if o.type != "MESH":
            continue
        for i, slot in enumerate(o.material_slots):
            m = slot.material
            if m is None or not m.node_tree:
                continue
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            tex = None
            cut = False
            color = (0.7, 0.7, 0.7, 1)
            if bsdf:
                color = tuple(bsdf.inputs["Base Color"].default_value)
                link = bsdf.inputs["Base Color"].links
                if link and link[0].from_node.type == "TEX_IMAGE":
                    tex = link[0].from_node.image
                cut = bool(bsdf.inputs["Alpha"].links)
            tpath = None
            if tex is not None:
                if tex.packed_file or not tex.filepath:
                    out = ROOT / "asset_vault" / "_polyhaven" / "_unpacked" / f"{spec['asset']}_{tex.name}.png"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    tex.filepath_raw = str(out)
                    tex.file_format = "PNG"
                    tex.save()
                tpath = bpy.path.abspath(tex.filepath)
            em = spec.get("emission", 0.0) if "glass" in m.name.lower() or spec.get("lit") else 0.0
            nm = toon.toon_material(f"{rid}_{spec['asset']}_{m.name}", color, texture=tpath, cutout=cut, emission=em)
            slot.material = nm
        if not any(md.type == "SOLIDIFY" for md in o.modifiers) and spec.get("outline", True):
            toon.add_outline(o, 0.006)
    # transform
    bpy.context.view_layer.update()
    if "height" in spec:
        zs = [(o.matrix_world @ Vector(c)).z for o in new if o.type == "MESH" for c in o.bound_box]
        h = max(zs) - min(zs)
        if h > 1e-6:
            root.scale = (spec["height"] / h,) * 3
    else:
        root.scale = (spec.get("scale", 1.0),) * 3
    root.location = spec["pos"]
    root.rotation_euler = (0, 0, math.radians(spec.get("rot", 0)))
    return root


def window_wall(name, axis_len, height, thick, pos, rot, color, windows, col):
    """Wall along local X with rectangular window cutouts built from boxes. windows: [(x_center, w, z_bottom, h)]."""
    segs = []
    xs = sorted(windows, key=lambda w: w[0])
    cur = -axis_len / 2
    for k, (xc, w, zb, wh) in enumerate(xs):
        x0, x1 = xc - w / 2, xc + w / 2
        if x0 > cur:
            segs.append((cur, x0, 0, height))
        segs.append((x0, x1, 0, zb))
        segs.append((x0, x1, zb + wh, height))
        cur = x1
    if cur < axis_len / 2:
        segs.append((cur, axis_len / 2, 0, height))
    import mathutils
    r = mathutils.Matrix.Rotation(math.radians(rot), 4, "Z")
    for k, (a, b, z0, z1) in enumerate(segs):
        if b - a < 1e-3 or z1 - z0 < 1e-3:
            continue
        local = Vector(((a + b) / 2, 0, (z0 + z1) / 2))
        wp = Vector(pos) + (r @ local)
        box(f"{name}_{k}", (b - a, thick, z1 - z0), wp, color, col, rot=(0, 0, math.radians(rot)))
    for k, (xc, w, zb, wh) in enumerate(windows):  # glowing glass
        local = Vector((xc, 0, zb + wh / 2))
        wp = Vector(pos) + (r @ local)
        box(f"{name}_glass{k}", (w, 0.02, wh), wp, "#bfdcff", col, outline=False, emission=0.55, rot=(0, 0, math.radians(rot)))
        box(f"{name}_frame{k}", (w + 0.08, thick * 1.1, 0.06), wp + r @ Vector((0, 0, wh / 2)), "#f3efe6", col, outline=False,
            rot=(0, 0, math.radians(rot)))


def build_interior(rec, col):
    W, D, H = rec["size"]
    sh = rec["shell"]
    box("floor", (W + 0.4, D + 0.4, 0.1), (0, 0, -0.05), sh["floor"], col)
    if sh.get("rug"):
        box("rug", (sh["rug"]["w"], sh["rug"]["d"], 0.02), (*sh["rug"]["pos"], 0.01), sh["rug"]["color"], col)
    box("wall_L", (0.15, D, H), (-W / 2, 0, H / 2), sh["walls"], col)
    box("wall_R", (0.15, D, H), (W / 2, 0, H / 2), sh["walls"], col)
    window_wall("wall_back", W, H, 0.15, (0, D / 2, 0), 0, sh["walls"],
                [tuple(w) for w in sh.get("windows", [])], col)
    box("baseboard", (W, 0.04, 0.12), (0, D / 2 - 0.08, 0.06), sh.get("trim", "#f3efe6"), col, outline=False)
    if sh.get("ceiling"):
        box("ceiling", (W + 0.4, D + 0.4, 0.1), (0, 0, H + 0.05), sh["walls"], col)


def build_street(rec, col):
    W, D, H = rec["size"]
    sh = rec["shell"]
    box("ground", (W, D, 0.1), (0, 0, -0.05), sh["ground"], col, outline=False)
    box("sidewalk", (W, 2.2, 0.16), (0, D / 2 - 1.1 - sh.get("walk_offset", 0), 0.0), sh["sidewalk"], col)
    for i, b in enumerate(sh.get("buildings", [])):
        box(f"bld{i}", tuple(b["size"]), tuple(b["pos"]), b["color"], col)
        nx = max(1, int(b["size"][0] // 1.8))
        nz = max(1, int((b["size"][2] - 1.0) // 1.7))
        for ix in range(nx):
            for iz in range(nz):
                x = b["pos"][0] - b["size"][0] / 2 + (ix + 0.5) * b["size"][0] / nx
                z = 1.5 + iz * 1.7
                if z + 0.5 > b["size"][2]:
                    continue
                lit = ((ix * 7 + iz * 3 + i) % 3 == 0)
                box(f"bld{i}_w{ix}_{iz}", (0.9, 0.04, 1.05), (x, b["pos"][1] - b["size"][1] / 2 - 0.02, z),
                    "#ffd98a" if lit else "#8fb4d0", col, outline=False, emission=0.7 if lit else 0.1)
    for i, t in enumerate(sh.get("trees", [])):
        tree(f"tree{i}", t["pos"], col, t.get("h", 4.0), t.get("canopy", "#4f9a4a"))


def build_park(rec, col):
    W, D, H = rec["size"]
    sh = rec["shell"]
    box("grass", (W, D, 0.1), (0, 0, -0.05), sh["ground"], col, outline=False)
    for i, p in enumerate(sh.get("paths", [])):
        box(f"path{i}", tuple(p["size"]), (p["pos"][0], p["pos"][1], 0.01), p["color"], col, outline=False)
    for i, t in enumerate(sh.get("trees", [])):
        tree(f"tree{i}", t["pos"], col, t.get("h", 4.0), t.get("canopy", "#4f9a4a"))
    for i, hll in enumerate(sh.get("hills", [])):
        blob(f"hill{i}", hll["r"], tuple(hll["pos"]), hll["color"], col, tuple(hll.get("scale", (1, 1, 0.35))))
    box("backdrop", (W * 1.6, 0.1, 14), (0, D / 2 + 6, 7), sh.get("sky", "#9fd0f0"), col, outline=False, emission=0.5)


KINDS = {"interior": build_interior, "street": build_street, "park": build_park}


def main():
    a = script_args()
    rec = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    out = Path(a[1]) if len(a) > 1 else ROOT / "asset_vault" / "sets" / f"{rec['id']}.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = _mk_col("SET")
    KINDS[rec["kind"]](rec, col)
    for i, p in enumerate(rec.get("props", [])):
        try:
            import_prop(p, col, rec["id"])
        except Exception as exc:
            print(f"[build_set] skip prop {p.get('asset')}: {exc}")
    for name, an in rec["anchors"].items():
        e = bpy.data.objects.new(f"ANCHOR_{name}", None)
        e.empty_display_type = "ARROWS"
        e.location = an["pos"]
        e.rotation_euler = (0, 0, math.radians(an.get("rot", 0)))
        col.objects.link(e)
    root = bpy.data.objects.new("SET_META", None)
    root["set_id"] = rec["id"]
    root["kind"] = rec["kind"]
    root["moods"] = json.dumps(rec.get("moods", ["day"]))
    col.objects.link(root)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("[build_set] saved", out)


main()
