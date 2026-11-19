"""Master NPR look: banded toon shading + rim light + inverted-hull ink outline (GPU-cheap),
optional Grease Pencil Line Art for static sets. Runs inside Blender (bpy)."""
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


def toon_material(name, color, bands=3, rim=0.30, rim_color=(1.0, 0.93, 0.8), texture=None,
                  shadow_tint=(0.78, 0.7, 0.93), cutout=False, emission=0.0, posterize=0, saturate=1.0, value=1.0):
    """Banded diffuse (Shader-to-RGB) -> lit/shadow colours, cool shadow tint, fresnel rim."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    t = mat.node_tree
    t.nodes.clear()
    out = _n(t, "ShaderNodeOutputMaterial", (1000, 0))
    diff = _n(t, "ShaderNodeBsdfDiffuse", (-700, 100))
    s2r = _n(t, "ShaderNodeShaderToRGB", (-500, 100))
    ramp = _n(t, "ShaderNodeValToRGB", (-300, 100))
    ramp.color_ramp.interpolation = "CONSTANT"
    el = ramp.color_ramp.elements
    while len(el) < bands:
        el.new(0.5)
    for i, e in enumerate(el):
        e.position = i / bands
        v = 0.28 + 0.72 * i / max(bands - 1, 1)     # shadow band keeps 28% of the base colour (no black holes)
        e.color = (v, v, v, 1)
    t.links.new(diff.outputs["BSDF"], s2r.inputs["Shader"])
    t.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])

    if texture:
        tex = _n(t, "ShaderNodeTexImage", (-500, 450))
        tex.image = bpy.data.images.load(str(texture), check_existing=True)
        base_out = tex.outputs["Color"]
        if posterize or saturate != 1.0 or value != 1.0:   # flatten photo textures into cel-painted colour patches
            if saturate != 1.0 or value != 1.0:
                hs = _n(t, "ShaderNodeHueSaturation", (-250, 450))
                hs.inputs["Saturation"].default_value = saturate
                hs.inputs["Value"].default_value = value
                t.links.new(base_out, hs.inputs["Color"])
                base_out = hs.outputs["Color"]
            if posterize:
                sep = _n(t, "ShaderNodeSeparateColor", (-120, 640))
                com = _n(t, "ShaderNodeCombineColor", (330, 640))
                t.links.new(base_out, sep.inputs["Color"])
                for i, ch in enumerate(("Red", "Green", "Blue")):
                    mu = _n(t, "ShaderNodeMath", (30, 760 - 90 * i), operation="MULTIPLY")
                    mu.inputs[1].default_value = posterize
                    fl = _n(t, "ShaderNodeMath", (140, 760 - 90 * i), operation="ROUND")
                    dv = _n(t, "ShaderNodeMath", (240, 760 - 90 * i), operation="DIVIDE")
                    dv.inputs[1].default_value = posterize
                    t.links.new(sep.outputs[ch], mu.inputs[0])
                    t.links.new(mu.outputs[0], fl.inputs[0])
                    t.links.new(fl.outputs[0], dv.inputs[0])
                    t.links.new(dv.outputs[0], com.inputs[ch])
                base_out = com.outputs["Color"]
    else:
        base = _n(t, "ShaderNodeRGB", (-500, 450))
        base.outputs[0].default_value = (*color[:3], 1)
        base_out = base.outputs[0]

    shade = _mix_rgba(t, (-100, 450), "MULTIPLY")
    shade.inputs["Factor"].default_value = 1.0
    shade.inputs[7].default_value = (*shadow_tint, 1)
    t.links.new(base_out, shade.inputs[6])

    # ramp drives shadow -> lit using only the lit/dark split (first band darkest)
    lit = _mix_rgba(t, (200, 250))
    t.links.new(ramp.outputs["Color"], lit.inputs["Factor"])
    t.links.new(shade.outputs[2], lit.inputs[6])
    t.links.new(base_out, lit.inputs[7])

    lw = _n(t, "ShaderNodeLayerWeight", (-500, -250))
    lw.inputs["Blend"].default_value = 0.5
    rimramp = _n(t, "ShaderNodeValToRGB", (-250, -250))
    rimramp.color_ramp.interpolation = "CONSTANT"
    rimramp.color_ramp.elements[0].position = 0.0
    rimramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    rimramp.color_ramp.elements[1].position = 0.7
    rimramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    t.links.new(lw.outputs["Fresnel"], rimramp.inputs["Fac"])
    rimmix = _mix_rgba(t, (550, 100), "ADD")
    rimmix.inputs[7].default_value = (*(c * rim for c in rim_color), 1)
    t.links.new(rimramp.outputs["Color"], rimmix.inputs["Factor"])
    t.links.new(lit.outputs[2], rimmix.inputs[6])

    emit = _n(t, "ShaderNodeEmission", (800, 100))
    t.links.new(rimmix.outputs[2], emit.inputs["Color"])
    if emission > 0:   # self-lit (windows, lamps, screens): lift colour toward white-hot
        boost = _n(t, "ShaderNodeEmission", (800, -100))
        boost.inputs["Strength"].default_value = emission
        t.links.new(base_out, boost.inputs["Color"])
        add = _n(t, "ShaderNodeAddShader", (1000, 0))
        t.links.new(emit.outputs["Emission"], add.inputs[0])
        t.links.new(boost.outputs["Emission"], add.inputs[1])
        t.links.new(add.outputs[0], out.inputs["Surface"])
    elif cutout and texture:   # alpha-cut foliage / decals
        tr = _n(t, "ShaderNodeBsdfTransparent", (800, -150))
        mix = _n(t, "ShaderNodeMixShader", (1000, 0))
        t.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
        t.links.new(tr.outputs[0], mix.inputs[1])
        t.links.new(emit.outputs["Emission"], mix.inputs[2])
        t.links.new(mix.outputs[0], out.inputs["Surface"])
        mat.surface_render_method = "DITHERED"
    else:
        t.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


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


def add_outline(obj, thickness=0.004, name="InkHull"):
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
