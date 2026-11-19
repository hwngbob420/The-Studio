"""Mixamo auto-ingestor + retargeter.   python engine/ingest_mixamo.py [--watch]
Drop .fbx files from Adobe Mixamo (free login, done by YOU in a browser) into  asset_vault/mixamo_inbox/ :
  * CHARACTER fbx  ("With Skin", T-pose, e.g. Louise, Remy, AJ, Megan, Leonard)
        -> imported, scaled to metres + grounded, materials cleaned and re-skinned with the V2 toon shader, ink outline,
           saved to asset_vault/actors/<name>.blend and registered in vault_config/presets/mixamo_registry.json
        -> portrait thumbnail asset_vault/thumbs/<name>.png
  * ANIMATION fbx ("Without Skin", e.g. Talking, Shrugging, Sitting Tired, Drinking Coffee, Laughing)
        -> retargeted by DIRECTION (limb direction vectors, same maths as our own library) onto the Studio rig, baked to an
           NLA-ready action 'mx_<name>' appended to asset_vault/actions/library_q.blend, registered in the manifest.
Every ingested file is moved to asset_vault/mixamo_inbox/done/. Then:  python engine/catalog_gen.py  (done automatically).
Runs Blender headless for each file; this same file is the Blender-side worker (it detects bpy)."""
import json
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "asset_vault" / "mixamo_inbox"
REGISTRY = ROOT / "vault_config" / "presets" / "mixamo_registry.json"

# Studio rig bone  ->  Mixamo bone (without the 'mixamorig:' prefix)
BONE_MAP = {
    "Body": "Hips", "Abdomen": "Spine", "Torso": "Spine1", "Chest": "Spine2", "Neck": "Neck", "Head": "Head",
    "Shoulder.L": "LeftShoulder", "UpperArm.L": "LeftArm", "LowerArm.L": "LeftForeArm", "Wrist.L": "LeftHand",
    "Shoulder.R": "RightShoulder", "UpperArm.R": "RightArm", "LowerArm.R": "RightForeArm", "Wrist.R": "RightHand",
    "UpperLeg.L": "LeftUpLeg", "LowerLeg.L": "LeftLeg", "Foot.L": "LeftFoot",
    "UpperLeg.R": "RightUpLeg", "LowerLeg.R": "RightLeg", "Foot.R": "RightFoot",
}
# retarget order (parents first): limb bones aim along the source bone's direction (child head - own head)
CHAIN = [("Abdomen", "Torso"), ("Torso", "Chest"), ("Chest", "Neck"), ("Neck", "Head"),
         ("UpperArm.L", "LowerArm.L"), ("LowerArm.L", "Wrist.L"), ("UpperArm.R", "LowerArm.R"), ("LowerArm.R", "Wrist.R"),
         ("UpperLeg.L", "LowerLeg.L"), ("LowerLeg.L", "Foot.L"), ("UpperLeg.R", "LowerLeg.R"), ("LowerLeg.R", "Foot.R")]


def launcher():
    from studio_paths import find_blender
    INBOX.mkdir(parents=True, exist_ok=True)
    (INBOX / "done").mkdir(exist_ok=True)

    def sweep():
        files = sorted(INBOX.glob("*.fbx"))
        for f in files:
            print("[ingest_mixamo]", f.name)
            r = subprocess.run([find_blender(), "-b", "--python", str(Path(__file__).resolve()), "--", str(f)])
            if r.returncode == 0:
                shutil.move(str(f), INBOX / "done" / f.name)
        if files:
            subprocess.run([sys.executable, "-I", str(ROOT / "engine" / "catalog_gen.py")])
        return len(files)

    if "--watch" in sys.argv:
        print("watching", INBOX, "(Ctrl+C to stop)")
        while True:
            sweep()
            time.sleep(5)
    else:
        n = sweep()
        print(f"[ingest_mixamo] {n} file(s) processed" if n else f"[ingest_mixamo] inbox empty: {INBOX}")


# ---------------------------------------------------------------- Blender side
def blender_main():
    import bpy
    from mathutils import Vector
    sys.path.insert(0, str(ROOT / "engine"))
    sys.path.insert(0, str(ROOT / "vault_config" / "shaders"))
    import master_toon as toon
    from actions_lib import fcurves_of

    fbx = Path(sys.argv[sys.argv.index("--") + 1])
    name = "".join(ch if ch.isalnum() else "_" for ch in fbx.stem.lower()).strip("_")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=False)
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    reg = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"actors": {}, "actions": {}}

    if meshes:                                         # ---------- character
        bpy.context.view_layer.update()
        for o in [arm] + meshes:                       # cm -> m, apply, ground
            o.select_set(True)
        k = 0.01 if arm.dimensions.z > 20 else 1.0
        arm.scale = (arm.scale[0] * k,) * 3
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.context.view_layer.update()
        zs = [(o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box]
        h = max(zs) - min(zs)
        s = 1.75 / h
        arm.scale = (s,) * 3
        arm.location.z -= min(zs) * s
        for o in meshes:
            for slot in o.material_slots:
                m = slot.material
                if not m or not m.node_tree:
                    continue
                bs = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                col, tex = (0.8, 0.8, 0.8, 1), None
                if bs:
                    col = tuple(bs.inputs["Base Color"].default_value)
                    lk = bs.inputs["Base Color"].links
                    if lk and lk[0].from_node.type == "TEX_IMAGE":
                        img = lk[0].from_node.image
                        if img.packed_file or not img.filepath:
                            out = ROOT / "asset_vault" / "_unpacked" / f"{name}_{img.name}.png"
                            out.parent.mkdir(parents=True, exist_ok=True)
                            img.filepath_raw = str(out)
                            img.file_format = "PNG"
                            img.save()
                        tex = bpy.path.abspath(img.filepath)
                cut = bool(bs and bs.inputs["Alpha"].links)
                slot.material = toon.toon_material(f"{name}_{m.name}", col, texture=tex, cutout=cut, saturate=1.05)
            for p in o.data.polygons:
                p.use_smooth = True
            toon.add_outline(o, 0.0045)
        arm["studio_actor"], arm["rig_profile"] = name, "mixamo"
        arm.name = f"{name}.rig"
        if arm.animation_data:
            arm.animation_data_clear()
        out = ROOT / "asset_vault" / "actors" / f"{name}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(out))
        # portrait thumbnail
        scn = bpy.context.scene
        toon.hdri_world(next((ROOT / "asset_vault" / "_hdri").glob("*.hdr")), 1.0)
        sun = bpy.data.lights.new("k", "SUN")
        sun.energy = 3
        so = bpy.data.objects.new("k", sun)
        scn.collection.objects.link(so)
        so.rotation_euler = (0.9, 0, -0.5)
        cam = bpy.data.cameras.new("c")
        cam.lens = 70
        co = bpy.data.objects.new("c", cam)
        scn.collection.objects.link(co)
        scn.camera = co
        top = max(zs) * s - min(zs) * s
        co.location = (0, -2.6, top - 0.18)
        co.rotation_euler = (math.radians(90), 0, 0)
        scn.render.engine = "BLENDER_EEVEE"
        scn.render.resolution_x = scn.render.resolution_y = 256
        thumbs = ROOT / "asset_vault" / "thumbs"
        thumbs.mkdir(exist_ok=True)
        scn.render.filepath = str(thumbs / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        reg["actors"][name] = {"rig": "mixamo", "file": f"asset_vault/actors/{name}.blend", "height": 1.75,
                               "note": "Mixamo character: body language via retargeted mx_* actions; no face rig (head/eyes by bone)."}
        print("[ingest_mixamo] character ->", out)
    else:                                              # ---------- animation: retarget by direction onto the Studio rig
        src = arm
        action = src.animation_data.action if src.animation_data else None
        fps = bpy.context.scene.render.fps
        f0, f1 = (int(action.frame_range[0]), int(action.frame_range[1])) if action else (1, 1)
        pre = "mixamorig:" if any(b.name.startswith("mixamorig:") for b in src.data.bones) else ""
        actor_files = sorted((ROOT / "asset_vault" / "actors").glob("*.blend"))
        quat = next(f for f in actor_files if f.stem not in reg.get("actors", {}))
        src_pose = {n: pre + m for n, m in BONE_MAP.items() if (pre + m) in src.pose.bones}
        # world-space direction of each source segment over time
        dirs, hips = {}, {}
        for fr in range(f0, f1 + 1):
            bpy.context.scene.frame_set(fr)
            bpy.context.view_layer.update()
            d = {}
            for a, b in CHAIN:
                if a in src_pose and b in src_pose:
                    ha = src.matrix_world @ src.pose.bones[src_pose[a]].head
                    hb = src.matrix_world @ src.pose.bones[src_pose[b]].head
                    d[a] = (hb - ha).normalized()
            dirs[fr] = d
            if "Body" in src_pose:
                hips[fr] = src.matrix_world @ src.pose.bones[src_pose["Body"]].head
        src_h = max((src.matrix_world @ src.pose.bones[src_pose["Head"]].head).z, 1e-3) if "Head" in src_pose else 1.5
        # build on the Studio rig
        import actions_q
        bpy.ops.wm.open_mainfile(filepath=str(ROOT / "asset_vault" / "actions" / "library_q.blend"))
        bpy.ops.wm.append(directory=str(quat) + "/Object/", filename=next(
            o for o in ["%s.rig" % quat.stem]))
        dst = bpy.data.objects[f"{quat.stem}.rig"]
        bpy.context.view_layer.objects.active = dst
        bpy.ops.object.mode_set(mode="POSE")
        dst.animation_data_create()
        act = bpy.data.actions.new(f"mx_{name}")
        dst.animation_data.action = act
        flip = -1.0 if (hips and (hips[f0].y - hips[f1].y) < 0 and False) else 1.0
        base_hips = hips[f0] if hips else Vector()
        dst_h = (dst.matrix_world @ dst.data.bones["Head"].head_local).z
        for fr in range(f0, f1 + 1):
            actions_q.reset_pose(dst, None)
            for a, b in CHAIN:
                if a in dirs[fr]:
                    actions_q.aim(dst, a, dirs[fr][a])
            if hips:
                dz = (hips[fr] - base_hips) * (dst_h / src_h)
                actions_q.shift_bone(dst, "Body", (dz.x, dz.y, dz.z))
            kf = int(round((fr - f0) * 60.0 / fps)) + 1
            for pb in dst.pose.bones:
                pb.keyframe_insert("rotation_quaternion", frame=kf, group=pb.name)
            if hips:
                dst.pose.bones["Body"].keyframe_insert("location", frame=kf, group="Body")
        bpy.ops.object.mode_set(mode="OBJECT")
        act["loop"], act["length"], act["upper_only"], act["mixamo"] = False, (f1 - f0) / fps, False, True
        act.use_fake_user = True
        dst.animation_data.action = None
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o)
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "asset_vault" / "actions" / "library_q.blend"))
        reg["actions"][f"mx_{name}"] = {"seconds": round((f1 - f0) / fps, 2), "source": fbx.name}
        print("[ingest_mixamo] animation -> mx_" + name)
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=1))


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401
        blender_main()
    except ImportError:
        sys.path.insert(0, str(ROOT / "engine"))
        launcher()
