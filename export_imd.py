import bpy
import xml.etree.ElementTree as ET


def generate_materials(imd):

    material_array = ET.SubElement(imd, 'material_array')
    material_array.set('size', str(len(bpy.data.materials)))

    for index, bl_material in enumerate(bpy.data.materials):
        material = ET.SubElement(material_array, 'material')
        material.set('index', str(index))


def get_material_index(obj, index):

    name = obj.material_slots[index].material.name
    return bpy.data.materials.find(name)


class Batch():
    """ 
    A Batch represents a bunch of triangles with material 
    information that gets passed on to the gpu. 
    """

    def __init__(self, material_index):
        
        self.material_index = material_index
        self.primitives = {'triangles': [], 'quads': []}

    def process(self, polygon, obj):

        verts_local = [v.co for v in obj.data.vertices.values()]
        verts_world = [obj.matrix_world @ v_local for v_local in verts_local]

        if len(polygon.vertices) == 3:
            self.primitives['triangles'].append([verts_world[i] for i in polygon.vertices])
        elif len(polygon.vertices) == 4:
            self.primitives['quads'].append([verts_world[i] for i in polygon.vertices])


def generate_batches():

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
    batches = generate_batches()

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


def generate_body(imd):

    generate_materials(imd)
    generate_polygons(imd)
