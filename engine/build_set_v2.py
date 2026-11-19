"""V2 set builder - REAL ASSETS ONLY.  blender -b --python build_set_v2.py -- <recipe.json> [out.blend]
Allowed geometry sources: KayKit CC0 packs (buildings, roads, cars, furniture, trees, hills), Poly Haven CC0 models,
AmbientCG CC0 PBR textures (ground / floor / wall SURFACES) and Poly Haven HDRIs (sky + bounce light).
HARD RULE: no houses, trees, cars or furniture from cubes/cylinders/spheres. The only generated geometry is flat
textured surfaces (ground, floor, wall planes with window openings) - there is deliberately no box/sphere helper here.

Recipe:
  {"id","label","kind":"exterior|interior","hdri":{day,golden,night,...: hdri id},
   "surfaces":[{"type":"ground","name","rect":[x0,y0,x1,y1],"z":0,"pbr":"Grass004","tile":6.0}, ...],
   "walls":[{"rect":[x0,y0,x1,y1],"h":2.9,"pbr":"Plaster001","tile":3.0,"windows":[[x_center,width,z_bottom,height]],"axis":"x|y"}],
   "props":[{"src":"kaykit:city_builder:building_A"|"ph:sofa_02","pos":[x,y,z],"rot":deg,"height"|"scale"|"width":v,"ink":true}],
   "anchors":{"A":{"pos":[..],"rot":deg},...},"ground_z":0}"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
sys.path.insert(0, str(ROOT / "engine"))
import master_toon as toon  # noqa: E402
from fetch_ambientcg import color_map  # noqa: E402
from fetch_kaykit import model as kaykit_model  # noqa: E402
from fetch_polyhaven import fetch as ph_fetch  # noqa: E402
from studio_paths import script_args  # noqa: E402


def mkcol(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def surface(name, rect, z, pbr, tile, col, tint=None, vertical=False, axis="x", h=0.0, windows=()):
    """Flat textured surface (ground/floor/wall) with tiled PBR colour map; optional window cut-outs on walls."""
    x0, y0, x1, y1 = rect
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    quads = []
    if not vertical:
        quads.append(((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)))
    else:  # wall along x (axis x, at y=y0) or along y (axis y, at x=x0), height h; windows cut as rectangles
        L = (x1 - x0) if axis == "x" else (y1 - y0)
        def P(s, zz):
            return (x0 + s, y0, zz) if axis == "x" else (x0, y0 + s, zz)
        cuts = sorted(windows)
        # window x-centres are given relative to the wall start
        cur = 0.0
        for (c, w, zb, wh) in cuts:
            a, b = c - w / 2, c + w / 2
            if a > cur:
                quads.append((P(cur, 0), P(a, 0), P(a, h), P(cur, h)))
            quads.append((P(a, 0), P(b, 0), P(b, zb), P(a, zb)))
            quads.append((P(a, zb + wh), P(b, zb + wh), P(b, h), P(a, h)))
            cur = b
        if cur < L:
            quads.append((P(cur, 0), P(L, 0), P(L, h), P(cur, h)))
    for q in quads:
        vs = [bm.verts.new(p) for p in q]
        f = bm.faces.new(vs)
        for loop, v in zip(f.loops, q):
            if not vertical:
                loop[uv].uv = (v[0] / tile, v[1] / tile)
            else:
                s = (v[0] - x0) if axis == "x" else (v[1] - y0)
                loop[uv].uv = (s / tile, v[2] / tile)
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    tex = str(color_map(pbr))
    mat = toon.toon_material(f"{name}_{pbr}", (1, 1, 1, 1), texture=tex, saturate=1.05, value=1.0)
    ob.data.materials.append(mat)
    return ob


def import_gltf(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def restyle(objs, tag, ink=True, ink_w=0.006):
    for o in objs:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None or not m.node_tree:
                continue
            bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            tex, color, cut = None, (0.7, 0.7, 0.7, 1), False
            if bsdf:
                color = tuple(bsdf.inputs["Base Color"].default_value)
                link = bsdf.inputs["Base Color"].links
                if link and link[0].from_node.type == "TEX_IMAGE":
                    img = link[0].from_node.image
                    tex = img
                cut = bool(bsdf.inputs["Alpha"].links)
            tpath = None
            if tex is not None:
                if tex.packed_file or not tex.filepath:
                    out = ROOT / "asset_vault" / "_unpacked" / f"{tag}_{tex.name}.png"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    tex.filepath_raw = str(out)
                    tex.file_format = "PNG"
                    tex.save()
                tpath = bpy.path.abspath(tex.filepath)
            nm = toon.toon_material(f"{tag}_{m.name}", color, texture=tpath, cutout=cut)
            if tpath and tex is not None and tex.size[0] <= 512:   # palette atlases: keep flats crisp
                for n in nm.node_tree.nodes:
                    if n.type == "TEX_IMAGE":
                        n.interpolation = "Closest"
            slot.material = nm
        for p in o.data.polygons:
            p.use_smooth = True
        if ink and not any(md.type == "SOLIDIFY" for md in o.modifiers):
            toon.add_outline(o, ink_w)


def place(spec, col, rid, i):
    kind, *rest = spec["src"].split(":")
    if kind == "kaykit":
        path = kaykit_model(rest[0], rest[1])
        tag = f"{rid}_{rest[1]}"
    else:
        path = ph_fetch(rest[0])
        tag = f"{rid}_{rest[0]}"
    objs = import_gltf(path)
    root = bpy.data.objects.new(f"{tag}_{i}", None)
    col.objects.link(root)
    for o in objs:
        if o.parent is None:
            o.parent = root
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    restyle(objs, tag, ink=spec.get("ink", True), ink_w=spec.get("ink_w", 0.006))
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    mn = Vector([min(p[k] for p in pts) for k in range(3)])
    mx = Vector([max(p[k] for p in pts) for k in range(3)])
    size = mx - mn
    if "height" in spec:
        k = spec["height"] / max(size.z, 1e-6)
    elif "width" in spec:
        k = spec["width"] / max(size.x, 1e-6)
    else:
        k = spec.get("scale", 1.0)
    root.scale = (k, k, k)
    root.rotation_euler = (0, 0, math.radians(spec.get("rot", 0)))
    # sit the model's lowest point exactly on z (ground contact)
    root.location = (spec["pos"][0], spec["pos"][1], spec["pos"][2] - mn.z * k if spec.get("ground", True) else spec["pos"][2])
    return root


def main():
    a = script_args()
    rec = json.loads(Path(a[0]).read_text(encoding="utf-8"))
    out = Path(a[1]) if len(a) > 1 else ROOT / "asset_vault" / "sets" / f"{rec['id']}.blend"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    col = mkcol("SET")
    for s in rec.get("surfaces", []):
        surface(s["name"], s["rect"], s.get("z", 0.0), s["pbr"], s.get("tile", 4.0), col)
    for i, w in enumerate(rec.get("walls", [])):
        r = w["rect"]
        surface(f"wall{i}", r, 0.0, w["pbr"], w.get("tile", 3.0), col, vertical=True, axis=w.get("axis", "x"), h=w["h"],
                windows=[tuple(x) for x in w.get("windows", [])])
        for (c, wd, zb, wh) in w.get("windows", []):      # glowing glass pane = emissive plane inside the opening
            s0 = r[0] if w.get("axis", "x") == "x" else r[1]
            bm = bmesh.new()
            if w.get("axis", "x") == "x":
                pts = [(r[0] + c - wd / 2, r[1] + 0.02, zb), (r[0] + c + wd / 2, r[1] + 0.02, zb),
                       (r[0] + c + wd / 2, r[1] + 0.02, zb + wh), (r[0] + c - wd / 2, r[1] + 0.02, zb + wh)]
            else:
                pts = [(r[0] + 0.02, r[1] + c - wd / 2, zb), (r[0] + 0.02, r[1] + c + wd / 2, zb),
                       (r[0] + 0.02, r[1] + c + wd / 2, zb + wh), (r[0] + 0.02, r[1] + c - wd / 2, zb + wh)]
            bm.faces.new([bm.verts.new(p) for p in pts])
            me = bpy.data.meshes.new("glass")
            bm.to_mesh(me)
            bm.free()
            g = bpy.data.objects.new("glass", me)
            col.objects.link(g)
            g.data.materials.append(toon.toon_material("window_glass", (0.50, 0.68, 0.95, 1), emission=0.18))
    for i, p in enumerate(rec.get("props", [])):
        try:
            place(p, col, rec["id"], i)
        except Exception as exc:
            print(f"[build_set_v2] SKIP {p.get('src')}: {exc}")
    for name, an in rec["anchors"].items():
        e = bpy.data.objects.new(f"ANCHOR_{name}", None)
        e.empty_display_type = "ARROWS"
        e.location = an["pos"]
        e.rotation_euler = (0, 0, math.radians(an.get("rot", 0)))
        e["kind"] = an.get("kind", "standing")
        col.objects.link(e)
    meta = bpy.data.objects.new("SET_META", None)
    meta["set_id"] = rec["id"]
    meta["kind"] = rec["kind"]
    meta["hdri"] = json.dumps(rec.get("hdri", {}))
    meta["ground_z"] = rec.get("ground_z", 0.0)
    meta["lights"] = json.dumps(rec.get("lights", []))
    col.objects.link(meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("[build_set_v2] saved", out, "props:", len(rec.get("props", [])))


main()
