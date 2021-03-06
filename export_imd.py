import bpy
import math
from mathutils import Vector
import xml.etree.ElementTree as ET
import json
from .nns_model import NitroModel
from .util import VecFx32


settings = None


def generate_model_info(imd, model):
    model_info = ET.SubElement(imd, 'model_info')
    model_info.set('pos_scale', str(model.info.pos_scale))
    model_info.set('scaling_rule', 'standard')
    model_info.set('vertex_style', 'direct')
    magnification = str(round(settings['imd_magnification'], 6))
    model_info.set('magnify', magnification)
    model_info.set('tool_start_frame', '1')
    model_info.set('tex_matrix_mode', 'maya')
    model_info.set('compress_node', settings['imd_compress_nodes'])
    nodes_len = str(len(model.nodes))
    model_info.set('node_size', nodes_len + ' ' + nodes_len)
    model_info.set('compress_material', 'off')
    material_len = str(len(model.materials))
    model_info.set('material_size', material_len + ' ' + material_len)
    model_info.set('output_texture', 'used')
    model_info.set('force_full_weight', 'on')
    strip = 'on' if settings['imd_use_primitive_strip'] else 'off'
    model_info.set('use_primitive_strip', strip)


def generate_box_test(imd, model):
    # Set Pos Scale
    pos_scale = model.box_test.pos_scale
    box_test = ET.SubElement(imd, 'box_test')
    box_test.set('pos_scale', str(pos_scale))
    # Set Position
    xyz = model.box_test.xyz
    scaled_xyz = (VecFx32().from_vector(xyz) >> pos_scale).to_vector()
    floats = [str(v) for v in scaled_xyz]
    box_test.set('xyz', ' '.join(floats))
    # Set Dimensions
    whd = model.box_test.whd
    scaled_whd = (VecFx32().from_vector(whd) >> pos_scale).to_vector()
    floats = [str(v) for v in scaled_whd]
    box_test.set('whd', ' '.join(floats))


def generate_textures(imd, model):
    if len(model.textures) == 0:
        return
    tex_image_array = ET.SubElement(imd, 'tex_image_array')
    tex_image_array.set('size', str(len(model.textures)))
    for tex in model.textures:
        tex_image = ET.SubElement(tex_image_array, 'tex_image')
        tex_image.set('index', str(tex.index))
        tex_image.set('name', tex.name)
        tex_image.set('width', str(tex.width))
        tex_image.set('height', str(tex.height))
        tex_image.set('original_width', str(tex.original_width))
        tex_image.set('original_height', str(tex.original_height))
        tex_image.set('format', tex.format)
        if hasattr(tex, 'color0_mode'):
            tex_image.set('color0_mode', tex.color0_mode)
        if hasattr(tex, 'palette_name'):
            tex_image.set('palette_name', tex.palette_name)
        tex_image.set('path', tex.path)
        bitmap = ET.SubElement(tex_image, 'bitmap')
        bitmap.set('size', str(tex.bitmap_size))
        bitmap.text = tex.bitmap_data
        if tex.format == 'tex4x4':
            tex4x4_palette_idx = ET.SubElement(tex_image, 'tex4x4_palette_idx')
            tex4x4_palette_idx.set('size', str(tex.tex4x4_palette_idx_size))
            tex4x4_palette_idx.text = tex.tex4x4_palette_idx_data


def generate_palettes(imd, model):
    if len(model.palettes) == 0:
        return
    tex_palette_array = ET.SubElement(imd, 'tex_palette_array')
    tex_palette_array.set('size', str(len(model.palettes)))
    for pal in model.palettes:
        tex_palette = ET.SubElement(tex_palette_array, 'tex_palette')
        tex_palette.set('index', str(pal.index))
        tex_palette.set('name', pal.name)
        tex_palette.set('color_size', str(pal.size))
        tex_palette.text = pal.data


def generate_materials(imd, model):
    material_array = ET.SubElement(imd, 'material_array')
    material_array.set('size', str(len(model.materials)))
    for mat in model.materials:
        material = ET.SubElement(material_array, 'material')
        material.set('index', str(mat.index))
        material.set('name', mat.name)
        material.set('light0', mat.light0)
        material.set('light1', mat.light1)
        material.set('light2', mat.light2)
        material.set('light3', mat.light3)
        material.set('face', mat.face)
        material.set('alpha', str(mat.alpha))
        material.set('wire_mode', mat.wire_mode)
        material.set('polygon_mode', mat.polygon_mode)
        material.set('polygon_id', str(mat.polygon_id))
        material.set('fog_flag', mat.fog_flag)
        material.set('depth_test_decal', mat.depth_test_decal)
        material.set('translucent_update_depth', mat.translucent_update_depth)
        material.set('render_1_pixel', mat.render_1_pixel)
        material.set('far_clipping', mat.far_clipping)
        material.set('diffuse', mat.diffuse)
        material.set('ambient', mat.ambient)
        material.set('specular', mat.specular)
        material.set('emission', mat.emission)
        material.set('shininess_table_flag', mat.shininess_table_flag)
        material.set('tex_image_idx', str(mat.image_idx))
        material.set('tex_palette_idx', str(mat.palette_idx))
        # Only output when there is a texture assigned
        if mat.image_idx != -1:
            material.set('tex_tiling',
                         f'{mat.tex_tiling_u} {mat.tex_tiling_v}')
            material.set('tex_scale', mat.tex_scale)
            material.set('tex_rotate', mat.tex_rotate)
            material.set('tex_translate', mat.tex_translate)
            material.set('tex_gen_mode', mat.tex_gen_mode)
            if mat.tex_gen_mode == 'nrm' or mat.tex_gen_mode == 'pos':
                material.set('tex_gen_st_src', mat.tex_gen_st_src)
                material.set('tex_effect_mtx', mat.tex_effect_mtx)


def generate_matrices(imd, model):
    matrix_array = ET.SubElement(imd, 'matrix_array')
    matrix_array.set('size', str(len(model.matrices)))
    for matrix in model.matrices:
        matrix_t = ET.SubElement(matrix_array, 'matrix')
        matrix_t.set('index', str(matrix.index))
        matrix_t.set('mtx_weight', str(matrix.weight))
        matrix_t.set('node_idx', str(matrix.node_idx))


def generate_polygons(imd, model):
    polygons = ET.SubElement(imd, 'polygon_array')
    polygons.set('size', str(len(model.polygons)))
    for polygon in model.polygons:
        polygon_t = ET.SubElement(polygons, 'polygon')
        polygon_t.set('index', str(polygon.index))
        polygon_t.set('name', polygon.name)
        polygon_t.set('mtx_prim_size', str(len(polygon.mtx_prims)))
        polygon_t.set('nrm_flag', 'on' if polygon.use_nrm else 'off')
        polygon_t.set('clr_flag', 'on' if polygon.use_clr else 'off')
        polygon_t.set('tex_flag', 'on' if polygon.use_tex else 'off')
        polygon_t.set('vertex_size', str(polygon.vertex_size))
        polygon_t.set('polygon_size', str(polygon.polygon_size))
        polygon_t.set('triangle_size', str(polygon.triangle_size))
        polygon_t.set('quad_size', str(polygon.quad_size))

        for mtx_prim in polygon.mtx_prims:
            mtx_prim_t = ET.SubElement(polygon_t, 'mtx_prim')
            mtx_prim_t.set('index', str(mtx_prim.index))

            mtx_list_t = ET.SubElement(mtx_prim_t, 'mtx_list')
            mtx_list_t.set('size', str(len(mtx_prim.mtx_list)))
            mtx_list_t.text = ' '.join([str(x) for x in mtx_prim.mtx_list])

            primitive_array = ET.SubElement(mtx_prim_t, 'primitive_array')
            primitive_array.set('size', str(len(mtx_prim.primitives)))

            for index, primitive in enumerate(mtx_prim.primitives):
                primitive_t = ET.SubElement(primitive_array, 'primitive')
                primitive_t.set('index', str(index))
                primitive_t.set('type', primitive.type)
                primitive_t.set('vertex_size', str(primitive.vertex_size))
                for cmd in primitive.commands:
                    command = ET.SubElement(primitive_t, cmd.type)
                    command.set(cmd.tag, cmd.data)


def generate_nodes(imd, model: NitroModel):
    node_array = ET.SubElement(imd, 'node_array')
    node_array.set('size', str(len(model.nodes)))

    for node in model.nodes:
        node_t = ET.SubElement(node_array, 'node')
        node_t.set('index', str(node.index))
        node_t.set('name', node.name)
        node_t.set('kind', str(node.kind))
        node_t.set('parent', str(node.parent))
        node_t.set('child', str(node.child))
        node_t.set('brother_next', str(node.brother_next))
        node_t.set('brother_prev', str(node.brother_prev))
        node_t.set('draw_mtx', 'on' if node.draw_mtx else 'off')
        node_t.set('billboard', node.billboard)
        scale = ' '.join([str(round(x, 6)) for x in node.scale])
        node_t.set('scale', scale)
        rotate = ' '.join([str(round(x, 6)) for x in node.rotate])
        node_t.set('rotate', rotate)
        translate = ' '.join([str(round(x, 6)) for x in node.translate])
        node_t.set('translate', translate)
        node_t.set('visibility',  'on' if node.visibility else 'off')

        node_t.set('display_size', str(len(node.displays)))
        if node.vertex_size:
            node_t.set('vertex_size', str(node.vertex_size))
        if node.polygon_size:
            node_t.set('polygon_size', str(node.polygon_size))
        if node.triangle_size:
            node_t.set('triangle_size', str(node.triangle_size))
        if node.quad_size:
            node_t.set('quad_size', str(node.quad_size))

        for display in node.displays:
            display_t = ET.SubElement(node_t, 'display')
            display_t.set('index', str(display.index))
            display_t.set('material', str(display.material))
            display_t.set('polygon', str(display.polygon))
            display_t.set('priority', '0')


def generate_output_info(imd, model):
    output = model.output_info
    output_info = ET.SubElement(imd, 'output_info')
    output_info.set('vertex_size', str(output.vertex_size))
    output_info.set('polygon_size', str(output.polygon_size))
    output_info.set('triangle_size', str(output.triangle_size))
    output_info.set('quad_size', str(output.quad_size))


def generate_body(imd, model, export_settings):
    global settings
    settings = export_settings

    generate_model_info(imd, model)
    generate_box_test(imd, model)
    generate_textures(imd, model)
    generate_palettes(imd, model)
    generate_materials(imd, model)
    generate_matrices(imd, model)
    generate_polygons(imd, model)
    generate_nodes(imd, model)
    generate_output_info(imd, model)
