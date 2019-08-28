import bpy
from mathutils import Vector, Matrix
from bpy_extras.io_utils import axis_conversion
from .util import VecFx32, float_to_fx32
from . import local_logger as logger


model = None


settings = {}


global_matrix = None


def get_global_mat_index(obj, index):
    if len(obj.material_slots) <= index:
        # If an object doesn't have (enough) material slots, the polgyon
        # with the requested index shouldn't be converted.
        return -1
    name = obj.material_slots[index].material.name
    return bpy.data.materials.find(name)


# Vertex command check functions
def is_pos_s(vecfx32):
    return (
        (vecfx32.x & 0x3F) == 0 and
        (vecfx32.y & 0x3F) == 0 and
        (vecfx32.z & 0x3F) == 0
    )


def is_pos_diff(diff):
    # 512 is 0.125 in FX32
    return (
        abs(diff.x) < 512 and
        abs(diff.y) < 512 and
        abs(diff.z) < 512
    )


def calculate_pos_scale(max_coord):
    m = float_to_fx32(max_coord)
    pos_scale = 0
    while m >= 0x8000:
        pos_scale += 1
        m >>= 1
    return pos_scale


def get_object_max_min(obj):
        matrix = global_matrix @ obj.matrix_world
        bounds = [matrix @ Vector(v) for v in obj.bound_box]
        return {
            'min': bounds[0],
            'max': bounds[6]
        }


def get_all_max_min():
    min_p = Vector([float('inf'), float('inf'), float('inf')])
    max_p = Vector([-float('inf'), -float('inf'), -float('inf')])
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        max_min = get_object_max_min(obj)
        # Max
        max_p.x = max(max_p.x, max_min['max'].x)
        max_p.y = max(max_p.y, max_min['max'].y)
        max_p.z = max(max_p.z, max_min['max'].z)
        # Min
        min_p.x = min(min_p.x, max_min['min'].x)
        min_p.y = min(min_p.y, max_min['min'].y)
        min_p.z = min(min_p.z, max_min['min'].z)
    return {
        'min': min_p,
        'max': max_p
    }


class NitroModelInfo():
    def __init__(self):
        box = get_all_max_min()
        max_max = abs(max(box['max'].x, box['max'].y, box['max'].z))
        min_min = abs(min(box['min'].x, box['min'].y, box['min'].z))
        max_coord = max(max_max, min_min)
        self.pos_scale = calculate_pos_scale(max_coord)


class NitroBoxTest():
    def __init__(self):
        box = get_all_max_min()
        self.xyz = box['min']
        self.whd = box['max'] - box['min']

        max_whd = abs(max(self.whd.x, self.whd.y, self.whd.z))
        min_xyz = abs(min(self.xyz.x, self.xyz.y, self.xyz.z))
        max_coord = max(max_whd, min_xyz)
        self.pos_scale = calculate_pos_scale(max_coord)


class NitroMaterial():
    def __init__(self, blender_index, index):
        self.blender_index = blender_index
        self.index = index
        blender_material = bpy.data.materials[blender_index]
        self.name = blender_material.name


class NitroOuputInfo():
    def __init__(self):
        self.polygon_size = 0
        self.triangle_size = 0
        self.quad_size = 0
        self.vertex_size = 0


class NitroCommand():
    def __init__(self, type_, tag, data):
        self.type = type_
        self.tag = tag
        self.data = data


class NitroPrimitive():
    def __init__(self, type_):
        self.type = type_
        self.vertex_size = 0
        self.triangle_size = 0
        self.quad_size = 0
        self.commands = []
        self._previous_vecfx32 = None
        # for after sort
        # quad_strip=0 triangle_strip=1 quads=2 triangles=3
        self.sort_key = 0

    def is_empty(self):
        return self._previous_vecfx32 is None

    def add_command(self, type_: str, tag: str, data: str):
        self.commands.append(NitroCommand(type_, tag, data))

    def insert_mtx(self, position, idx: int):
        self.commands.insert(position, NitroCommand('mtx', 'idx', str(idx)))

    def add_mtx(self, idx: int):
        self.add_command('mtx', 'idx', str(idx))

    def add_pos_xyz(self, vec: Vector):
        floats = [str(v) for v in vec]
        self.add_command('pos_xyz', 'xyz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_s(self, vec: Vector):
        floats = [str(v) for v in vec]
        self.add_command('pos_s', 'xyz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_diff(self, vec: Vector):
        floats = [str(v) for v in vec]
        self.add_command('pos_diff', 'xyz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_yz(self, vec: Vector):
        floats = [str(v) for v in [vec.y, vec.z]]
        self.add_command('pos_yz', 'yz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_xz(self, vec: Vector):
        floats = [str(v) for v in [vec.x, vec.z]]
        self.add_command('pos_xz', 'xz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_xy(self, vec: Vector):
        floats = [str(v) for v in [vec.x, vec.y]]
        self.add_command('pos_xy', 'xy', ' '.join(floats))
        self.vertex_size += 1


class NitroPolygon():
    def __init__(self, index, material):
        self.index = index
        self.material_index = material
        self.primitives = []
        self.use_colors = 'off'

    def is_empty(self):
        if not self.primitives:
            return True
        if not self.primitives[0].commands:
            return True
        return False

    def add_to_primitive(self, obj, polygon):
        verts_local = [v.co for v in obj.data.vertices.values()]
        matrix = global_matrix @ obj.matrix_world
        verts_world = [matrix @ v_local for v_local in verts_local]

        if len(polygon.loop_indices) == 3:
            primitive = self.get_primitive('triangles')
            primitive.sort_key = 3
            model.output_info.vertex_size += 3
            model.output_info.triangle_size += 1
            model.output_info.polygon_size += 1
            primitive.triangle_size += 1
        elif len(polygon.loop_indices) == 4:
            primitive = self.get_primitive('quads')
            primitive.sort_key = 2
            model.output_info.vertex_size += 4
            model.output_info.quad_size += 1
            model.output_info.polygon_size += 1
            primitive.quad_size += 1
        else:
            logger.log('ngon, skipped.')
            return

        logger.log(
            f'Add mesh to polygon {self.index} '
            f'vertices size: {len(polygon.loop_indices)} '
            f'material BL index {polygon.material_index}'
        )

        if len(obj.data.vertex_colors) > 0:
            self.use_colors = 'on'

        for idx in polygon.loop_indices:
            pos_scale = model.model_info.pos_scale

            # Get vertex and convert it to VecFx32.
            vertex_index = obj.data.loops[idx].vertex_index
            vecfx32 = VecFx32().from_floats(verts_world[vertex_index])

            # Apply pos_scale.
            scaled_vecfx32 = vecfx32 >> pos_scale
            scaled_vec = scaled_vecfx32.to_vector()

            # Calculate difference from previous vertex.
            if not primitive.is_empty():
                diff_vecfx32 = scaled_vecfx32 - primitive._previous_vecfx32
                diff_vec = diff_vecfx32.to_vector()

            # Color
            if self.use_colors == 'on':
                color = obj.data.vertex_colors[0].data[idx].color
                r = int(color[0] * 31)
                g = int(color[1] * 31)
                b = int(color[2] * 31)
                primitive.add_command('clr', 'rgb', f'{r} {g} {b}')

            # PosYZ
            if not primitive.is_empty() and diff_vecfx32.x == 0:
                primitive.add_pos_yz(scaled_vec)
            # PosXZ
            elif not primitive.is_empty() and diff_vecfx32.y == 0:
                primitive.add_pos_xz(scaled_vec)
            # PosXY
            elif not primitive.is_empty() and diff_vecfx32.z == 0:
                primitive.add_pos_xy(scaled_vec)
            # PosDiff
            elif not primitive.is_empty() and is_pos_diff(diff_vecfx32):
                primitive.add_pos_diff(diff_vec)
            # PosShort
            elif is_pos_s(scaled_vecfx32):
                primitive.add_pos_s(scaled_vec)
            # PosXYZ
            else:
                primitive.add_pos_xyz(scaled_vec)

            primitive._previous_vecfx32 = scaled_vecfx32

    def get_primitive(self, type_):
        for primitive in self.primitives:
            if primitive.type == type_:
                return primitive
        self.primitives.append(NitroPrimitive(type_))
        return self.primitives[-1]

    def set_initial_mtx(self):
        self.primitives[0].insert_mtx(0, 0)


class NitroModel():
    def __init__(self):
        self.output_info = NitroOuputInfo()
        self.model_info = NitroModelInfo()
        self.box_test = NitroBoxTest()
        self.materials = []
        self.polygons = []

    def collect(self):
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            logger.log('Object: ' + obj.name)
            for polygon in obj.data.polygons:
                index = get_global_mat_index(obj, polygon.material_index)
                if index == -1:
                    logger.log("Polygon doesn't have material. Skipped.")
                    continue
                material = self.find_material(index)
                pol = self.find_polgyon(material.index)
                pol.add_to_primitive(obj, polygon)

        for polygon in self.polygons:
            polygon.primitives.sort(key=lambda x: x.sort_key)
            polygon.set_initial_mtx()

    def find_polgyon(self, material_index):
        for polygon in self.polygons:
            if polygon.material_index == material_index:
                return polygon
        self.polygons.append(NitroPolygon(len(self.polygons), material_index))
        return self.polygons[-1]

    def find_material(self, blender_index):
        for material in self.materials:
            if material.blender_index == blender_index:
                return material
        index = len(self.materials)
        self.materials.append(NitroMaterial(blender_index, index))
        return self.materials[-1]


def get_nitro_model(export_settings):
    global model, settings, global_matrix

    settings = export_settings

    global_matrix = (
        Matrix.Scale(settings['magnification'], 4) @ axis_conversion(
            to_forward='-Z',
            to_up='Y',
        ).to_4x4())

    model = NitroModel()
    model.collect()

    return model
