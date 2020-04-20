import bpy
from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       IntProperty,
                       FloatVectorProperty)


def generate_tiling_nodes(material, nodes, links, node_image):

    node_uvmap = nodes.new(type='ShaderNodeUVMap')
    node_uvmap.uv_map = "UVMap"

    node_sp_xyz = nodes.new(type='ShaderNodeSeparateXYZ')
    links.new(node_uvmap.outputs[0], node_sp_xyz.inputs[0])

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
        node_math_u.inputs[1].default_value = 1.0
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
        node_math_v.inputs[1].default_value = 1.0
        node_math_v.use_clamp = True
        links.new(node_sp_xyz.outputs[1], node_math_v.inputs[0])
        links.new(node_math_v.outputs[0], node_cb_xyz.inputs[1])
    else:
        links.new(node_sp_xyz.outputs[1], node_cb_xyz.inputs[1])

    links.new(node_cb_xyz.outputs[0], node_image.inputs[0])


def generate_mod_vc_nodes(material):
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    links.clear()

    node_image = nodes.new(type='ShaderNodeTexImage')
    node_image.name = 'nns_input_image'
    node_image.interpolation = 'Closest'

    if material.nns_image != '':
        try:
            image = bpy.data.images.load(material.nns_image,
                                         check_existing=True)
            node_image.image = image
        except Exception:
            raise NameError("Cannot load image %s" % path)

    generate_tiling_nodes(material, nodes, links, node_image)

    node_attr = nodes.new(type='ShaderNodeAttribute')
    node_attr.attribute_name = 'Col'
    node_mix = nodes.new(type='ShaderNodeMixRGB')
    node_mix.inputs[0].default_value = 0.0
    node_multiply = nodes.new(type='ShaderNodeMixRGB')
    node_multiply.blend_type = 'MULTIPLY'
    node_multiply.inputs[0].default_value = 1.0
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    links.new(node_image.outputs[0], node_mix.inputs[1])
    links.new(node_image.outputs[1], node_mix.inputs[2])
    links.new(node_image.outputs[1], node_mix_shader.inputs[0])
    links.new(node_mix.outputs[0], node_multiply.inputs[1])
    links.new(node_attr.outputs[0], node_multiply.inputs[2])
    links.new(node_multiply.outputs[0], node_mix_shader.inputs[2])
    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_mix_shader.outputs[0], node_output.inputs[0])


def generate_decal_vc_nodes(material):
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links
    links.clear()

    node_image = nodes.new(type='ShaderNodeTexImage')
    node_image.name = 'nns_input_image'
    node_image.interpolation = 'Closest'

    if material.nns_image != '':
        try:
            image = bpy.data.images.load(material.nns_image,
                                         check_existing=True)
            node_image.image = image
        except Exception:
            raise NameError("Cannot load image %s" % path)

    generate_tiling_nodes(material, nodes, links, node_image)

    node_attr = nodes.new(type='ShaderNodeAttribute')
    node_attr.attribute_name = 'Col'
    node_mix_1 = nodes.new(type='ShaderNodeMixRGB')
    node_mix_1.inputs[0].default_value = 0.0
    node_mix_2 = nodes.new(type='ShaderNodeMixRGB')
    node_output = nodes.new(type='ShaderNodeOutputMaterial')

    links.new(node_image.outputs[0], node_mix_1.inputs[1])
    links.new(node_image.outputs[1], node_mix_1.inputs[2])
    links.new(node_image.outputs[1], node_mix_2.inputs[0])

    links.new(node_mix_1.outputs[0], node_mix_2.inputs[2])

    links.new(node_attr.outputs[0], node_mix_2.inputs[1])

    links.new(node_mix_2.outputs[0], node_output.inputs[0])


def generate_nodes(material):
    if material.is_nns:
        if material.nns_polygon_mode == "modulate":
            generate_mod_vc_nodes(material)
        elif material.nns_polygon_mode == "decal":
            generate_decal_vc_nodes(material)


def update_nodes_mode(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_image(self, context):
    material = context.material
    if material.is_nns:
        if material.nns_image != '':
            try:
                image = bpy.data.images.load(material.nns_image)
                node_image = material.node_tree.nodes.get('nns_input_image')
                node_image.image = image
            except Exception:
                raise NameError("Cannot load image %s" % path)


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
            self.report({'INFO'}, 'Created new NNS material.')
        return {'FINISHED'}


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
            title.label(text="NNS Material Options")

            layout.prop(mat, "nns_image")
            layout.row().prop(mat, "nns_diffuse")
            layout.row().prop(mat, "nns_ambient")
            layout.row().prop(mat, "nns_specular")
            layout.row().prop(mat, "nns_emission")

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
            layout.prop(mat, "nns_tex_tiling_u")
            layout.prop(mat, "nns_tex_tiling_v")
            layout.prop(mat, "nns_polygon_mode")
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
    bpy.types.Material.nns_image = StringProperty(
        subtype='FILE_PATH', name='Texture', update=update_nodes_image)
    bpy.types.Material.nns_diffuse = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Diffuse')
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
        name="Display face", items=display_face_items)
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
        name="Tex gen mode", items=tex_gen_mode_items)
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

    bpy.utils.register_class(CreateNNSMaterial)
    bpy.utils.register_class(NTR_PT_material)


def material_unregister():
    bpy.utils.unregister_class(CreateNNSMaterial)
    bpy.utils.unregister_class(NTR_PT_material)
