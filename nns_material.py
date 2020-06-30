import bpy
from bpy.props import (BoolProperty,
                       FloatProperty,
                       EnumProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty)
from bpy.types import Image
from bpy.app.handlers import persistent


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
    node_sub.location = (-100,0)
    node_sub.inputs[1].default_value = (0.5, 0.5, 0.5)
    
    node_rt_mapping = nodes.new(type='ShaderNodeMapping')
    node_rt_mapping.name = 'nns_node_rt'
    node_rt_mapping.location = (0,0)
    node_rt_mapping.inputs[3].default_value = (1, 1, 1)

    node_add = nodes.new(type='ShaderNodeVectorMath')
    node_add.operation = 'ADD'
    node_add.location = (100,0)
    node_add.inputs[1].default_value = (0.5, 0.5, 0.5)
    
    node_s_mapping = nodes.new(type='ShaderNodeMapping')
    node_s_mapping.name = 'nns_node_s'
    node_s_mapping.location = (200,0)
    node_s_mapping.inputs[3].default_value = (1, 1, 1)

    links.new(input.outputs[0], node_sub.inputs[0])
    links.new(node_sub.outputs[0], node_rt_mapping.inputs[0])
    links.new(node_rt_mapping.outputs[0], node_add.inputs[0])
    links.new(node_add.outputs[0], node_s_mapping.inputs[0])

    return node_s_mapping


def generate_image_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_image = nodes.new(type='ShaderNodeTexImage')
    node_image.name = 'nns_node_image'
    node_image.interpolation = 'Closest'
    if material.nns_image != '':
        try:
            node_image.image = material.nns_image
        except Exception:
            raise NameError("Cannot load image %s" % path)

    # Make this ahead of time. Must always be filled.
    node_srt = None

    if material.nns_tex_gen_mode == "nrm":
        node_geo = nodes.new(type='ShaderNodeNewGeometry')
        node_vec_trans = nodes.new(type='ShaderNodeVectorTransform')
        node_vec_trans.convert_from = 'OBJECT'
        node_vec_trans.convert_to = 'CAMERA'
        node_vec_trans.vector_type = 'NORMAL'
        node_mapping = nodes.new(type='ShaderNodeMapping')
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

    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    links.new(node_mix.outputs[0], node_multiply.inputs[1])
    links.new(node_multiply.outputs[0], node_mix_shader.inputs[2])

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_mix_shader.outputs[0], node_output.inputs[0])

    if "vc" in material.nns_mat_type:
        node_attr = nodes.new(type='ShaderNodeAttribute')
        node_attr.attribute_name = 'Col'
        links.new(node_attr.outputs[0], node_multiply.inputs[2])


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

    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    links.new(node_mix_2.outputs[0], node_mix_shader.inputs[2])
    links.new(node_trans_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_mix_shader.outputs[0], node_output.inputs[0])

    if "vc" in material.nns_mat_type:
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

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])


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
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
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
    links.new(node_mix_shader.outputs[0], node_output.inputs[0])


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
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    node_output.location = (400, 0)

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_mix_df.outputs[0], node_mix_shader.inputs[2])
    links.new(node_mix_shader.outputs[0], node_output.inputs[0])


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
    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_vc.outputs[0], node_mix_shader.inputs[2])
    links.new(node_mix_shader.outputs[0], node_output.inputs[0])


def generate_nodes(material):
    if material.is_nns:
        nodes = material.node_tree.nodes
        nodes.clear()
        links = material.node_tree.links
        links.clear()

        if material.nns_mat_type == "tx":
            generate_image_only_nodes(material)
        elif material.nns_mat_type == "df":
            generate_solid_color_nodes(material)
        elif material.nns_mat_type == "vc":
            generate_only_vc_nodes(material)
        elif material.nns_polygon_mode == "modulate" \
                or material.nns_polygon_mode == "toon_highlight" \
                or material.nns_polygon_mode == "shadow":
            generate_mod_vc_nodes(material)
        elif material.nns_polygon_mode == "decal":
            generate_decal_vc_nodes(material)


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
                raise NameError("Cannot load image %s" % path)


def update_nodes_alpha(self, context):
    material = context.material
    if material.is_nns:
        if material.nns_polygon_mode == "modulate":
            try:
                node_alpha = material.node_tree.nodes.get('nns_node_alpha')
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
                node_alpha.inputs[0].default_value = material.nns_alpha / 31
            except Exception:
                raise NameError("Something alpha I think")


def update_nodes_diffuse(self, context):
    material = context.material
    if material.is_nns:
        node_diffuse = material.node_tree.nodes.get('nns_node_diffuse')
        node_diffuse.inputs[2].default_value = (
            material.nns_diffuse[0],
            material.nns_diffuse[1],
            material.nns_diffuse[2],
            1.0
        )


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
            except Exception:
                raise NameError("Couldn't find node?")


def update_nodes_srt_hook(self, context):
    material = context.material
    update_nodes_srt(material)


@persistent
def frame_change_handler(scene):
    if bpy.context.active_object.active_material:
        material = bpy.context.active_object.active_material
        update_nodes_srt(material)


def create_nns_material(obj):
    material = bpy.data.materials.new('Material')
    obj.data.materials.append(material)
    if bpy.context.object is not None:
        bpy.context.object.active_material_index = len(obj.material_slots) - 1

    material.is_nns = True
    material.use_nodes = True
    material.blend_method = 'BLEND'

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
        elif not(mat.use_nodes and mat.is_nns):
            pass
        elif "tx" in mat.nns_mat_type:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material SRT")
            layout.row(align=True).prop(mat, "nns_srt_scale")
            layout.prop(mat, "nns_srt_rotate")
            layout.row(align=True).prop(mat, "nns_srt_translate")


class NTR_PT_material(bpy.types.Panel):
    bl_label = "NNS Material Options"
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
        mat = context.material

        layout.operator(CreateNNSMaterial.bl_idname)

        if mat is None:
            pass
        elif not(mat.use_nodes and mat.is_nns):
            pass
        else:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material Options")

            layout.prop(mat, "nns_mat_type")

            if "vc" in mat.nns_mat_type:
                layout.label(
                    text='Note: There must be a vertex color layer named '
                         '"Col"')

            if "tx" in mat.nns_mat_type:
                layout.template_ID(mat, "nns_image", open="image.open")

            if "df" in mat.nns_mat_type:
                layout.row().prop(mat, "nns_diffuse")

            if "nr" in mat.nns_mat_type:
                layout.row().prop(mat, "nns_ambient")
                layout.row().prop(mat, "nns_specular")
                layout.row().prop(mat, "nns_emission")

            layout.row().prop(mat, "nns_alpha", slider=True)

            if "nr" in mat.nns_mat_type:
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
    bpy.types.Material.is_nns = BoolProperty(default=False)
    mat_type_items = [
        ("df", "Solid color", '', 1),
        ("df_nr", "Solid color + normals", '', 2),
        ("vc", "Vertex colored", '', 3),
        ("tx_df", "Textured + solid color", '', 4),
        ("tx_vc", "Textured + vertex colors", '', 5),
        ("tx_nr_df", "Textured + normals", '', 6)
    ]
    bpy.types.Material.nns_mat_type = EnumProperty(
        name="Material type", items=mat_type_items,
        update=update_nodes_mat_type)
    bpy.types.Material.nns_image = PointerProperty(
        name='Texture', type=Image, update=update_nodes_image)
    bpy.types.Material.nns_diffuse = FloatVectorProperty(
        default=(1, 1, 1), subtype='COLOR', min=0.0, max=1.0, name='Diffuse',
        update=update_nodes_diffuse)
    bpy.types.Material.nns_ambient = FloatVectorProperty(
        default=(1, 1, 1), subtype='COLOR', min=0.0, max=1.0, name='Ambient')
    bpy.types.Material.nns_specular = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Specular')
    bpy.types.Material.nns_emission = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Emission')
    bpy.types.Material.nns_light0 = BoolProperty(name="Light0", default=False)
    bpy.types.Material.nns_light1 = BoolProperty(name="Light1", default=False)
    bpy.types.Material.nns_light2 = BoolProperty(name="Light2", default=False)
    bpy.types.Material.nns_light3 = BoolProperty(name="Light3", default=False)
    bpy.types.Material.nns_use_srst = BoolProperty(
        name="Use Specular Reflection Table", default=False)
    bpy.types.Material.nns_fog = BoolProperty(
        name="Fog", default=False)
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
    bpy.types.Material.nns_tex_effect_mtx_0 = FloatVectorProperty(size=2,
                                                                  name='')
    bpy.types.Material.nns_tex_effect_mtx_1 = FloatVectorProperty(size=2,
                                                                  name='')
    bpy.types.Material.nns_tex_effect_mtx_2 = FloatVectorProperty(size=2,
                                                                  name='')
    bpy.types.Material.nns_tex_effect_mtx_3 = FloatVectorProperty(size=2,
                                                                  name='')
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

    bpy.utils.register_class(CreateNNSMaterial)
    bpy.utils.register_class(NTR_PT_material)
    bpy.utils.register_class(NTR_PT_material_keyframe)


def material_unregister():
    bpy.utils.unregister_class(CreateNNSMaterial)
    bpy.utils.unregister_class(NTR_PT_material)
    bpy.utils.unregister_class(NTR_PT_material_keyframe)
