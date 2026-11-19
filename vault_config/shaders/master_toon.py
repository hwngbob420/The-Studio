"""Master NPR look: banded toon shading + rim light + inverted-hull ink outline (GPU-cheap),
optional Grease Pencil Line Art for static sets. Runs inside Blender (bpy)."""
import math

import bpy

INK = (0.03, 0.02, 0.04, 1.0)


def _n(tree, type_, loc, **props):
    node = tree.nodes.new(type_)
    node.location = loc
    for k, v in props.items():
        setattr(node, k, v)
    return node


def _mix_rgba(tree, loc, blend="MIX"):
    return _n(tree, "ShaderNodeMix", loc, data_type="RGBA", blend_type=blend)


def toon_material(name, color, bands=3, rim=0.22, rim_color=(1.0, 0.93, 0.8), texture=None,
                  shadow_tint=None, cutout=False, emission=0.0, posterize=0, saturate=1.0, value=1.0,
                  cool=(0.60, 0.64, 0.92), mid=(0.93, 0.90, 0.88), warm=(1.14, 1.07, 0.96), steps=(0.18, 0.55)):
    """V2 Western 3-band shader: base x [cool ambient shadow | neutral midtone | warm highlight].
    Bands come from the diffuse term of the scene lights/HDRI (Shader-to-RGB), rim from a fresnel ramp."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    t = mat.node_tree
    t.nodes.clear()
    out = _n(t, "ShaderNodeOutputMaterial", (1200, 0))
    diff = _n(t, "ShaderNodeBsdfDiffuse", (-800, 100))
    s2r = _n(t, "ShaderNodeShaderToRGB", (-600, 100))
    bw = _n(t, "ShaderNodeRGBToBW", (-420, 100))
    ramp = _n(t, "ShaderNodeValToRGB", (-250, 100))
    ramp.color_ramp.interpolation = "LINEAR"           # tiny soft edge between bands (hand-painted feel)
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, (*cool, 1)
    el[1].position, el[1].color = 1.0, (*warm, 1)
    e0 = el.new(steps[0]); e0.color = (*cool, 1)
    e1 = el.new(steps[0] + 0.03); e1.color = (*mid, 1)
    e2 = el.new(steps[1]); e2.color = (*mid, 1)
    e3 = el.new(steps[1] + 0.03); e3.color = (*warm, 1)
    t.links.new(diff.outputs["BSDF"], s2r.inputs["Shader"])
    t.links.new(s2r.outputs["Color"], bw.inputs["Color"])
    t.links.new(bw.outputs["Val"], ramp.inputs["Fac"])

    if texture:
        tex = _n(t, "ShaderNodeTexImage", (-600, 450))
        tex.image = bpy.data.images.load(str(texture), check_existing=True)
        base_out = tex.outputs["Color"]
        if saturate != 1.0 or value != 1.0:
            hs = _n(t, "ShaderNodeHueSaturation", (-400, 450))
            hs.inputs["Saturation"].default_value = saturate
            hs.inputs["Value"].default_value = value
            t.links.new(base_out, hs.inputs["Color"])
            base_out = hs.outputs["Color"]
    else:
        base = _n(t, "ShaderNodeRGB", (-500, 450))
        base.outputs[0].default_value = (*color[:3], 1)
        base_out = base.outputs[0]

    shade = _mix_rgba(t, (200, 300), "MULTIPLY")
    shade.inputs["Factor"].default_value = 1.0
    t.links.new(base_out, shade.inputs[6])
    t.links.new(ramp.outputs["Color"], shade.inputs[7])

    lw = _n(t, "ShaderNodeLayerWeight", (-500, -250))
    lw.inputs["Blend"].default_value = 0.5
    rimramp = _n(t, "ShaderNodeValToRGB", (-250, -250))
    rimramp.color_ramp.interpolation = "LINEAR"
    rimramp.color_ramp.elements[0].position = 0.62
    rimramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    rimramp.color_ramp.elements[1].position = 0.70
    rimramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    t.links.new(lw.outputs["Fresnel"], rimramp.inputs["Fac"])
    rimmix = _mix_rgba(t, (650, 100), "ADD")
    rimmix.inputs[7].default_value = (*(c * rim for c in rim_color), 1)
    t.links.new(rimramp.outputs["Color"], rimmix.inputs["Factor"])
    t.links.new(shade.outputs[2], rimmix.inputs[6])

    emit = _n(t, "ShaderNodeEmission", (850, 100))
    t.links.new(rimmix.outputs[2], emit.inputs["Color"])
    if emission > 0:
        boost = _n(t, "ShaderNodeEmission", (850, -100))
        boost.inputs["Strength"].default_value = emission
        t.links.new(base_out, boost.inputs["Color"])
        add = _n(t, "ShaderNodeAddShader", (1000, 0))
        t.links.new(emit.outputs["Emission"], add.inputs[0])
        t.links.new(boost.outputs["Emission"], add.inputs[1])
        t.links.new(add.outputs[0], out.inputs["Surface"])
    elif cutout and texture:
        tr = _n(t, "ShaderNodeBsdfTransparent", (850, -150))
        mix = _n(t, "ShaderNodeMixShader", (1000, 0))
        t.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        t.links.new(tr.outputs[0], mix.inputs[1])
        t.links.new(emit.outputs["Emission"], mix.inputs[2])
        t.links.new(mix.outputs[0], out.inputs["Surface"])
        mat.surface_render_method = "DITHERED"
    else:
        t.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def hdri_world(path, strength=1.0, tint=None, rotation_deg=0.0):
    """Real Poly Haven HDRI as sky + bounce light."""
    scn = bpy.context.scene
    w = scn.world or bpy.data.worlds.new("World")
    scn.world = w
    w.use_nodes = True
    t = w.node_tree
    t.nodes.clear()
    out = _n(t, "ShaderNodeOutputWorld", (600, 0))
    bg = _n(t, "ShaderNodeBackground", (400, 0))
    env = _n(t, "ShaderNodeTexEnvironment", (0, 0))
    env.image = bpy.data.images.load(str(path), check_existing=True)
    mp = _n(t, "ShaderNodeMapping", (-250, 0))
    mp.inputs["Rotation"].default_value[2] = math.radians(rotation_deg)
    tc = _n(t, "ShaderNodeTexCoord", (-450, 0))
    t.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    t.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    last = env.outputs["Color"]
    if tint:
        mx = _mix_rgba(t, (200, 0), "MULTIPLY")
        mx.inputs["Factor"].default_value = 1.0
        mx.inputs[7].default_value = (*tint, 1)
        t.links.new(last, mx.inputs[6])
        last = mx.outputs[2]
    t.links.new(last, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    t.links.new(bg.outputs[0], out.inputs[0])


def ink_material(name="Ink"):
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    t = m.node_tree
    t.nodes.clear()
    out = t.nodes.new("ShaderNodeOutputMaterial")
    em = t.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = INK
    t.links.new(em.outputs[0], out.inputs[0])
    m.use_backface_culling = True
    return m


def add_outline(obj, thickness=0.004, name="InkHull", exclude_group=None):
    """Inverted-hull outline: flipped solidify + ink-only slot with backface culling. GPU-cheap."""
    if name in obj.modifiers:
        return None
    ink = ink_material()
    obj.data.materials.append(ink)
    idx = len(obj.data.materials) - 1
    mod = obj.modifiers.new(name, "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 1.0
    mod.use_flip_normals = True
    mod.use_rim = False
    mod.material_offset = idx
    if exclude_group:   # weight-0 verts get zero thickness -> no ink on eyes/brows/mouth
        mod.vertex_group = exclude_group
        mod.thickness_vertex_group = 0.0
    return mod


def add_lineart(target, thickness=6, name="LineArt"):
    """Grease Pencil v3 Line Art for static geometry (sets). CPU-recomputed per frame -> sets only."""
    is_col = isinstance(target, bpy.types.Collection)
    bpy.ops.object.grease_pencil_add(type="LINEART_COLLECTION" if is_col else "LINEART_OBJECT")
    gp = bpy.context.object
    gp.name = name
    for m in gp.modifiers:
        if m.type == "LINEART":
            if is_col:
                m.source_type = "COLLECTION"
                m.source_collection = target
            else:
                m.source_type = "OBJECT"
                m.source_object = target
            m.target_layer = gp.data.layers[0].name
            m.target_material = gp.material_slots[0].material if gp.material_slots else None
            m.thickness = thickness
    return gp


def setup_world(color=(0.55, 0.7, 0.9), strength=1.0):
    scn = bpy.context.scene
    w = scn.world or bpy.data.worlds.new("World")
    scn.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength
