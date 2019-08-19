import bpy
import xml.etree.ElementTree as ET


settings = None


def generate_model_info(imd):
    model_info = ET.SubElement(imd, 'model_info')
    model_info.set('pos_scale', '0')
    model_info.set('scaling_rule', 'standard')
    model_info.set('vertex_style', 'direct')
    model_info.set('magnify', '1.000000')
    model_info.set('tool_start_frame', '1')
    model_info.set('tex_matrix_mode', 'maya')
    model_info.set('compress_node', 'unite_combine')
    model_info.set('node_size', '2 1')
    model_info.set('compress_material', 'off')
    model_info.set('material_size', '1 1')
    model_info.set('output_texture', 'used')
    model_info.set('force_full_weight', 'on')
    model_info.set('use_primitive_strip', 'on')


def generate_box_test(imd):
    box_test = ET.SubElement(imd, 'box_test')
    box_test.set('post_scale', '0')
    box_test.set('xyz', '0 0 0')
    box_test.set('whd', '0 0 0')


def generate_materials(imd):
    material_array = ET.SubElement(imd, 'material_array')
    material_array.set('size', str(len(bpy.data.materials)))

    for index, bl_material in enumerate(bpy.data.materials):
        material = ET.SubElement(material_array, 'material')
        material.set('index', str(index))
        material.set('name', bl_material.name)
        material.set('light0', 'off')
        material.set('light1', 'off')
        material.set('light2', 'off')
        material.set('light3', 'off')
        material.set('face', 'front')
        material.set('alpha', '31')
        material.set('wire_mode', 'off')
        material.set('polygon_mode', 'modulate')
        material.set('polygon_id', '0')
        material.set('fog_flag', 'off')
        material.set('depth_test_decal', 'off')
        material.set('translucent_update_depth', 'off')
        material.set('render_1_pixel', 'off')
        material.set('far_clipping', 'off')
        material.set('diffuse', '31 31 31')
        material.set('ambient', '31 31 31')
        material.set('specular', '0 0 0')
        material.set('emission', '0 0 0')
        material.set('shininess_table_flag', 'off')
        material.set('tex_image_idx', '0')
        material.set('tex_palette_idx', '0')
        material.set('tex_tiling', 'clamp clamp')
        material.set('tex_scale', '1.000000 1.000000')
        material.set('tex_rotate', '0.000000')
        material.set('tex_translate', '0.000000 0.000000')
        material.set('tex_gen_mode', 'none')


def generate_matrices(imd):
    matrix_array = ET.SubElement(imd, 'matrix_array')
    matrix_array.set('size', '1')

    matrix = ET.SubElement(matrix_array, 'matrix')
    matrix.set('index', '0')
    matrix.set('mtx_weight', '1')
    matrix.set('node_idx', '0')


def get_material_index(obj, index):
    name = obj.material_slots[index].material.name
    return bpy.data.materials.find(name)


class Batch():
    """
    A Batch represents a bunch of triangles with material information
    that gets passed on to the gpu.
    """
    def __init__(self, material_index):
        self.material_index = material_index
        self.primitives = {'triangles': [], 'quads': []}

    def process(self, polygon, obj):
        verts_local = [v.co for v in obj.data.vertices.values()]
        verts_world = [obj.matrix_world @ v_local for v_local in verts_local]
        if len(polygon.vertices) == 3:
            self.primitives['triangles'].append(
                [verts_world[i] for i in polygon.vertices]
            )
        elif len(polygon.vertices) == 4:
            self.primitives['quads'].append(
                [verts_world[i] for i in polygon.vertices]
            )


def get_batches():
    batches = [Batch(i) for i in range(len(bpy.data.materials))]
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for polygon in obj.data.polygons:
            index = get_material_index(obj, polygon.material_index)
            batches[index].process(polygon, obj)
    return batches


def generate_polygons(imd):
    polygons = ET.SubElement(imd, 'polygons')
    batches = get_batches()

    for index, batch in enumerate(batches):
        polygon = ET.SubElement(polygons, 'polygon')
        polygon.set('index', str(index))
        polygon.set('name', f'polygon{index}')

        mtx_prim = ET.SubElement(polygon, 'mtx_prim')
        mtx_prim.set('index', '0')

        mtx_list = ET.SubElement(mtx_prim, 'mtx_list')
        mtx_list.set('size', '1')
        mtx_list.text = '0'

        primitive_array = ET.SubElement(mtx_prim, 'primitive_array')
        primitive_array.set('size', '1')

        primitive = ET.SubElement(primitive_array, 'primitive')
        primitive.set('index', '0')
        primitive.set('type', 'quads')
        primitive.set('vertex_size', '0')

        for quad in batch.primitives['quads']:
            for vector in quad:
                pos_xyz = ET.SubElement(primitive, 'pos_xyz')
                pos_xyz.set('xyz', ' '.join([str(v) for v in vector]))


def generate_body(imd, export_settings):
    settings = export_settings

    generate_model_info(imd)
    generate_box_test(imd)
    generate_materials(imd)
    generate_matrices(imd)
    generate_polygons(imd)
