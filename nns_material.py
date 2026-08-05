import bpy
from bpy.props import (BoolProperty,
                       FloatProperty,
                       EnumProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       CollectionProperty)
from bpy.types import Image
from bpy.app.handlers import persistent
from .util import safe_register_class


def generate_output_node(material, input):
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    if material.nns_hdr_add_self:
        add_shader1 = nodes.new(type='ShaderNodeAddShader')
        add_shader2 = nodes.new(type='ShaderNodeAddShader')
        links.new(input.outputs[0], add_shader1.inputs[0])
        links.new(input.outputs[0], add_shader1.inputs[1])
        if bpy.app.version < (3, 0, 0):
            links.new(add_shader1.outputs[0], add_shader2.inputs[0])
            links.new(add_shader1.outputs[0], add_shader2.inputs[1])
            links.new(add_shader2.outputs[0], node_output.inputs[0])
        else:
            links.new(add_shader1.outputs[0], node_output.inputs[0])
    else:
        links.new(input.outputs[0], node_output.inputs[0])


def generate_culling_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_geo = nodes.new(type='ShaderNodeNewGeometry')
    node_invert = nodes.new(type='ShaderNodeInvert')

    if material.nns_display_face == "front":
        node_invert.inputs[0].default_value = 1.0
    elif material.nns_display_face == "back":
        node_invert.inputs[0].default_value = 0.0

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.inputs[0].default_value = 1.0
    links.new(node_geo.outputs[6], node_invert.inputs[1])
    links.new(node_invert.outputs[0], node_mix_rgb.inputs[1])

    return node_mix_rgb


def generate_srt_nodes(material, input):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_sub = nodes.new(type='ShaderNodeVectorMath')
    node_sub.operation = 'SUBTRACT'
    node_sub.location = (-100, 0)

    if material.nns_tex_gen_mode == "nrm":
        node_sub.inputs[1].default_value = (0, 0, 0)
    else:
        node_sub.inputs[1].default_value = (0.5, 0.5, 0.5)

    node_rt_mapping = nodes.new(type='ShaderNodeMapping')
    node_rt_mapping.name = 'nns_node_rt'
    node_rt_mapping.location = (0, 0)
    node_rt_mapping.inputs[3].default_value = (1, 1, 1)

    node_add = nodes.new(type='ShaderNodeVectorMath')
    node_add.operation = 'ADD'
    node_add.location = (100, 0)
    node_add.inputs[1].default_value = (0.5, 0.5, 0.5)

    node_s_mapping = nodes.new(type='ShaderNodeMapping')
    node_s_mapping.name = 'nns_node_s'
    node_s_mapping.location = (200, 0)
    node_s_mapping.inputs[3].default_value = (1, 1, 1)

    links.new(input.outputs[0], node_sub.inputs[0])
    links.new(node_sub.outputs[0], node_rt_mapping.inputs[0])
    links.new(node_rt_mapping.outputs[0], node_add.inputs[0])
    links.new(node_add.outputs[0], node_s_mapping.inputs[0])

    return node_s_mapping


node_offset_x = 0
node_offset_y = 0
loca = (0, 0)


def create_node(mat, name, node_type, location, offset_mode="x"):
    global node_offset_x
    global node_offset_y
    nodes = mat.node_tree.nodes
    newnode = nodes.new(type=node_type)
    newnode.name = name
    newnode.label = name
    if offset_mode == 0:
        newnode.location = location
    elif offset_mode == "x":
        newnode.location = (location[0] + node_offset_x, location[1] + node_offset_y)
        node_offset_x += 180
    elif offset_mode == "y":
        newnode.location = (location[0], location[1] + node_offset_y)
        node_offset_y -= 150
    elif offset_mode == "xy":
        newnode.location = (location[0] + node_offset_x, location[1] + node_offset_y)
        node_offset_x += 180
        newnode.location = (location[0], location[1] + node_offset_y)
        node_offset_y -= 150
    return newnode


def create_light_nodes(mat, index, location):
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # get inputs

    # lights

    light_vec = nodes.get("Light" + str(index) + " Vector")
    light_spec = nodes.get("Light" + str(index) + " Specular")
    light_col = nodes.get("Light" + str(index) + " Color Filtered")

    # materials

    node_diffuse = nodes.get("df")
    node_ambient = nodes.get("amb")
    node_specular = nodes.get("spec")

    # transform inputs
    # normals to camera space

    normal_vec_node = create_node(mat, "normal vector(N)", 'ShaderNodeNewGeometry', location)

    vec_mult1 = create_node(mat, "Fix backface", "ShaderNodeVectorMath", location)
    vec_mult1.operation = "MULTIPLY"

    mult_add1 = create_node(mat, "remap backface factor", "ShaderNodeMath", location)
    mult_add1.operation = "MULTIPLY_ADD"
    mult_add1.inputs[1].default_value = -2.0
    mult_add1.inputs[2].default_value = 1.0

    vec_trans = create_node(mat, "transform to camera space", 'ShaderNodeVectorTransform', location)
    vec_trans.convert_from = "WORLD"
    vec_trans.convert_to = "CAMERA"

    links.new(normal_vec_node.outputs[6], mult_add1.inputs[0])
    links.new(normal_vec_node.outputs[1], vec_mult1.inputs[0])
    links.new(mult_add1.outputs[0], vec_mult1.inputs[1])
    links.new(vec_mult1.outputs[0], vec_trans.inputs[0])

    # LightVector in camera space
    vec_mult2 = create_node(mat, "inverse light angle", "ShaderNodeVectorMath", location)
    vec_mult2.inputs[1].default_value = (-1, -1, -1)
    vec_mult2.operation = "MULTIPLY"

    vec_norm1 = create_node(mat, "Normalize", "ShaderNodeVectorMath", location)
    vec_norm1.operation = "NORMALIZE"

    links.new(light_vec.outputs[0], vec_mult2.inputs[0])
    links.new(vec_mult2.outputs[0], vec_norm1.inputs[0])

    sep_xyz1 = create_node(mat, "SepXYZ", "ShaderNodeSeparateXYZ", location)
    comb_xyz1 = create_node(mat, "CombXYZ", "ShaderNodeCombineXYZ", location)

    links.new(vec_norm1.outputs[0], sep_xyz1.inputs[0])
    links.new(sep_xyz1.outputs[0], comb_xyz1.inputs[0])
    links.new(sep_xyz1.outputs[1], comb_xyz1.inputs[2])
    links.new(sep_xyz1.outputs[2], comb_xyz1.inputs[1])

    # ld : Diffuse reflection shininess
    # ls : Specular reflection shininess

    # calculation of ld

    dot_prod1 = create_node(mat, "Dot Prod1", "ShaderNodeVectorMath", location)
    dot_prod1.operation = "DOT_PRODUCT"

    links.new(vec_trans.outputs[0], dot_prod1.inputs[0])
    links.new(comb_xyz1.outputs[0], dot_prod1.inputs[1])

    clamp1 = create_node(mat, "Clamp1", "ShaderNodeClamp", location)
    clamp1.inputs[1].default_value = 0.0
    clamp1.inputs[2].default_value = 1.0

    ld = create_node(mat, "ld", "ShaderNodeMath", location)
    ld.operation = "POWER"
    ld.inputs[1].default_value = 1.50

    links.new(dot_prod1.outputs[1], clamp1.inputs[0])
    links.new(clamp1.outputs[0], ld.inputs[0])

    # half angle vector

    vec_add1 = create_node(mat, "VecAdd1", "ShaderNodeVectorMath", location)
    vec_add1.operation = "ADD"
    vec_add1.inputs[1].default_value = (0, 0.99, 0)

    vec_norm2 = create_node(mat, "VecNorm2", "ShaderNodeVectorMath", location)
    vec_norm2.operation = "NORMALIZE"

    links.new(comb_xyz1.outputs[0], vec_add1.inputs[0])
    links.new(vec_add1.outputs[0], vec_norm2.inputs[0])

    # calculation of ls (may not be 100% accurate due to me not knowing how to search for tables in the ida db
    # but it's accurate enough for preview purpose)
    # may be updated if i find a better approwimation or get the exact formula

    dot_prod2 = create_node(mat, "DotProd2", "ShaderNodeVectorMath", location)
    dot_prod2.operation = "DOT_PRODUCT"

    # specular corrective mask

    sign1 = create_node(mat, "Sign1", "ShaderNodeMath", location)
    sign1.operation = "SIGN"
    sign1.use_clamp = True

    # end of mask

    pow1 = create_node(mat, "Pow1", "ShaderNodeMath", location)
    pow1.operation = "POWER"
    pow1.inputs[1].default_value = 2.0

    links.new(vec_norm2.outputs[0], dot_prod2.inputs[0])
    links.new(vec_trans.outputs[0], dot_prod2.inputs[1])
    links.new(dot_prod2.outputs[1], pow1.inputs[0])
    links.new(dot_prod2.outputs[1], sign1.inputs[0])

    mult1 = create_node(mat, "Mult1", "ShaderNodeMath", location)
    mult1.operation = "MULTIPLY"
    mult1.inputs[1].default_value = 2.0

    sub1 = create_node(mat, "Sub1", "ShaderNodeMath", location)
    sub1.operation = "SUBTRACT"
    sub1.inputs[1].default_value = 1.0
    sub1.use_clamp = True

    links.new(pow1.outputs[0], mult1.inputs[0])
    links.new(mult1.outputs[0], sub1.inputs[0])

    # applying the spec corrective mask

    mult3 = create_node(mat, "Mult3", "ShaderNodeMath", location)
    mult3.operation = "MULTIPLY"
    links.new(sign1.outputs[0], mult3.inputs[0])
    links.new(sub1.outputs[0], mult3.inputs[1])

    ls = create_node(mat, "Specular brightness", "ShaderNodeMath", location)
    ls.operation = "POWER"
    ls.inputs[1].default_value = 2.0
    links.new(mult3.outputs[0], ls.inputs[0])

    # Diffuse color

    di = create_node(mat, "Diffuse " + str(index), "ShaderNodeMixRGB", location)
    di.blend_type = "MULTIPLY"
    di.inputs[0].default_value = 1.0

    links.new(node_diffuse.outputs[0], di.inputs[1])
    links.new(ld.outputs[0], di.inputs[2])

    # Specular color

    pow2 = create_node(mat, "Pow2", "ShaderNodeMath", location)
    pow2.operation = "POWER"
    pow2.inputs[1].default_value = 1.5

    mult4 = create_node(mat, "Mult4", "ShaderNodeMath", location)
    mult4.operation = "MULTIPLY"

    si = create_node(mat, "Specular " + str(index), "ShaderNodeMixRGB", location)
    si.blend_type = "MULTIPLY"
    si.inputs[0].default_value = 1.0

    links.new(node_specular.outputs[0], si.inputs[1])
    links.new(light_spec.outputs[0], pow2.inputs[0])
    links.new(ls.outputs[0], mult4.inputs[0])
    links.new(pow2.outputs[0], mult4.inputs[1])
    links.new(mult4.outputs[0], si.inputs[2])

    # addition of the three colors (all except emission)

    col_add1 = create_node(mat, "Ambient " + str(index), "ShaderNodeMixRGB", location)
    col_add1.blend_type = "ADD"
    col_add1.inputs[0].default_value = 1.0

    col_add2 = create_node(mat, "ColAdd2", "ShaderNodeMixRGB", location)
    col_add2.blend_type = "ADD"
    col_add2.inputs[0].default_value = 1.0

    links.new(node_ambient.outputs[0], col_add1.inputs[2])
    links.new(di.outputs[0], col_add1.inputs[1])
    links.new(col_add1.outputs[0], col_add2.inputs[1])
    links.new(si.outputs[0], col_add2.inputs[2])

    # multiply with light color

    col_mult1 = create_node(mat, "Result " + str(index), "ShaderNodeMixRGB", location)
    col_mult1.blend_type = "MULTIPLY"
    col_mult1.inputs[0].default_value = 1.0

    links.new(light_col.outputs[0], col_mult1.inputs[2])
    links.new(col_add2.outputs[0], col_mult1.inputs[1])
    light_node = col_mult1

    return light_node


def generate_normal_lightning_color_nodes(material, diffuse_from_vertex_color=False):
    global node_offset_y
    global node_offset_x
    global loca

    node_offset_x = 0
    node_offset_y = 0

    mat = material
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    matcols = {"amb": (material.nns_ambient[0],
                       material.nns_ambient[1],
                       material.nns_ambient[2],
                       1.0),
               "spec": (material.nns_specular[0],
                        material.nns_specular[1],
                        material.nns_specular[2],
                        1.0),
               "em": (material.nns_emission[0],
                      material.nns_emission[1],
                      material.nns_emission[2],
                      1.0)}
    if not diffuse_from_vertex_color:
        matcols["df"] = (material.nns_diffuse[0],
                          material.nns_diffuse[1],
                          material.nns_diffuse[2],
                          1.0)

    light0 = {"LightVector": (0, 0, -1), "LightCol": (1, 1, 1, 1), "LightSpecular": 0.5,
              "isLightEnabled": mat.nns_light0, "LightIndex": 0}
    light1 = {"LightVector": (0, 0.5, -0.5), "LightCol": (1, 1, 1, 1), "LightSpecular": 1,
              "isLightEnabled": mat.nns_light1, "LightIndex": 1}
    light2 = {"LightVector": (0, 0, -1), "LightCol": (1, 0, 0, 1), "LightSpecular": 0.5,
              "isLightEnabled": mat.nns_light2, "LightIndex": 2}
    light3 = {"LightVector": (0, 0, 1), "LightCol": (1, 1, 0, 1), "LightSpecular": 0, "isLightEnabled": mat.nns_light3,
              "LightIndex": 3}

    lights = (light0, light1, light2, light3)

    # inputs
    node_offset_x = 0
    node_offset_y = -300
    loca = (-7500, -300)

    for i in range(4):
        light_vec = create_node(mat, "Light" + str(i) + " Vector", "ShaderNodeCombineXYZ", loca, offset_mode="y")
        for j in range(3):
            light_vec.inputs[j].default_value = lights[i]["LightVector"][j]

        light_col = create_node(mat, "Light" + str(i) + " Color", "ShaderNodeRGB", loca, offset_mode="y")
        light_col.outputs[0].default_value = lights[i]["LightCol"]

        light_spec = create_node(mat, "Light" + str(i) + " Specular", "ShaderNodeValue", loca, offset_mode="y")
        light_spec.outputs[0].default_value = lights[i]["LightSpecular"]

        light_enabled = create_node(mat, "Light" + str(i) + " Enabled", "ShaderNodeValue", loca, offset_mode="y")
        light_enabled.outputs[0].default_value = lights[i]["isLightEnabled"]

        mask_node = create_node(mat, "Light" + str(i) + " Color Filtered", "ShaderNodeMixRGB", (-7300, loca[1]),
                                offset_mode="y")

        mask_node.blend_type = "MULTIPLY"
        mask_node.inputs[0].default_value = 1.0

        links.new(light_col.outputs[0], mask_node.inputs[1])
        links.new(light_enabled.outputs[0], mask_node.inputs[2])

    # material colors

    for name in matcols.keys():
        col = create_node(mat, name, "ShaderNodeRGB", loca, offset_mode="y")
        col.outputs[0].default_value = matcols[name]

    # The "df" node feeds into the lighting math below purely by name (create_light_nodes looks it up via nodes.get("df")), so swapping what kind of node it is, a flat material color vs. a per-vertex color attribute, is enough to make the same lighting equation work with either diffuse source, no other changes needed.
    if diffuse_from_vertex_color:
        node_df = create_node(mat, "df", "ShaderNodeAttribute", loca, offset_mode="y")
        node_df.attribute_name = "Col"
    else:
        node_df = nodes.get("df")

    # add all the results of the light0, 1, 2 and 3 calculations

    add_nodes_x = -600
    node_offset_y = -300

    l_col_add1 = create_node(mat, "LColAdd1", "ShaderNodeMixRGB", (add_nodes_x, -300), offset_mode="xy")
    l_col_add1.blend_type = "ADD"
    l_col_add1.inputs[0].default_value = 1.0

    l_col_add2 = create_node(mat, "LColAdd2", "ShaderNodeMixRGB", (add_nodes_x, -450), offset_mode="xy")
    l_col_add2.blend_type = "ADD"
    l_col_add2.inputs[0].default_value = 1.0

    l_col_add3 = create_node(mat, "LColAdd3", "ShaderNodeMixRGB", (add_nodes_x, -600), offset_mode="xy")
    l_col_add3.blend_type = "ADD"
    l_col_add3.inputs[0].default_value = 1.0

    l_col_add4 = create_node(mat, "Total result", "ShaderNodeMixRGB", (add_nodes_x, -750), offset_mode="xy")
    l_col_add4.blend_type = "ADD"
    l_col_add4.inputs[0].default_value = 1.0
    node_emission = nodes.get("em")

    use_diffuse_node = create_node(mat, "UseOnlyDiffuse?", "ShaderNodeMixRGB", (add_nodes_x, -750), offset_mode="xy")
    use_diffuse_node.blend_type = "MIX"

    links.new(l_col_add1.outputs[0], l_col_add2.inputs[1])
    links.new(l_col_add2.outputs[0], l_col_add3.inputs[1])
    links.new(l_col_add3.outputs[0], l_col_add4.inputs[1])
    links.new(node_emission.outputs[0], l_col_add4.inputs[2])

    node_offset_x = 0
    node_offset_y = -300

    for i in range(4):
        light_node = create_light_nodes(mat, i, (-6500 - i * 150, -300))
        if i == 0 or i == 1:
            links.new(light_node.outputs[0], l_col_add1.inputs[i + 1])
        elif i == 2:
            links.new(light_node.outputs[0], l_col_add2.inputs[2])
        else:
            links.new(light_node.outputs[0], l_col_add3.inputs[2])
        node_offset_y -= 350
        node_offset_x = 0

    links.new(l_col_add3.outputs[0], l_col_add4.inputs[1])
    links.new(l_col_add4.outputs[0], use_diffuse_node.inputs[1])
    light_total_result = use_diffuse_node

    # if no light is enbaled
    use_only_diffuse = True
    for light in lights:
        if light["isLightEnabled"]:
            use_only_diffuse = False

    light_total_result.inputs[0].default_value = use_only_diffuse
    if diffuse_from_vertex_color:
        links.new(node_df.outputs[0], light_total_result.inputs[2])
    else:
        light_total_result.inputs[2].default_value = matcols["df"]

    return light_total_result


def generate_decal_vc_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_1 = nodes.new(type='ShaderNodeMixRGB')
    node_mix_1.inputs[0].default_value = 0.0

    node_mix_2 = nodes.new(type='ShaderNodeMixRGB')

    links.new(node_mix_1.outputs[0], node_mix_2.inputs[2])

    if "tx" in material.nns_mat_type:
        node_image = generate_image_nodes(material)
        links.new(node_image.outputs[0], node_mix_1.inputs[1])
        links.new(node_image.outputs[1], node_mix_1.inputs[2])
        links.new(node_image.outputs[1], node_mix_2.inputs[0])

    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_trans_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')

    links.new(node_mix_2.outputs[0], node_mix_shader.inputs[2])
    links.new(node_trans_bsdf.outputs[0], node_mix_shader.inputs[1])

    if "nr" in material.nns_mat_type:
        node_vertex_lighting = generate_normal_lightning_color_nodes(
            material, diffuse_from_vertex_color=("vc" in material.nns_mat_type))
        links.new(node_vertex_lighting.outputs[0], node_mix_2.inputs[1])

    elif "vc" in material.nns_mat_type:
        node_attr = nodes.new(type='ShaderNodeAttribute')
        node_attr.attribute_name = 'Col'
        links.new(node_attr.outputs[0], node_mix_2.inputs[1])

    else:
        node_diffuse = nodes.new(type='ShaderNodeMixRGB')
        node_diffuse.name = 'nns_node_diffuse'
        node_diffuse.blend_type = 'MULTIPLY'
        node_diffuse.inputs[0].default_value = 1.0
        node_diffuse.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
        node_diffuse.inputs[2].default_value = (
            material.nns_diffuse[0],
            material.nns_diffuse[1],
            material.nns_diffuse[2],
            1.0)
        links.new(node_diffuse.outputs[0], node_mix_2.inputs[1])

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.location = (0, 200)
    node_mix_rgb.blend_type = 'MIX'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (0, 0, 0, 1)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0)

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    generate_output_node(material, node_mix_shader)


def generate_image_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links


    node_image = nodes.new(type='ShaderNodeTexImage')
    node_image.name = 'nns_node_image'
    node_image.interpolation = 'Closest'
    image = get_material_texture_image(material)
    if image is not None:
        try:
            node_image.image = image
        except Exception:
            raise NameError("Cannot load image")

    # Make this ahead of time. Must always be filled.
    node_srt = None

    if material.nns_tex_gen_mode == "nrm":
        node_geo = nodes.new(type='ShaderNodeNewGeometry')
        node_vec_trans = nodes.new(type='ShaderNodeVectorTransform')
        node_vec_trans.convert_from = 'WORLD'
        node_vec_trans.convert_to = 'CAMERA'
        node_vec_trans.vector_type = 'NORMAL'
        node_mapping = nodes.new(type='ShaderNodeMapping')
        node_mapping.inputs[3].default_value = (0.5, 0.5, 0.5)
        links.new(node_geo.outputs[1], node_vec_trans.inputs[0])
        links.new(node_vec_trans.outputs[0], node_mapping.inputs[0])
        node_srt = generate_srt_nodes(material, node_mapping)
    else:
        node_uvmap = nodes.new(type='ShaderNodeUVMap')
        node_uvmap.uv_map = "UVMap"
        node_srt = generate_srt_nodes(material, node_uvmap)

    node_sp_xyz = nodes.new(type='ShaderNodeSeparateXYZ')
    links.new(node_srt.outputs[0], node_sp_xyz.inputs[0])

    node_cb_xyz = nodes.new(type='ShaderNodeCombineXYZ')
    links.new(node_sp_xyz.outputs[2], node_cb_xyz.inputs[2])

    if material.nns_tex_tiling_u == "flip":
        node_math_u = nodes.new(type='ShaderNodeMath')
        node_math_u.operation = 'PINGPONG'
        node_math_u.inputs[1].default_value = 1.0
        links.new(node_sp_xyz.outputs[0], node_math_u.inputs[0])
        links.new(node_math_u.outputs[0], node_cb_xyz.inputs[0])
    elif material.nns_tex_tiling_u == "clamp":
        node_math_u = nodes.new(type='ShaderNodeMath')
        node_math_u.operation = 'MINIMUM'
        node_math_u.inputs[1].default_value = 0.99
        node_math_u.use_clamp = True
        links.new(node_sp_xyz.outputs[0], node_math_u.inputs[0])
        links.new(node_math_u.outputs[0], node_cb_xyz.inputs[0])
    else:
        links.new(node_sp_xyz.outputs[0], node_cb_xyz.inputs[0])

    if material.nns_tex_tiling_v == "flip":
        node_math_v = nodes.new(type='ShaderNodeMath')
        node_math_v.operation = 'PINGPONG'
        node_math_v.inputs[1].default_value = 1.0
        links.new(node_sp_xyz.outputs[1], node_math_v.inputs[0])
        links.new(node_math_v.outputs[0], node_cb_xyz.inputs[1])
    elif material.nns_tex_tiling_v == "clamp":
        node_math_v = nodes.new(type='ShaderNodeMath')
        node_math_v.operation = 'MINIMUM'
        node_math_v.inputs[1].default_value = 0.99
        node_math_v.use_clamp = True
        links.new(node_sp_xyz.outputs[1], node_math_v.inputs[0])
        links.new(node_math_v.outputs[0], node_cb_xyz.inputs[1])
    else:
        links.new(node_sp_xyz.outputs[1], node_cb_xyz.inputs[1])

    links.new(node_cb_xyz.outputs[0], node_image.inputs[0])

    return node_image


def generate_mod_vc_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix = nodes.new(type='ShaderNodeMixRGB')
    node_mix.inputs[0].default_value = 0.0

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )

    if "tx" in material.nns_mat_type:
        node_image = generate_image_nodes(material)
        links.new(node_image.outputs[0], node_mix.inputs[1])
        links.new(node_image.outputs[1], node_mix.inputs[2])
        links.new(node_image.outputs[1], node_mix_rgb.inputs[1])

    node_multiply = nodes.new(type='ShaderNodeMixRGB')
    node_multiply.name = 'nns_node_diffuse'
    node_multiply.blend_type = 'MULTIPLY'
    node_multiply.inputs[0].default_value = 1.0
    node_multiply.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_multiply.inputs[2].default_value = (
        material.nns_diffuse[0],
        material.nns_diffuse[1],
        material.nns_diffuse[2],
        1.0
    )

    if "nr" in material.nns_mat_type:
        node_vertex_lighting = generate_normal_lightning_color_nodes(
            material, diffuse_from_vertex_color=("vc" in material.nns_mat_type))
        links.new(node_vertex_lighting.outputs[0], node_multiply.inputs[2])

    elif "vc" in material.nns_mat_type:
        node_attr = nodes.new(type='ShaderNodeAttribute')
        node_attr.attribute_name = 'Col'
        links.new(node_attr.outputs[0], node_multiply.inputs[2])

    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    links.new(node_mix.outputs[0], node_multiply.inputs[1])
    links.new(node_multiply.outputs[0], node_mix_shader.inputs[2])

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    generate_output_node(material, node_mix_shader)


def generate_image_only_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_image = generate_image_nodes(material)

    links.new(node_image.outputs[0], node_mix_shader.inputs[2])
    links.new(node_image.outputs[1], node_mix_rgb.inputs[1])

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    generate_output_node(material, node_mix_shader)


def generate_solid_color_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.location = (0, 200)
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_df = nodes.new(type='ShaderNodeMixRGB')
    node_mix_df.location = (0, -100)
    node_mix_df.name = 'nns_node_diffuse'
    node_mix_df.inputs[0].default_value = 1.0
    node_mix_df.inputs[2].default_value = (
        material.nns_diffuse[0],
        material.nns_diffuse[1],
        material.nns_diffuse[2],
        1.0
    )
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_mix_shader.location = (200, 0)

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_mix_df.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)


def generate_only_normal_lighting(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_vc_light = generate_normal_lightning_color_nodes(material)
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_vc_light.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)


def generate_only_vc_normal_lighting_nodes(material):
    """vc_nr: vertex colors combined with real-time lighting, no
    texture. Same structure as generate_only_normal_lighting() (solid
    color + lighting), just sourcing the diffuse term from the mesh's
    vertex colors instead of the material's fixed diffuse color.
    """
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_vc_light = generate_normal_lightning_color_nodes(
        material, diffuse_from_vertex_color=True)
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_vc_light.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)


def generate_only_vc_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_vc = nodes.new(type='ShaderNodeVertexColor')
    node_vc.layer_name = 'Col'
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_vc.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)

# fog

node_fog_offset_x = 0
node_fog_offset_y = 0
loca_fog = (0, 0)


def create_node_fog(name, node_type, location=loca_fog, offset_mode="x"):
    global node_fog_offset_x
    global node_fog_offset_y
    nodes = bpy.data.node_groups.get("nns fog").nodes
    newnode = nodes.new(type=node_type)
    newnode.name = name
    newnode.label = name
    if offset_mode == 0:
        newnode.location = location
    elif offset_mode == "x":
        newnode.location = (location[0] + node_fog_offset_x, location[1] + node_fog_offset_y)
        node_fog_offset_x += 180
    elif offset_mode == "y":
        newnode.location = (location[0], location[1] + node_fog_offset_y)
        node_fog_offset_y -= 150
    elif offset_mode == "xy":
        newnode.location = (location[0] + node_fog_offset_x, location[1] + node_fog_offset_y)
        node_fog_offset_x += 180
        newnode.location = (location[0], location[1] + node_fog_offset_y)
        node_fog_offset_y -= 150
    return newnode


def generate_fog_group():
    if "nns fog" not in bpy.data.node_groups.keys():
        fog_group = bpy.data.node_groups.new(name="nns fog", type="ShaderNodeTree")
    else:
        fog_group = bpy.data.node_groups.get("nns fog")

    nodes = fog_group.nodes
    nodes.clear()

    input_node = create_node_fog("input node", "NodeGroupInput", (-150, 0))
    output_node = create_node_fog("output_node", "NodeGroupOutput", (1000, 0), 0)

    # reset group

    if "surface color" not in fog_group.inputs or "mat use fog" not in fog_group.inputs:
        for input in fog_group.inputs:
            fog_group.inputs.remove(input)
        fog_group.inputs.new("NodeSocketColor", "surface color")
        fog_group.inputs.new("NodeSocketFloat", "mat use fog")

    if "Color" not in fog_group.outputs:
        for output in fog_group.outputs:
            fog_group.outputs.remove(output)
        fog_group.outputs.new("NodeSocketColor", "Color")

    for node in nodes:
        nodes.remove(node)

    generate_fog_group_nodes(fog_group, input_node, output_node)


def generate_fog_group_nodes(fog_group, input_node, output_node):
    global node_fog_offset_x
    global node_fog_offset_y

    node_fog_offset_x = 0
    node_fog_offset_y = 0
    # input data
    input_node = create_node_fog("inputs", "NodeGroupInput", (0, 150), 0)

    # invariable
    cam = create_node_fog("cam", "ShaderNodeCameraData", loca_fog, "y")

    # variable
    use_fog = create_node_fog("use_fog", "ShaderNodeValue", loca_fog, "y")
    scale = create_node_fog("scale", "ShaderNodeValue", loca_fog, "y")
    scale.outputs[0].default_value = 20
    fog_offset = create_node_fog("fog offset", "ShaderNodeValue", loca_fog, "y")
    fog_color = create_node_fog("fog color", "ShaderNodeRGB", loca_fog, "y")

    node_fog_offset_y = 0
    node_fog_offset_x = 150

    divide = create_node_fog("divide", "ShaderNodeMath")
    divide.operation = "DIVIDE"

    subtract = create_node_fog("subtract", "ShaderNodeMath")
    subtract.operation = "SUBTRACT"
    subtract.use_clamp = True

    sub_c1 = create_node_fog("subtract", "ShaderNodeMath")
    sub_c1.operation = "SUBTRACT"
    sub_c1.inputs[0].default_value = 1

    pow1 = create_node_fog("pow", "ShaderNodeMath")
    pow1.operation = "POWER"
    pow1.inputs[1].default_value = 7

    sub_c2 = create_node_fog("subtract", "ShaderNodeMath")
    sub_c2.operation = "SUBTRACT"
    sub_c2.inputs[0].default_value = 1

    pow2 = create_node_fog("pow", "ShaderNodeMath")
    pow2.operation = "POWER"
    pow2.inputs[1].default_value = 0.5

    mix_c = create_node_fog("mix 1", "ShaderNodeMixRGB")
    mix_c.blend_type = "MIX"

    curve = create_node_fog("curve", "ShaderNodeRGBCurve")
    curve.mapping.extend = 'HORIZONTAL'
    curve.width = 350
    node_fog_offset_x += 300

    mix_1 = create_node_fog("mix 1", "ShaderNodeMixRGB")
    mix_1.blend_type = "MIX"

    mult = create_node_fog("mult", "ShaderNodeMath")
    mult.operation = "MULTIPLY"

    mix_2 = create_node_fog("mix 2", "ShaderNodeMixRGB")
    mix_2.blend_type = "MIX"

    links = fog_group.links

    links.new(cam.outputs[1], divide.inputs[0])
    links.new(scale.outputs[0], divide.inputs[1])

    links.new(divide.outputs[0], subtract.inputs[0])
    links.new(fog_offset.outputs[0], subtract.inputs[1])

    # blending correction

    links.new(subtract.outputs[0], sub_c1.inputs[1])
    links.new(sub_c1.outputs[0], pow1.inputs[0])
    links.new(pow1.outputs[0], sub_c2.inputs[1])

    links.new(fog_color.outputs[0], pow2.inputs[0])
    links.new(pow2.outputs[0],mix_c.inputs[0])
    links.new(sub_c2.outputs[0], mix_c.inputs[1])
    links.new(subtract.outputs[0], mix_c.inputs[2])

    # fog density curve

    links.new(mix_c.outputs[0], curve.inputs[1])
    links.new(curve.outputs[0], mix_1.inputs[0])
    links.new(input_node.outputs["surface color"], mix_1.inputs[1])
    links.new(fog_color.outputs[0], mix_1.inputs[2])

    links.new(input_node.outputs["mat use fog"], mult.inputs[0])
    links.new(use_fog.outputs[0], mult.inputs[1])

    links.new(mult.outputs[0], mix_2.inputs[0])
    links.new(mix_1.outputs[0], mix_2.inputs[2])
    links.new(input_node.outputs["surface color"], mix_2.inputs[1])

    # output data

    output_node = create_node_fog("outputs", "NodeGroupOutput")
    links.new(mix_2.outputs[0], output_node.inputs["Color"])


def generate_fog_material_nodes(material):
    mat = material
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    mix_shader = nodes.get("Mix Shader")
    nns_df = mix_shader.inputs[2].links[0].from_node

    nns_fog = create_node(mat, "nns fog", "ShaderNodeGroup", loca)
    update_fog_group_nodes(self=None, context=bpy.context)
    nns_fog.node_tree = bpy.data.node_groups.get("nns fog")
    nns_fog.inputs[1].default_value = int(mat.nns_fog)

    nns_fog.location = (mix_shader.location[0], mix_shader.location[1] - 150)
    links.new(nns_df.outputs[0], nns_fog.inputs[0])
    links.new(nns_fog.outputs[0], mix_shader.inputs[2])


def get_material_texture_image(material):
    """Returns the Image this NNS material should use, or None.

    A material's texture comes entirely from the texture pattern list
    (nns_texframe_reference) now: no entries means no texture (the DS
    uses the solid/vertex color instead), the first entry is always the
    base texture shown even with no animation, and more entries enable
    .itp texture-pattern animation.

    nns_image is only still read here as a fallback, for materials
    saved with an older version of this plugin before the two texture
    systems were unified. migrate_legacy_textures() moves it into the
    pattern list on file load, so this fallback should rarely actually
    trigger, but it's kept as a safety net in case a material is
    accessed before that migration runs.
    """
    if material.nns_texframe_reference:
        return material.nns_texframe_reference[0].image
    if material.nns_image:
        return material.nns_image
    return None


def compute_mat_type(material):
    """Derives the internal nns_mat_type value from the three
    independent choices the material panel actually exposes: color type
    (solid/vertex), whether any light is on, and whether a texture is
    assigned. nns_mat_type used to be one big dropdown users picked
    directly, covering only the combinations someone had built a node
    graph for; it's computed now so every combination the hardware
    actually supports is reachable, and the rest of the exporter (which
    only ever checks "tx"/"vc"/"nr" as substrings of this value, never
    the whole string) doesn't need to change to understand the new
    combinations.

    This has to match the exact strings already registered in
    mat_type_items below, not just contain the right substrings.
    Blender's EnumProperty rejects a value that isn't one of the
    registered items. The original naming wasn't fully consistent
    (textured+normal+solid is "tx_nr_df", with "nr" moved in front of the
    base name, while every other normals combination keeps "_nr" at the
    end), so this is an explicit table rather than generic string
    building, to avoid constructing an unregistered value.
    """
    has_texture = get_material_texture_image(material) is not None
    any_light = (material.nns_light0 or material.nns_light1
                 or material.nns_light2 or material.nns_light3)
    is_vertex = material.nns_color_type == 'vertex'

    # (has_texture, is_vertex, any_light) -> registered mat_type string
    table = {
        (False, False, False): 'df',
        (False, False, True): 'df_nr',
        (False, True, False): 'vc',
        (False, True, True): 'vc_nr',
        (True, False, False): 'tx_df',
        (True, False, True): 'tx_nr_df',
        (True, True, False): 'tx_vc',
        (True, True, True): 'tx_vc_nr',
    }
    return table[(has_texture, is_vertex, any_light)]


def refresh_mat_type(material):
    """Recomputes nns_mat_type from the material's current settings and
    rebuilds the preview node graph if it actually changed (e.g. going
    from no lights to lights crosses into a completely different node graph,
    not just a value tweak on the existing one).
    """
    if material is None or not material.is_nns:
        return
    new_type = compute_mat_type(material)
    if new_type != material.nns_mat_type:
        material.nns_mat_type = new_type
        generate_nodes(material)


def update_computed_mat_type(self, context):
    refresh_mat_type(context.material)


def update_light_toggle(self, context):
    """Shared update= callback for all four light booleans. Toggling a
    light can change what nns_mat_type should be, which needs a full node graph rebuild
    but if it doesn't change (e.g. a second light toggling while at least one
    other was already on), the lighting node graph already exists and
    only the per-light enabled values need refreshing, same as before.
    """
    material = context.material
    if material is None or not material.is_nns:
        return

    old_type = material.nns_mat_type
    new_type = compute_mat_type(material)

    if new_type != old_type:
        material.nns_mat_type = new_type
        generate_nodes(material)
    else:
        update_nodes_use_only_diffuse(material)
        if "nr" in material.nns_mat_type:
            for i in range(4):
                node = material.node_tree.nodes.get(f"Light{i} Enabled")
                if node is not None:
                    node.outputs[0].default_value = getattr(
                        material, f"nns_light{i}")


def generate_nodes(material):
    if material.is_nns:
        nodes = material.node_tree.nodes
        nodes.clear()
        links = material.node_tree.links
        links.clear()

        if material.nns_mat_type == "tx":
            print("oui")
            generate_image_only_nodes(material)
        elif material.nns_mat_type == "df":
            generate_solid_color_nodes(material)
        elif material.nns_mat_type == "vc":
            generate_only_vc_nodes(material)
        elif material.nns_mat_type == "df_nr":
            generate_only_normal_lighting(material)
        elif material.nns_mat_type == "vc_nr":
            generate_only_vc_normal_lighting_nodes(material)
        elif material.nns_polygon_mode == "modulate" \
                or material.nns_polygon_mode == "toon_highlight" \
                or material.nns_polygon_mode == "shadow":
            generate_mod_vc_nodes(material)
        elif material.nns_polygon_mode == "decal":
            generate_decal_vc_nodes(material)

        generate_fog_material_nodes(material)

def update_fog_group_nodes(self, context):
    if "nns fog" not in bpy.data.node_groups.keys():
        generate_fog_group()

    fog_group = bpy.data.node_groups.get("nns fog")
    if "fog offset" not in fog_group.nodes.keys():
        generate_fog_group()

    nodes = fog_group.nodes

    use_fog = nodes.get("use_fog")
    use_fog.outputs[0].default_value = context.scene.Fog_enable  # scene property

    scale = nodes.get("scale")
    scale.outputs[0].default_value = context.scene.Fog_scale

    fog_offset = nodes.get("fog offset")
    fog_offset.outputs[0].default_value = context.scene.Fog_offset

    fog_color = nodes.get("fog color")
    color = context.scene.Fog_color
    fog_color.outputs[0].default_value = (color[0], color[1], color[2], 1)


def update_material_fog(self, context):
    material = context.material
    nodes = material.node_tree.nodes
    group = nodes.get("nns fog")
    if group is not None:
        group.inputs[1].default_value = int(material.nns_fog)
    else:
        generate_nodes(material)


def update_light0(self, context):
    for mat in bpy.data.materials.values():
        if mat.is_nns:
            if "nr" in mat.nns_mat_type:
                nodes = mat.node_tree.nodes
                col = nodes.get("Light0 Color")
                if col is not None:
                    col.outputs[0].default_value = (bpy.context.scene.Light0_color[0],
                                                    bpy.context.scene.Light0_color[1],
                                                    bpy.context.scene.Light0_color[2],
                                                    1.0)
                    vec = nodes.get("Light0 Vector")
                    for i in range(3):
                        vec.inputs[i].default_value = bpy.context.scene.Light0_vector[i]
                    spec = nodes.get("Light0 Specular")
                    spec.outputs[0].default_value = bpy.context.scene.Light0_specular


def update_light1(self, context):
    for mat in bpy.data.materials.values():
        if mat.is_nns:
            if "nr" in mat.nns_mat_type:
                nodes = mat.node_tree.nodes
                col = nodes.get("Light1 Color")
                if col is not None:
                    col.outputs[0].default_value = (bpy.context.scene.Light1_color[0],
                                                    bpy.context.scene.Light1_color[1],
                                                    bpy.context.scene.Light1_color[2],
                                                    1.0)
                    vec = nodes.get("Light1 Vector")
                    for i in range(3):
                        vec.inputs[i].default_value = bpy.context.scene.Light1_vector[i]
                    spec = nodes.get("Light1 Specular")
                    spec.outputs[0].default_value = bpy.context.scene.Light1_specular


def update_light2(self, context):
    for mat in bpy.data.materials.values():
        if mat.is_nns:
            if "nr" in mat.nns_mat_type:
                nodes = mat.node_tree.nodes
                col = nodes.get("Light2 Color")
                if col is not None:
                    col.outputs[0].default_value = (bpy.context.scene.Light2_color[0],
                                                    bpy.context.scene.Light2_color[1],
                                                    bpy.context.scene.Light2_color[2],
                                                    1.0)
                    vec = nodes.get("Light2 Vector")
                    for i in range(3):
                        vec.inputs[i].default_value = bpy.context.scene.Light2_vector[i]
                    spec = nodes.get("Light2 Specular")
                    spec.outputs[0].default_value = bpy.context.scene.Light2_specular


def update_light3(self, context):
    for mat in bpy.data.materials.values():
        if mat.is_nns:
            if "nr" in mat.nns_mat_type:
                nodes = mat.node_tree.nodes
                col = nodes.get("Light3 Color")
                if col is not None:
                    col.outputs[0].default_value = (bpy.context.scene.Light3_color[0],
                                                    bpy.context.scene.Light3_color[1],
                                                    bpy.context.scene.Light3_color[2],
                                                    1.0)
                    vec = nodes.get("Light3 Vector")
                    for i in range(3):
                        vec.inputs[i].default_value = bpy.context.scene.Light3_vector[i]
                    spec = nodes.get("Light3 Specular")
                    spec.outputs[0].default_value = bpy.context.scene.Light3_specular


def update_nodes_mode(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_mat_type(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_image(self, context):
    material = context.material
    if material.is_nns:
        if material.nns_image != '':
            try:
                node_image = material.node_tree.nodes.get('nns_node_image')
                node_image.image = material.nns_image
            except Exception:
                raise NameError("Cannot load image")


def _apply_alpha_to_nodes(material):
    if material.is_nns:
        if material.nns_polygon_mode == "modulate":
            try:
                node_alpha = material.node_tree.nodes.get('nns_node_alpha')
                node_alpha.blend_type = "MULTIPLY"
                node_alpha.inputs[2].default_value = (
                    material.nns_alpha / 31,
                    material.nns_alpha / 31,
                    material.nns_alpha / 31,
                    1.0
                )
            except Exception:
                raise NameError("Something alpha I think")
        elif material.nns_polygon_mode == "decal":
            try:
                node_alpha = material.node_tree.nodes.get('nns_node_alpha')
                node_alpha.blend_type = "MIX"
                node_alpha.inputs[1].default_value = (0, 0, 0, 1)
                node_alpha.inputs[0].default_value = material.nns_alpha / 31
            except Exception:
                raise NameError("Something alpha I think")


def update_nodes_alpha(self, context):
    _apply_alpha_to_nodes(context.material)


def _apply_diffuse_to_nodes(material):
    if material.is_nns:
        if material.nns_mat_type == "df" or material.nns_mat_type == "tx_df":
            node_diffuse = material.node_tree.nodes.get('nns_node_diffuse')
            node_diffuse.inputs[2].default_value = (
                material.nns_diffuse[0],
                material.nns_diffuse[1],
                material.nns_diffuse[2],
                1.0
            )
        if "nr" in material.nns_mat_type:
            node_diffuse1 = material.node_tree.nodes.get("df")
            node_diffuse1.outputs[0].default_value = (
                material.nns_diffuse[0],
                material.nns_diffuse[1],
                material.nns_diffuse[2],
                1.0
            )
            node_diffuse2 = material.node_tree.nodes.get("UseOnlyDiffuse?")
            node_diffuse2.inputs[2].default_value = (
                material.nns_diffuse[0],
                material.nns_diffuse[1],
                material.nns_diffuse[2],
                1.0
            )


def update_nodes_diffuse(self, context):
    _apply_diffuse_to_nodes(context.material)


def _apply_emission_to_nodes(material):
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_emission = material.node_tree.nodes.get("em")
            node_emission.outputs[0].default_value = (
                material.nns_emission[0],
                material.nns_emission[1],
                material.nns_emission[2],
                1.0
            )


def update_nodes_emission(self, context):
    _apply_emission_to_nodes(context.material)


def _apply_ambient_to_nodes(material):
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_emission = material.node_tree.nodes.get("amb")
            node_emission.outputs[0].default_value = (
                material.nns_ambient[0],
                material.nns_ambient[1],
                material.nns_ambient[2],
                1.0
            )


def update_nodes_ambient(self, context):
    _apply_ambient_to_nodes(context.material)


def _apply_specular_to_nodes(material):
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_specular = material.node_tree.nodes.get("spec")
            node_specular.outputs[0].default_value = (
                material.nns_specular[0],
                material.nns_specular[1],
                material.nns_specular[2],
                1.0
            )


def update_nodes_specular(self, context):
    _apply_specular_to_nodes(context.material)


def update_nodes_use_only_diffuse(material):
    mask_node = material.node_tree.nodes.get("UseOnlyDiffuse?")
    use_only_diffuse = True
    lights = (material.nns_light0, material.nns_light1, material.nns_light2, material.nns_light3)
    for light in lights:
        if light:
            use_only_diffuse = False
    mask_node.inputs[0].default_value = use_only_diffuse


def update_nodes_light0(self, context):
    material = context.material
    update_nodes_use_only_diffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_light0 = material.node_tree.nodes.get("Light0 Enabled")
            node_light0.outputs[0].default_value = material.nns_light0


def update_nodes_light1(self, context):
    material = context.material
    update_nodes_use_only_diffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_light1 = material.node_tree.nodes.get("Light1 Enabled")
            node_light1.outputs[0].default_value = material.nns_light1


def update_nodes_light2(self, context):
    material = context.material
    update_nodes_use_only_diffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_light2 = material.node_tree.nodes.get("Light2 Enabled")
            node_light2.outputs[0].default_value = material.nns_light2


def update_nodes_light3(self, context):
    material = context.material
    update_nodes_use_only_diffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_light3 = material.node_tree.nodes.get("Light3 Enabled")
            node_light3.outputs[0].default_value = material.nns_light3


def update_nodes_face(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_tex_gen(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_srt(material):
    if material.is_nns:
        if "tx" in material.nns_mat_type:
            try:
                node_rt = material.node_tree.nodes.get('nns_node_rt')
                node_rt.inputs[1].default_value = (
                    -material.nns_srt_translate[0],
                    -material.nns_srt_translate[1],
                    0
                )
                node_rt.inputs[2].default_value[2] = material.nns_srt_rotate
                node_s = material.node_tree.nodes.get('nns_node_s')
                node_s.inputs[3].default_value = (
                    material.nns_srt_scale[0],
                    material.nns_srt_scale[1],
                    0
                )

                node_i = material.node_tree.nodes.get('nns_node_image')
                if material.nns_texframe_reference:
                    node_i.image = material.nns_texframe_reference[material.nns_texframe_reference_index].image
                else:
                    node_i.image = material.nns_image
            except Exception:
                raise NameError("Couldn't find node?")


def update_nodes_srt_hook(self, context):
    for material in bpy.data.materials.values():
        if material.is_nns:
            update_nodes_srt(material)


@persistent
def frame_change_handler(scene):
    active_object = bpy.context.active_object
    if active_object and active_object.active_material:
        material = active_object.active_material
        update_nodes_srt(material)
        # These five used to only refresh when the property's own update= callback fired which Blender does NOT do when a value changes because of keyframed animation playback/scrubbing (only when a person edits it directly in the UI). That made an animated material color (e.g. an .ima diffuse animation) look frozen in the viewport until you happened to click the property, at which point it would "snap" to the already-correct-but-not-yet-displayed value. Refreshing them here too, on every frame change, keeps the preview in sync during playback the same way the SRT nodes already were.
        _apply_diffuse_to_nodes(material)
        _apply_ambient_to_nodes(material)
        _apply_specular_to_nodes(material)
        _apply_emission_to_nodes(material)
        _apply_alpha_to_nodes(material)


@persistent
def migrate_legacy_textures(dummy=None):
    """Runs on file load (and once immediately when the addon is
    (re)enabled, in case a file with old-style materials is already
    open when that happens).

    Materials saved with an older version of this plugin store their
    texture in nns_image; this version reads a material's texture
    entirely from the texture pattern list (nns_texframe_reference)
    instead, so old files don't lose their textures. Also recomputes
    nns_mat_type for every NNS material, since a fresh file predates the
    color-type/light-driven computation this version relies on and
    would otherwise keep whatever value was saved from the old direct
    dropdown.
    """
    for material in bpy.data.materials:
        if not getattr(material, 'is_nns', False):
            continue

        if material.nns_image and not material.nns_texframe_reference:
            ref = material.nns_texframe_reference.add()
            ref.image = material.nns_image
            material.nns_image = None

        material.nns_mat_type = compute_mat_type(material)
        generate_nodes(material)


def create_nns_material(obj):
    material = bpy.data.materials.new('Material')
    obj.data.materials.append(material)
    if bpy.context.object is not None:
        bpy.context.object.active_material_index = len(obj.material_slots) - 1

    material.is_nns = True
    material.use_nodes = True
    material.blend_method = 'CLIP'

    generate_nodes(material)


# This class is taken and modified from kurethedead's fast64 plugin.
class CreateNNSMaterial(bpy.types.Operator):
    bl_idname = 'object.create_nns_material'
    bl_label = "Create NNS Material"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    def execute(self, context):
        obj = bpy.context.view_layer.objects.active
        if obj is None:
            self.report({'ERROR'}, 'No active object selected.')
        else:
            create_nns_material(obj)
            self.report({'INFO'}, 'NNS: Created new material.')
        return {'FINISHED'}


class NTRTexReference(bpy.types.PropertyGroup):
    image: PointerProperty(
        name='Texture',
        type=Image)


class NewTexReference(bpy.types.Operator):
    bl_idname = "nns_texframe_reference.new_texref"
    bl_label = "Add a new texture reference"

    def execute(self, context):
        context.material.nns_texframe_reference.add()
        refresh_mat_type(context.material)

        return {'FINISHED'}


class DeleteTexReference(bpy.types.Operator):
    bl_idname = "nns_texframe_reference.delete_texref"
    bl_label = "Deletes a texture reference"

    @classmethod
    def poll(cls, context):
        return context.material.nns_texframe_reference

    def execute(self, context):
        my_list = context.material.nns_texframe_reference
        index = context.material.nns_texframe_reference_index

        my_list.remove(index)
        context.material.nns_texframe_reference_index = min(
            max(0, index - 1), len(my_list) - 1)
        refresh_mat_type(context.material)

        return {'FINISHED'}


class NTR_UL_texframe(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if item.image:
                layout.label(text=item.image.name, translate=False,
                             icon_value=layout.icon(item.image))
            else:
                layout.label(text="", translate=False, icon='FILE_IMAGE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class NTR_PT_material_texframe(bpy.types.Panel):
    bl_label = "NNS Material Textures"
    bl_idname = "MATERIAL_TEXFRAME_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        mat = context.material

        if mat is None:
            pass
        elif not (mat.use_nodes and mat.is_nns):
            pass
        else:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material Textures")
            layout.label(
                text="No entries: the DS uses the solid/vertex color "
                     "above. One entry: that's the base texture. More "
                     "than one: enables .itp pattern animation.")
            layout.template_list("NTR_UL_texframe", "",
                                 mat, "nns_texframe_reference",
                                 mat, "nns_texframe_reference_index")

            row = layout.row()
            row.operator('nns_texframe_reference.new_texref', text='New')
            row.operator('nns_texframe_reference.delete_texref', text='Delete')

            if (mat.nns_texframe_reference_index >= 0
                    and mat.nns_texframe_reference):
                idx = mat.nns_texframe_reference_index
                item = mat.nns_texframe_reference[idx]

                row = layout.row()
                row.template_ID(item, "image", open="image.open")


class NTR_PT_material_keyframe(bpy.types.Panel):
    bl_label = "NNS Material Keyframes"
    bl_idname = "MATERIAL_KEYFRAME_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        if mat is None:
            pass
        elif not (mat.use_nodes and mat.is_nns):
            pass
        elif "tx" in mat.nns_mat_type:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material SRT")
            layout.row(align=True).prop(mat, "nns_srt_scale")
            layout.prop(mat, "nns_srt_rotate")
            layout.row(align=True).prop(mat, "nns_srt_translate")


class NTR_PT_material_visual(bpy.types.Panel):
    bl_label = "NNS Material visual options"
    bl_idname = "MATERIAL_VISUAL_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        layout = layout.box()
        title = layout.column()
        title.box().label(text="NNS Material Visual Options")
        layout.prop(mat, "nns_hdr_add_self")


class SCENE_PT_NNS_Panel(bpy.types.Panel):
    bl_label = "nns scene settings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "NNS Scene"

    def draw(self, context):
        layout = self.layout
        layout.scale_x = 5.0

        # disclaimer

        layout.label(text="/!\\ These settings are only for preview purpose,\n they won't be exported")

        # Fog Only reads existing data here, never creates the "nns fog" node group from inside draw(). Blender doesn't allow creating/writing ID datablocks (node groups, nodes, ...) during panel drawing. doing that here used to crash this entire sidebar tab (including any other panel sharing it) the moment it was drawn in a file with no NNS material yet, since that's exactly when the group doesn't exist. The group gets created properly by generate_fog_material_nodes()/update_fog_group_nodes(), which only ever run from an actual operator or a property update callback, both valid contexts for creating data.
        fog_group = bpy.data.node_groups.get("nns fog")
        curve_node = fog_group.nodes.get("curve") if fog_group else None

        box = layout.box()
        box.label(text="Fog properties:")

        if curve_node is None:
            box.label(text="Create an NNS material first to preview fog.")
        else:
            box.label(text="Fog density curve:")
            box.template_curve_mapping(curve_node, "mapping")

            col = box.split(factor=0.5, align=True)
            col1 = col.column(align=True)
            col1.prop(context.scene, "Fog_enable", text="enable fog")
            col1.prop(context.scene, "Fog_color", text="fog color")
            col2 = col.column(align=True)
            col2.prop(context.scene, "Fog_scale", text="scale")
            col2.prop(context.scene, "Fog_offset", text="fog offset")

        # Light 0
        box = layout.box()
        box.label(text="Light 0 properties:")
        col = box.split(factor=0.5, align=True)
        col1 = col.column(align=True)
        col1.prop(context.scene, "Light0_color", text="color")
        col1.prop(context.scene, "Light0_specular", text="specular")
        col2 = col.column(align=True)
        col2.prop(context.scene, "Light0_vector", text="vector")

        # Light 1
        box = layout.box()
        box.label(text="Light 1 properties:")
        col = box.split(factor=0.5, align=True)
        col1 = col.column(align=True)
        col1.prop(context.scene, "Light1_color", text="color")
        col1.prop(context.scene, "Light1_specular", text="specular")
        col2 = col.column(align=True)
        col2.prop(context.scene, "Light1_vector", text="vector")

        # Light 2
        box = layout.box()
        box.label(text="Light 2 properties:")
        col = box.split(factor=0.5, align=True)
        col1 = col.column(align=True)
        col1.prop(context.scene, "Light2_color", text="color")
        col1.prop(context.scene, "Light2_specular", text="specular")
        col2 = col.column(align=True)
        col2.prop(context.scene, "Light2_vector", text="vector")

        # Light 3
        box = layout.box()
        box.label(text="Light 3 properties:")
        col = box.split(factor=0.5, align=True)
        col1 = col.column(align=True)
        col1.prop(context.scene, "Light3_color", text="color")
        col1.prop(context.scene, "Light3_specular", text="specular")
        col2 = col.column(align=True)
        col2.prop(context.scene, "Light3_vector", text="vector")


class NTR_PT_material(bpy.types.Panel):
    bl_label = "NNS Material"
    bl_idname = "MATERIAL_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        layout.operator(CreateNNSMaterial.bl_idname)


class NTR_PT_material_options(bpy.types.Panel):
    bl_label = "NNS Material Settings"
    bl_idname = "MATERIAL_OPTIONS_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        if mat is None:
            pass
        elif not (mat.use_nodes and mat.is_nns):
            pass
        else:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material Settings")

            layout.prop(mat, "nns_color_type")

            any_light_on = (mat.nns_light0 or mat.nns_light1
                             or mat.nns_light2 or mat.nns_light3)

            # Diffuse and emission are shown side by side since they're both always relevant regardless of lighting state. Ambient and specular only ever have a visible effect when combined with an active light's color, with every light off they contribute nothing, so they're grouped together right below and only shown once at least one light is on. Alpha comes last since it's independent of all of the above.
            if mat.nns_color_type == 'solid':
                row = layout.row()
                row.prop(mat, "nns_diffuse")
                row.prop(mat, "nns_emission")
            else:
                layout.label(
                    text='Note: There must be a vertex color layer named '
                         '"Col"')
                layout.row().prop(mat, "nns_emission")

            if any_light_on:
                row = layout.row()
                row.prop(mat, "nns_ambient")
                row.prop(mat, "nns_specular")

            layout.row().prop(mat, "nns_alpha", slider=True)

            row = layout.row(align=True)
            row.prop(mat, "nns_light0", toggle=True)
            row.prop(mat, "nns_light1", toggle=True)
            row.prop(mat, "nns_light2", toggle=True)
            row.prop(mat, "nns_light3", toggle=True)

            layout.prop(mat, "nns_use_srst")
            layout.prop(mat, "nns_fog")
            layout.prop(mat, "nns_wireframe")
            layout.prop(mat, "nns_depth_test")
            layout.prop(mat, "nns_update_depth_buffer")
            layout.prop(mat, "nns_render_1_pixel")
            layout.prop(mat, "nns_far_clipping")
            layout.prop(mat, "nns_polygonid")
            layout.prop(mat, "nns_priorityid")
            layout.prop(mat, "nns_display_face")
            layout.prop(mat, "nns_polygon_mode")

            if "tx" in mat.nns_mat_type:
                layout.prop(mat, "nns_tex_tiling_u")
                layout.prop(mat, "nns_tex_tiling_v")
                layout.row(align=True).prop(mat, "nns_tex_scale")
                layout.prop(mat, "nns_tex_rotate")
                layout.row(align=True).prop(mat, "nns_tex_translate")
                layout.prop(mat, "nns_tex_gen_mode")

            if mat.nns_tex_gen_mode == 'nrm' or mat.nns_tex_gen_mode == 'pos':
                layout.prop(mat, "nns_tex_gen_st_src")
                box = layout.box()
                box.label(text="Texture effect matrix")
                row = box.row(align=True)
                row.prop(mat, "nns_tex_effect_mtx_0")
                row = box.row(align=True)
                row.prop(mat, "nns_tex_effect_mtx_1")
                row = box.row(align=True)
                row.prop(mat, "nns_tex_effect_mtx_2")
                row = box.row(align=True)
                row.prop(mat, "nns_tex_effect_mtx_3")


def material_register():
    safe_register_class(NTRTexReference)
    safe_register_class(NewTexReference)
    safe_register_class(DeleteTexReference)
    bpy.types.Material.nns_texframe_reference = CollectionProperty(
        type=NTRTexReference)
    bpy.types.Material.nns_texframe_reference_index = IntProperty(
        name="Active texture reference index", default=0, update=update_nodes_srt_hook)  

    bpy.types.Material.nns_hdr_add_self = BoolProperty(
        default=False, name="HDR shaders", update=update_nodes_mode)
    bpy.types.Material.is_nns = BoolProperty(default=False)
    mat_type_items = [
        ("df", "Solid color", '', 1),
        ("df_nr", "Solid color + normals", '', 2),
        ("vc", "Vertex colored", '', 3),
        ("tx_df", "Textured + solid color", '', 4),
        ("tx_vc", "Textured + vertex colors", '', 5),
        ("tx_nr_df", "Textured + normals", '', 6),
        ("vc_nr", "Vertex colored + normals", '', 7),
        ("tx_vc_nr", "Textured + vertex colors + normals", '', 8),
    ]
    bpy.types.Material.nns_mat_type = EnumProperty(
        name="Material type", items=mat_type_items,
        update=update_nodes_mat_type)

    color_type_items = [
        ("solid", "Solid color", '', 1),
        ("vertex", "Vertex colors", '', 2),
    ]
    bpy.types.Material.nns_color_type = EnumProperty(
        name="Color type",
        description=(
            "Where this material's base color comes from before any "
            "lighting or texture is applied: either a fixed color you "
            "set below, or the mesh's own vertex color data"
        ),
        items=color_type_items,
        default='solid',
        update=update_computed_mat_type)
    bpy.types.Material.nns_image = PointerProperty(
        name='Texture', type=Image, update=update_nodes_image)
    bpy.types.Material.nns_diffuse = FloatVectorProperty(
        default=(1, 1, 1), subtype='COLOR', min=0.0, max=1.0, name='Diffuse',
        update=update_nodes_diffuse)
    bpy.types.Material.nns_ambient = FloatVectorProperty(
        default=(1, 1, 1), subtype='COLOR', min=0.0, max=1.0, name='Ambient',
        update=update_nodes_ambient)
    bpy.types.Material.nns_specular = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Specular',
        update=update_nodes_specular)
    bpy.types.Material.nns_emission = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Emission',
        update=update_nodes_emission)
    bpy.types.Material.nns_light0 = BoolProperty(name="Light0", default=False,
                                                 update=update_light_toggle)
    bpy.types.Material.nns_light1 = BoolProperty(name="Light1", default=False,
                                                 update=update_light_toggle)
    bpy.types.Material.nns_light2 = BoolProperty(name="Light2", default=False,
                                                 update=update_light_toggle)
    bpy.types.Material.nns_light3 = BoolProperty(name="Light3", default=False,
                                                 update=update_light_toggle)

    # scene fog properties

    bpy.types.Scene.Fog_enable = BoolProperty(name="Fog_enable", default=False, update=update_fog_group_nodes)
    bpy.types.Scene.Fog_color = bpy.types.Scene.Light0_color = FloatVectorProperty(
        name="Fog_color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker",
        update=update_fog_group_nodes
    )
    bpy.types.Scene.Fog_scale = FloatProperty(name="Fog_scale", default=1000, min=0.01, update=update_fog_group_nodes)
    bpy.types.Scene.Fog_offset = FloatProperty(name="Fog_offset", default=0, min=0, max=20, update=update_fog_group_nodes)

    # scene lights properties

    bpy.types.Scene.Light0_color = FloatVectorProperty(
        name="Light 0 color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker",
        update=update_light0
    )

    bpy.types.Scene.Light1_color = FloatVectorProperty(
        name="Light 1 color",
        subtype='COLOR',
        default=(1.0, 1.0, 1.0),
        min=0.0, max=1.0,
        description="color picker",
        update=update_light1
    )

    bpy.types.Scene.Light2_color = FloatVectorProperty(
        name="Light 2 color",
        subtype='COLOR',
        default=(1.0, 0, 0),
        min=0.0, max=1.0,
        description="color picker",
        update=update_light2
    )

    bpy.types.Scene.Light3_color = FloatVectorProperty(
        name="Light 3 color",
        subtype='COLOR',
        default=(1.0, 1.0, 0),
        min=0.0, max=1.0,
        description="color picker",
        update=update_light3
    )

    bpy.types.Scene.Light0_specular = FloatProperty(
        name="Light 0 specular",
        default=0.5,
        min=0,
        max=1,
        update=update_light0
    )

    bpy.types.Scene.Light1_specular = FloatProperty(
        name="Light 1 specular",
        default=1,
        min=0,
        max=1,
        update=update_light1
    )

    bpy.types.Scene.Light2_specular = FloatProperty(
        name="Light 2 specular",
        default=0.5,
        min=0,
        max=1,
        update=update_light2
    )

    bpy.types.Scene.Light3_specular = FloatProperty(
        name="Light 3 specular",
        default=0,
        min=0,
        max=1,
        update=update_light3
    )

    bpy.types.Scene.Light0_vector = FloatVectorProperty(
        name="Light 0 vector",
        subtype='XYZ',
        default=(0, 0, -1.0),
        min=-1.0, max=1.0,
        description="color picker",
        update=update_light0
    )

    bpy.types.Scene.Light1_vector = FloatVectorProperty(
        name="Light 1 vector",
        subtype='XYZ',
        default=(0, 0.5, -0.5),
        min=-1.0, max=1.0,
        description="color picker",
        update=update_light1
    )

    bpy.types.Scene.Light2_vector = FloatVectorProperty(
        name="Light 2 vector",
        subtype='XYZ',
        default=(0, 0, -1.0),
        min=-1.0, max=1.0,
        description="color picker",
        update=update_light2
    )

    bpy.types.Scene.Light3_vector = FloatVectorProperty(
        name="Light 3 vector",
        subtype='XYZ',
        default=(0, 0, 1.0),
        min=-1.0, max=1.0,
        description="color picker",
        update=update_light3
    )

    bpy.types.Material.nns_use_srst = BoolProperty(
        name="Use Specular Reflection Table", default=False)
    bpy.types.Material.nns_fog = BoolProperty(
        name="Fog", default=False, update=update_material_fog)
    bpy.types.Material.nns_wireframe = BoolProperty(
        name="Wireframe", default=False)
    bpy.types.Material.nns_depth_test = BoolProperty(
        name="Depth test for decal polygon", default=False)
    bpy.types.Material.nns_update_depth_buffer = BoolProperty(
        name="Translucent polygons update depth buffer", default=False)
    bpy.types.Material.nns_render_1_pixel = BoolProperty(
        name="Render 1-pixel polygon", default=False)
    bpy.types.Material.nns_far_clipping = BoolProperty(
        name="Far clipping", default=False)
    bpy.types.Material.nns_polygonid = IntProperty(
        name="Polygon ID", default=0)
    bpy.types.Material.nns_priorityid = IntProperty(
        name="Priority ID", default=0)
    display_face_items = [
        ("front", "Front face", '', 1),
        ("back", "Back face", '', 2),
        ("both", "Both faces", '', 3)
    ]
    bpy.types.Material.nns_display_face = EnumProperty(
        name="Display face", items=display_face_items,
        update=update_nodes_face)
    polygon_mode_items = [
        ("modulate", "Modulate", '', 1),
        ("decal", "Decal", '', 2),
        ("toon_highlight", "Toon/highlight", '', 3),
        ("shadow", "Shadow", '', 4)
    ]
    bpy.types.Material.nns_polygon_mode = EnumProperty(
        name="Polygon mode", items=polygon_mode_items,
        update=update_nodes_mode)
    tex_gen_mode_items = [
        ("none", "None", '', 1),
        ("tex", "Texcoord", '', 2),
        ("nrm", "Normal", '', 3),
        ("pos", "Vertex", '', 4)
    ]
    bpy.types.Material.nns_tex_gen_mode = EnumProperty(
        name="Tex gen mode", items=tex_gen_mode_items,
        update=update_nodes_tex_gen)
    tex_gen_st_src_items = [
        ("polygon", "Polygon", '', 1),
        ("material", "Material", '', 2),
    ]
    bpy.types.Material.nns_tex_gen_st_src = EnumProperty(
        name="Tex gen ST source", items=tex_gen_st_src_items)
    bpy.types.Material.nns_tex_effect_mtx_0 = FloatVectorProperty(
        size=2, name='', default=(1, 0))
    bpy.types.Material.nns_tex_effect_mtx_1 = FloatVectorProperty(
        size=2, name='', default=(0, 1))
    bpy.types.Material.nns_tex_effect_mtx_2 = FloatVectorProperty(
        size=2, name='')
    bpy.types.Material.nns_tex_effect_mtx_3 = FloatVectorProperty(
        size=2, name='')
    tex_tiling_items = [
        ("repeat", "Repeat", '', 1),
        ("flip", "Flip", '', 2),
        ("clamp", "Clamp", '', 3)
    ]
    bpy.types.Material.nns_tex_tiling_u = EnumProperty(
        name="Tex tiling u", items=tex_tiling_items, update=update_nodes_mode)
    bpy.types.Material.nns_tex_tiling_v = EnumProperty(
        name="Tex tiling v", items=tex_tiling_items, update=update_nodes_mode)
    bpy.types.Material.nns_alpha = IntProperty(
        name="Alpha", min=0, max=31, default=31, update=update_nodes_alpha)
    bpy.types.Material.nns_tex_scale = FloatVectorProperty(
        size=2, name="Texture scale", default=(1, 1))
    bpy.types.Material.nns_tex_rotate = FloatProperty(name="Texture rotation")
    bpy.types.Material.nns_tex_translate = FloatVectorProperty(
        size=2, name="Texture translation")

    bpy.types.Material.nns_srt_translate = FloatVectorProperty(
        size=2, name="Translate", update=update_nodes_srt_hook)
    bpy.types.Material.nns_srt_scale = FloatVectorProperty(
        size=2, name="Scale", update=update_nodes_srt_hook, default=(1, 1))
    bpy.types.Material.nns_srt_rotate = FloatProperty(
        name="Rotate", update=update_nodes_srt_hook, subtype='ANGLE')

    print("Register frame handler")
    bpy.app.handlers.frame_change_pre.append(frame_change_handler)

    # NOT called immediately here: bpy.data isn't accessible at all during register() (Blender blocks it through a restricted-context proxy since the file/data state isn't fully settled yet during addon enable), so migrate_legacy_textures() can only safely run from load_post, once an actual file has finished loading. A material that hasn't been migrated yet still works correctly in the meantime either way. get_material_texture_image() already falls back to reading nns_image directly when the pattern list is empty, so nothing is actually broken by the migration not having run yet, it just hasn't visually moved into the pattern list.
    bpy.app.handlers.load_post.append(migrate_legacy_textures)

    safe_register_class(CreateNNSMaterial)
    safe_register_class(NTR_PT_material_visual)
    # Registration order controls draw order for panels sharing the same bl_context, so this sequence is what keeps the create button, texture list, and settings panel appearing in that order in the UI.
    safe_register_class(NTR_PT_material)
    safe_register_class(NTR_UL_texframe)
    safe_register_class(NTR_PT_material_texframe)
    safe_register_class(NTR_PT_material_options)
    safe_register_class(NTR_PT_material_keyframe)
    safe_register_class(SCENE_PT_NNS_Panel)


def material_unregister():
    if frame_change_handler in bpy.app.handlers.frame_change_pre:
        bpy.app.handlers.frame_change_pre.remove(frame_change_handler)
    if migrate_legacy_textures in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(migrate_legacy_textures)

    bpy.utils.unregister_class(NTRTexReference)
    bpy.utils.unregister_class(NewTexReference)
    bpy.utils.unregister_class(DeleteTexReference)

    bpy.utils.unregister_class(CreateNNSMaterial)
    bpy.utils.unregister_class(NTR_PT_material_visual)
    bpy.utils.unregister_class(NTR_PT_material)
    bpy.utils.unregister_class(NTR_UL_texframe)
    bpy.utils.unregister_class(NTR_PT_material_texframe)
    bpy.utils.unregister_class(NTR_PT_material_options)
    bpy.utils.unregister_class(NTR_PT_material_keyframe)
    bpy.utils.unregister_class(SCENE_PT_NNS_Panel)
