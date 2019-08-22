import bpy
from mathutils import Vector
import xml.etree.ElementTree as ET
import json


settings = None


"""
Display list collection.

model_data = {
    output: {
        polygon_size: 0,
        triangle_size: 0,
        quad_size: 0,
        vertex_size: 0
    },
    polygons: [
        {
            material: 0,
            primitives: [
                {
                    type: triangles,
                    vertex_size: 0,
                    commands: [
                        {
                            type: "mtx",
                            tag: "idx",
                            data: "0"
                        },
                        {
                            type: "pos_xyz",
                            tag: "xyz",
                            data: "0.141357 0.119873 -0.139404"
                        }
                    ]
                }
            ]
        }
    ]
}
"""
model_data = {}


# FX32 Conversion Functions
def float_to_fx32(value):
    return int(round(value * 4096))


def fx32_to_float(value):
    return float(value) / 4096


# Bound Functions
def get_object_max_min(obj):
    bounds = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return {
        'min': bounds[0],
        'max': bounds[6]
    }


def get_all_max_min():
    min_p = Vector([float("inf"), float("inf"), float("inf")])
    max_p = Vector([-float("inf"), -float("inf"), -float("inf")])
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        max_min = get_object_max_min(obj)
        # Max
        max_p.x = max(max_p.x, max_min["max"].x)
        max_p.y = max(max_p.y, max_min["max"].y)
        max_p.z = max(max_p.z, max_min["max"].z)
        # Min
        min_p.x = min(min_p.x, max_min["min"].x)
        min_p.y = min(min_p.y, max_min["min"].y)
        min_p.z = min(min_p.z, max_min["min"].z)
    return {
        'min': min_p,
        'max': max_p
    }


# Pos Scale Functions
def calculate_pos_scale(max_coord):
    m = float_to_fx32(max_coord)
    pos_scale = 0
    while m >= 0x8000:
        pos_scale += 1
        m >>= 1
    return pos_scale


def get_pos_scale():
    max_min = get_all_max_min()
    max_max = abs(max(max_min["max"].x, max_min["max"].y, max_min["max"].z))
    min_min = abs(min(max_min["min"].x, max_min["min"].y, max_min["min"].z))
    max_coord = max(max_max, min_min)
    return calculate_pos_scale(max_coord)


def get_material_index(obj, index):
    name = obj.material_slots[index].material.name
    return bpy.data.materials.find(name)


def get_primitive(primitives, tp):
    for primitive in primitives:
        if primitive['type'] == tp:
            return primitive
    primitives.append(
        {
            'type': tp,
            'vertex_size': 0,
            'commands': []
        }
    )
    return primitives[-1]


def polygon_to_primitive(dl, obj, polygon):
    verts_local = [v.co for v in obj.data.vertices.values()]
    verts_world = [obj.matrix_world @ v_local for v_local in verts_local]

    if len(polygon.vertices) == 3:
        primitive = get_primitive(dl['primitives'], 'triangles')
        primitive['vertex_size'] += 3
        model_data['output']['vertex_size'] += 3
        model_data['output']['triangle_size'] += 1
    elif len(polygon.vertices) == 4:
        primitive = get_primitive(dl['primitives'], 'quads')
        primitive['vertex_size'] += 4
        model_data['output']['vertex_size'] += 4
        model_data['output']['quad_size'] += 1

    for i in polygon.vertices:
        primitive['commands'].append(
            {
                'type': 'pos_xyz',
                'tag': 'xyz',
                'data': ' '.join([str(v) for v in verts_world[i]])
            }
        )


def prepare_model_data():
    global model_data
    model_data = {
        'output': {
            'polygon_size': len(bpy.data.materials),
            'triangle_size': 0,
            'quad_size': 0,
            'vertex_size': 0
        },
        'polygons': []
    }

    for i in range(len(bpy.data.materials)):
        model_data['polygons'].append({'material': i, 'primitives': []})

    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for polygon in obj.data.polygons:
            index = get_material_index(obj, polygon.material_index)
            dl = model_data['polygons'][index]
            polygon_to_primitive(dl, obj, polygon)

    with open(settings['filepath'] + '.json', 'w') as f:
        f.write(json.dumps(model_data, indent=4))


def generate_model_info(imd):
    model_info = ET.SubElement(imd, 'model_info')
    model_info.set('pos_scale', str(get_pos_scale()))
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
    box_test.set('pos_scale', '0')
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


def generate_polygons(imd):
    polygons = ET.SubElement(imd, 'polygons')

    for index, dl in enumerate(model_data['polygons']):
        polygon = ET.SubElement(polygons, 'polygon')
        polygon.set('index', str(index))
        polygon.set('name', f'polygon{index}')

        mtx_prim = ET.SubElement(polygon, 'mtx_prim')
        mtx_prim.set('index', '0')

        mtx_list = ET.SubElement(mtx_prim, 'mtx_list')
        mtx_list.set('size', '1')
        mtx_list.text = '0'

        primitive_array = ET.SubElement(mtx_prim, 'primitive_array')
        primitive_array.set('size', str(len(dl['primitives'])))

        for pr in dl['primitives']:
            primitive = ET.SubElement(primitive_array, 'primitive')
            primitive.set('index', '0')
            primitive.set('type', pr['type'])
            primitive.set('vertex_size', str(pr['vertex_size']))
            for cmd in pr['commands']:
                command = ET.SubElement(primitive, cmd['type'])
                command.set(cmd['tag'], cmd['data'])


def generate_output_info(imd):
    output = model_data['output']
    output_info = ET.SubElement(imd, 'output_info')
    output_info.set('vertex_size', str(output['vertex_size']))
    output_info.set('polygon_size', str(output['polygon_size']))
    output_info.set('triangle_size', str(output['triangle_size']))
    output_info.set('quad_size', str(output['quad_size']))


def generate_body(imd, export_settings):
    global settings
    settings = export_settings

    prepare_model_data()

    generate_model_info(imd)
    generate_box_test(imd)
    generate_materials(imd)
    generate_matrices(imd)
    generate_polygons(imd)
    generate_output_info(imd)
