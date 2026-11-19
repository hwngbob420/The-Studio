"""V2 character ingestor (Blender headless).  Quaternius-style rigged CC0 humans -> Studio actor .blend
  blender -b --python ingest_actor.py -- <variant_id>
Pipeline: import GLB -> clean/scale -> add eye bones + charismatic eyeballs + viseme mouth card + brow shape keys
          -> variant overrides (skin/hair/eye/clothes palette, accessories, height) -> V2 toon + ink hull
          (eyes/brows/mouth excluded from ink) -> save asset_vault/actors/<id>.blend"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
import master_toon as toon  # noqa: E402
from studio_paths import script_args  # noqa: E402

CFG = ROOT / "vault_config" / "presets"


def hexlin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((x + 0.055) / 1.055) ** 2.4 if x > 0.04045 else x / 12.92 for x in c)


# ------------------------------------------------------------------ import + clean
def clean_import(glb):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(glb))
    bpy.context.view_layer.update()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    meshes = [o for o in bpy.data.objects if o.type == "MESH" and o.parent is not None and len(o.data.vertices) > 100]
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o not in meshes:
            bpy.data.objects.remove(o)
    for o in [arm] + meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    for o in list(bpy.data.objects):
        if o.type == "EMPTY":
            bpy.data.objects.remove(o)
    k = arm.scale[0]
    bpy.ops.object.select_all(action="DESELECT")
    for o in [arm] + meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for m in meshes:
        m.parent = arm
        m.matrix_parent_inverse = arm.matrix_world.inverted()
    # actions: root/hips translation keys were authored in the old (cm-like) units
    if abs(k - 1.0) > 1e-6:
        import actions_lib
        for act in bpy.data.actions:
            for fc in actions_lib.fcurves_of(act):
                if fc.data_path.endswith(".location"):
                    for kp in fc.keyframe_points:
                        kp.co[1] *= k
                        kp.handle_left[1] *= k
                        kp.handle_right[1] *= k
    return arm, meshes


def find_head(meshes):
    return next(m for m in meshes if m.name.endswith("_Head"))


# ------------------------------------------------------------------ face
def face_parts(head):
    """-> (eye_mat_idx, brow_mat_idx|None). Eyes = the 24-face feature material lowest on the face;
    brows = a small material just above/in front of it."""
    me = head.data
    info = []
    for i, m in enumerate(me.materials):
        ps = [p for p in me.polygons if p.material_index == i]
        if ps:
            c = sum((head.matrix_world @ p.center for p in ps), Vector()) / len(ps)
            info.append((i, len(ps), c))
    eyes = sorted([x for x in info if x[1] == 24 and x[2].y < -0.13], key=lambda x: x[2].z)
    eye = eyes[0]
    brow = next((x[0] for x in info if x[0] != eye[0] and x[1] <= 60 and x[2].y < -0.14
                 and 0.002 < x[2].z - eye[2].z < 0.035), None)
    return eye[0], brow


def surface_y(head, x, z):
    """Front-most y of the head mesh at (x,z) via raycast along +Y."""
    inv = head.matrix_world.inverted()
    o = inv @ Vector((x, -1.0, z))
    d = (inv.to_3x3() @ Vector((0, 1, 0))).normalized()
    ok, loc, _, _ = head.ray_cast(o, d)
    return (head.matrix_world @ loc).y if ok else -0.14


def add_bone(arm, name, head_w, tail_w, parent):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones.new(name)
    eb.head, eb.tail = head_w, tail_w
    eb.roll = 0.0
    eb.parent = arm.data.edit_bones[parent]
    eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")


def make_eyes(arm, head, eye_idx, iris_hex, sclera=(1.0, 0.99, 0.96)):
    me = head.data
    ps = [p for p in me.polygons if p.material_index == eye_idx]
    sides = {}
    for p in ps:
        c = head.matrix_world @ p.center
        sides.setdefault("L" if c.x > 0 else "R", []).append(c)
    eyes = {}
    skin_idx = next((i for i, m in enumerate(me.materials) if m and m.name.startswith("Skin")), 0)
    for s, cs in sides.items():
        c = sum(cs, Vector()) / len(cs)
        eyes[s] = Vector((c.x, c.y, c.z))
    for p in ps:           # remove the flat black eye patches: eyeballs replace them
        p.material_index = skin_idx
    r = 0.0150
    objs = {}
    for s, c in eyes.items():
        centre = Vector((c.x * 0.74, c.y - 0.001, c.z))     # the removed eye patch lies exactly on the face surface
        add_bone(arm, f"Eye.{s}", centre, centre + Vector((0, -0.03, 0)), "Head")
        bm = bmesh.new()
        bm.loops.layers.uv.new("UVMap")
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=r, calc_uvs=True)
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "X"))
        for v in bm.verts:
            v.co += centre
        mesh = bpy.data.meshes.new(f"EyeMesh.{s}")
        bm.to_mesh(mesh)
        bm.free()
        ob = bpy.data.objects.new(f"{head.name.split('_')[0]}_Eye.{s}", mesh)
        bpy.context.scene.collection.objects.link(ob)
        ob.parent = arm
        ob.matrix_parent_inverse = arm.matrix_world.inverted()
        ob.vertex_groups.new(name=f"Eye.{s}").add(list(range(len(mesh.vertices))), 1.0, "REPLACE")
        mod = ob.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        for poly in mesh.polygons:
            poly.use_smooth = True
        # shape keys: blink / squint / wide (squash about the eye centre)
        ob.shape_key_add(name="Basis")
        for nm, k in (("blink", 0.06), ("squint", 0.55), ("wide", 1.18)):
            sk = ob.shape_key_add(name=nm)
            for i, v in enumerate(mesh.vertices):
                d = v.co - centre
                sk.data[i].co = centre + Vector((d.x * (1.0 if nm != "wide" else 1.1), d.y, d.z * k))
        zero_keys(ob)
        ob.data.materials.append(eye_material(f"{head.name}_eye", iris_hex, sclera))
        objs[s] = ob
    return eyes, objs


def eye_material(name, iris_hex, sclera):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    uv = t.nodes.new("ShaderNodeTexCoord")
    sep = t.nodes.new("ShaderNodeSeparateXYZ")
    t.links.new(uv.outputs["UV"], sep.inputs[0])
    ramp = t.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    iris = hexlin(iris_hex)
    stops = [(0.0, (*sclera, 1)), (0.715, (*sclera, 1)), (0.735, (0.03, 0.02, 0.02, 1)),
             (0.775, (*iris, 1)), (0.86, (*[c * 0.55 for c in iris], 1)), (0.875, (0.01, 0.01, 0.015, 1)), (1.0, (0.01, 0.01, 0.015, 1))]
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = stops[0]
    el[1].position, el[1].color = stops[1]
    for pos, col in stops[2:]:
        e = el.new(pos)
        e.color = col
    t.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    # catch-light box (small bright dot near the iris upper-left)
    def math_(op, a, b, loc):
        n = t.nodes.new("ShaderNodeMath")
        n.operation = op
        n.location = loc
        return n
    g1 = math_("GREATER_THAN", None, None, (0, -300)); g1.inputs[1].default_value = 0.07
    l1 = math_("LESS_THAN", None, None, (0, -450)); l1.inputs[1].default_value = 0.14
    g2 = math_("GREATER_THAN", None, None, (0, -600)); g2.inputs[1].default_value = 0.915
    l2 = math_("LESS_THAN", None, None, (0, -750)); l2.inputs[1].default_value = 0.955
    for n, ch in ((g1, "X"), (l1, "X"), (g2, "Y"), (l2, "Y")):
        t.links.new(sep.outputs[ch], n.inputs[0])
    m1 = math_("MULTIPLY", None, None, (200, -300)); t.links.new(g1.outputs[0], m1.inputs[0]); t.links.new(l1.outputs[0], m1.inputs[1])
    m2 = math_("MULTIPLY", None, None, (200, -600)); t.links.new(g2.outputs[0], m2.inputs[0]); t.links.new(l2.outputs[0], m2.inputs[1])
    m3 = math_("MULTIPLY", None, None, (400, -450)); t.links.new(m1.outputs[0], m3.inputs[0]); t.links.new(m2.outputs[0], m3.inputs[1])
    mix = t.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[7].default_value = (1, 1, 1, 1)
    t.links.new(m3.outputs[0], mix.inputs["Factor"])
    t.links.new(ramp.outputs["Color"], mix.inputs[6])
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    t.links.new(mix.outputs[2], em.inputs["Color"])
    t.links.new(em.outputs[0], out.inputs[0])
    return m


VISEMES = {  # name: (half_width, open_height, corner_lift, upper_lip_raise)
    "X": (0.0325, 0.0019, 0.0000, 0.0), "A": (0.0312, 0.0008, 0.0000, 0.0), "B": (0.0287, 0.0055, 0.0020, 0.0),
    "C": (0.0300, 0.0117, 0.0000, 0.0), "D": (0.0312, 0.0203, 0.0000, 0.0), "E": (0.0187, 0.0148, 0.0000, 0.0),
    "F": (0.0125, 0.0094, 0.0000, 0.0), "G": (0.0275, 0.0039, 0.0000, 0.0035), "H": (0.0263, 0.0101, 0.0000, 0.0),
    "smile": (0.0000, 0.0000, 0.0085, 0.0), "frown": (0.0000, 0.0000, -0.0075, 0.0), "smirk": (0.0000, 0.0000, 0.0000, 0.0),
}


def zero_keys(ob):
    """Blender 5 creates shape keys at value 1.0 - make every key neutral."""
    if ob.data.shape_keys:
        for k in ob.data.shape_keys.key_blocks:
            if k.name != "Basis":
                k.value = 0.0


def make_mouth(arm, head, eye_z, mouth_hex="#3a1520"):
    me = head.data
    zs = [(head.matrix_world @ v.co) for v in me.vertices if (head.matrix_world @ v.co).y < -0.10]
    chin = min(v.z for v in zs)
    mz = eye_z - 0.43 * (eye_z - chin)
    sy = surface_y(head, 0.0, mz)
    N = 20
    bm = bmesh.new()
    ring = [bm.verts.new((math.cos(2 * math.pi * i / N), sy - 0.0025, mz + math.sin(2 * math.pi * i / N))) for i in range(N)]
    cen = bm.verts.new((0, sy - 0.0025, mz))
    for i in range(N):
        bm.faces.new((cen, ring[(i + 1) % N], ring[i]))
    mesh = bpy.data.meshes.new("MouthMesh")
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(f"{head.name.split('_')[0]}_Mouth", mesh)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()
    ob.vertex_groups.new(name="Head").add(list(range(len(mesh.vertices))), 1.0, "REPLACE")
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    def shape(hw, oh, lift, up):
        pts = []
        for i in range(N):
            a = 2 * math.pi * i / N
            cx, cz = math.cos(a), math.sin(a)
            x = cx * hw
            z = cz * (oh * 0.5 + 0.0006) + (up if cz > 0 else 0)
            z += lift * (abs(cx) ** 2.0) * (1 if True else 0)   # corners rise/fall
            pts.append((x, z))
        return pts

    base = shape(*VISEMES["X"][:4])
    ob.shape_key_add(name="Basis")
    for i, v in enumerate(mesh.vertices):
        if i < N:
            v.co.x, v.co.z = base[i][0], mz + base[i][1]
    ob.data.shape_keys.key_blocks["Basis"].data.foreach_set("co", [c for v in mesh.vertices for c in v.co])
    for nm, (hw, oh, lift, up) in VISEMES.items():
        sk = ob.shape_key_add(name=nm)
        pts = shape(hw if hw else VISEMES["X"][0], oh if hw else VISEMES["X"][1], lift, up)
        for i in range(N):
            sk.data[i].co = Vector((pts[i][0], sy - 0.0025, mz + pts[i][1]))
        sk.data[N].co = Vector((0, sy - 0.0025, mz))
        if nm in ("smile", "frown", "smirk"):
            sk.relative_key = ob.data.shape_keys.key_blocks["Basis"]
    zero_keys(ob)
    ob.data.materials.append(mouth_material(mouth_hex))
    return ob


def mouth_material(hexc):
    if "mouth_mat" in bpy.data.materials:
        return bpy.data.materials["mouth_mat"]
    m = bpy.data.materials.new("mouth_mat")
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*hexlin(hexc), 1)
    t.links.new(em.outputs[0], out.inputs[0])
    return m


def brow_keys(head, brow_idx):
    me = head.data
    if brow_idx is None:
        return
    verts = set()
    for p in me.polygons:
        if p.material_index == brow_idx:
            verts.update(p.vertices)
    head.shape_key_add(name="Basis")
    specs = {"brow_up": (0.0, 0.012, 0.0, 0.012), "brow_down": (0.0, -0.007, 0.0, -0.007),
             "brow_angry": (0.0, -0.013, 0.0, 0.004), "brow_sad": (0.0, 0.012, 0.0, -0.006),
             "brow_skeptic_L": (0.0, 0.014, 0.0, 0.014)}   # (_, inner_dz, _, outer_dz)
    for nm, (_, inner, _, outer) in specs.items():
        sk = head.shape_key_add(name=nm)
        for i in verts:
            x = abs(me.vertices[i].co.x)
            w = min(1.0, x / 0.065)            # 0 = inner end, 1 = outer end
            dz = inner * (1 - w) + outer * w
            if nm == "brow_skeptic_L" and me.vertices[i].co.x < 0:
                dz = 0.0
            sk.data[i].co = me.vertices[i].co + Vector((0, 0, dz))
    zero_keys(head)


def ink_groups(head, brow_idx):
    vg = head.vertex_groups.new(name="ink")
    brow_v = set()
    if brow_idx is not None:
        for p in head.data.polygons:
            if p.material_index == brow_idx:
                brow_v.update(p.vertices)
    vg.add([v.index for v in head.data.vertices if v.index not in brow_v], 1.0, "REPLACE")
    if brow_v:
        vg.add(list(brow_v), 0.0, "REPLACE")


# ------------------------------------------------------------------ variants / styling
def apply_variant(var, base, arm, meshes, head, eye_objs, mouth, brow_idx):
    pal = {}
    for k in base.get("skin_mats", []):
        pal[k] = var["skin"]
    for k in base.get("hair_mats", []):
        pal[k] = var["hair"]
    for k in base.get("brow_mats", []):
        pal[k] = var.get("brow", var["hair"])
    pal.update(var.get("palette", {}))
    mats = {}
    for o in meshes:
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            hexc = pal.get(m.name)
            if m.name not in mats:
                if hexc:
                    col = hexlin(hexc)
                else:
                    bs = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                    col = tuple(bs.inputs["Base Color"].default_value)[:3] if bs else (0.5, 0.5, 0.5)
                mats[m.name] = toon.toon_material(f"{var['id']}_{m.name}", (*col, 1))
            slot.material = mats[m.name]
    for o in meshes:
        for p in o.data.polygons:
            p.use_smooth = True
        o.data.update()
    # hide unwanted parts (e.g. hardhat) by deleting faces of a material
    for matname in var.get("remove_faces_head", []):
        for o in [head]:
            idx = [i for i, m in enumerate(o.data.materials) if m and m.name.endswith(matname)]
            if not idx:
                continue
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in idx], context="FACES")
            bm.to_mesh(o.data)
            bm.free()
    for o in meshes:
        toon.add_outline(o, 0.0045, exclude_group="ink" if o is head else None)
    for s, ob in eye_objs.items():
        pass
    arm.scale = (var.get("height", 1.78) / 1.83,) * 3


def lens_material():
    if "lens_clear" in bpy.data.materials:
        return bpy.data.materials["lens_clear"]
    m = bpy.data.materials.new("lens_clear")
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    tr = t.nodes.new("ShaderNodeBsdfTransparent")
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.75, 0.88, 1.0, 1)
    mix = t.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.10
    t.links.new(tr.outputs[0], mix.inputs[1])
    t.links.new(em.outputs[0], mix.inputs[2])
    t.links.new(mix.outputs[0], out.inputs[0])
    m.surface_render_method = "BLENDED"
    return m


def attach_accessory(arm, acc, tint=None):
    """Real CC0 mesh from Poly Pizza/Poly Haven glTF/glb parented to a bone with an offset."""
    path = acc["file"]
    p = Path(path) if Path(path).is_absolute() else ROOT / path
    before = set(bpy.data.objects)
    if p.suffix.lower() == ".glb" or p.suffix.lower() == ".gltf":
        bpy.ops.import_scene.gltf(filepath=str(p))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in new:
        if o.type == "EMPTY":
            continue
    root = bpy.data.objects.new(f"ACC_{acc['name']}", None)
    bpy.context.scene.collection.objects.link(root)
    for o in new:
        if o.parent is None and o is not root:
            o.parent = root
    bpy.context.view_layer.update()
    zs = [(o.matrix_world @ Vector(c)) for o in meshes for c in o.bound_box]
    size = max(max(v.x for v in zs) - min(v.x for v in zs), max(v.y for v in zs) - min(v.y for v in zs),
               max(v.z for v in zs) - min(v.z for v in zs))
    k = acc.get("width", 0.14) / max(size, 1e-6)
    bone = arm.data.bones[acc.get("bone", "Head")]
    rest_world = arm.matrix_world @ bone.matrix_local                   # bone frame at rest (T-pose)
    root.rotation_euler = [math.radians(a_) for a_ in acc.get("rot", (0, 0, 0))]
    root.scale = (k, k, k)
    root.location = arm.matrix_world @ bone.head_local + Vector(acc.get("offset", (0, -0.09, 0.03)))
    cs = root.constraints.new("CHILD_OF")           # rigid attachment that follows the bone's pose
    cs.target, cs.subtarget = arm, bone.name
    cs.inverse_matrix = rest_world.inverted()
    for o in meshes:
        nslots = len(o.material_slots)
        for i, slot in enumerate(o.material_slots):
            if not slot.material:
                continue
            if acc["name"] == "glasses" and i == nslots - 1:          # last material of these models = the lens
                slot.material = lens_material()
                continue
            bs = next((n for n in slot.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            col = tuple(bs.inputs["Base Color"].default_value) if bs else (0.2, 0.2, 0.2, 1)
            if acc.get("color"):
                col = (*hexlin(acc["color"]), 1)
            slot.material = toon.toon_material(f"acc_{acc['name']}_{slot.material.name}", col)
        if acc["name"] != "glasses":
            toon.add_outline(o, 0.003)
    return root


def build(var_id):
    allv = json.loads((CFG / "actor_variants.json").read_text(encoding="utf-8"))
    var = next(v for v in allv["variants"] if v["id"] == var_id)
    base = allv["bases"][var["base"]]
    from fetch_polypizza import fetch
    glb = fetch(base["poly_pizza"])
    arm, meshes = clean_import(glb)
    head = find_head(meshes)
    eye_idx, brow_idx = face_parts(head)
    bpy.context.view_layer.objects.active = head
    brow_keys(head, brow_idx)
    ink_groups(head, brow_idx)
    eyes, eye_objs = make_eyes(arm, head, eye_idx, var.get("eye", "#4a7fb0"))
    eye_z = sum(e.z for e in eyes.values()) / len(eyes)
    mouth = make_mouth(arm, head, eye_z, var.get("mouth", "#3a1520"))
    apply_variant(var, base, arm, meshes, head, eye_objs, mouth, brow_idx)
    for acc in var.get("accessories", []):
        try:
            attach_accessory(arm, acc)
        except Exception as exc:
            print("[ingest_actor] accessory failed", acc.get("name"), exc)
    if arm.animation_data:
        arm.animation_data_clear()
    for act in list(bpy.data.actions):
        if not act.use_fake_user:
            bpy.data.actions.remove(act)
    arm["studio_actor"] = var["id"]
    arm["studio_height"] = var.get("height", 1.78)
    arm["rig_profile"] = "quaternius62"
    arm.name = f"{var['id']}.rig"
    for o in bpy.data.objects:
        if o is not arm and o.type == "MESH":
            o.name = f"{var['id']}.{o.name}"
    out = ROOT / "asset_vault" / "actors" / f"{var['id']}.blend"
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("[ingest_actor] saved", out)


if __name__ == "__main__":
    for vid in script_args():
        build(vid)
