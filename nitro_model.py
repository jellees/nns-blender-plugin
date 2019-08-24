import bpy
from mathutils import Vector


output_info = None


boundry_box = None


# FX32 Conversion Functions
def float_to_fx32(value):
    return int(round(value * 4096))


def fx32_to_float(value):
    return float(value) / 4096


def vector_to_vecfx32(vec):
    return [
        float_to_fx32(vec.x),
        float_to_fx32(vec.y),
        float_to_fx32(vec.z)
    ]


def vecfx32_to_vector(values):
    return Vector([
        fx32_to_float(values[0]),
        fx32_to_float(values[1]),
        fx32_to_float(values[2]),
    ])


def calculate_diff(vec1, vec2):
    return [
        vec1[0] - vec2[0],
        vec1[1] - vec2[1],
        vec1[2] - vec2[2],
    ]


def apply_pos_scale_on_vector(vec, pos_scale):
    return Vector([
        fx32_to_float(float_to_fx32(vec.x) >> pos_scale),
        fx32_to_float(float_to_fx32(vec.y) >> pos_scale),
        fx32_to_float(float_to_fx32(vec.z) >> pos_scale),
    ])


def apply_pos_scale_on_vecfx32(vecfx32, pos_scale):
    return [
        vecfx32[0] >> pos_scale,
        vecfx32[1] >> pos_scale,
        vecfx32[2] >> pos_scale
    ]


# Vertex command check functions
def is_pos_s(vecfx32):
    return (
        (vecfx32[0] & 0x3F) == 0 and
        (vecfx32[1] & 0x3F) == 0 and
        (vecfx32[2] & 0x3F) == 0
    )


def is_pos_diff(diff):
    # 512 is 0.125 in FX32
    return (
        abs(diff[0]) < 512 and
        abs(diff[1]) < 512 and
        abs(diff[2]) < 512
    )


def get_material_index(obj, index):
    name = obj.material_slots[index].material.name
    return bpy.data.materials.find(name)


class NitroSceneBoundryBox():
    def __init__(self):
        max_min = self.get_all_max_min()
        self.min = max_min['min']
        self.max = max_min['max']

    def calculate_pos_scale(self, max_coord):
        m = float_to_fx32(max_coord)
        pos_scale = 0
        while m >= 0x8000:
            pos_scale += 1
            m >>= 1
        return pos_scale

    def get_pos_scale(self):
        max_max = abs(max(self.max.x, self.max.y, self.max.z))
        min_min = abs(min(self.min.x, self.min.y, self.min.z))
        max_coord = max(max_max, min_min)
        return self.calculate_pos_scale(max_coord)

    def get_box_test(self):
        return {
            'xyz': self.min,
            'whd': self.max - self.min
        }

    def get_box_test_pos_scale(self):
        box = self.get_box_test()
        max_whd = abs(max(box['whd'].x, box['whd'].y, box['whd'].z))
        min_xyz = abs(min(box['xyz'].x, box['xyz'].y, box['xyz'].z))
        max_coord = max(max_whd, min_xyz)
        return self.calculate_pos_scale(max_coord)

    def get_object_max_min(self, obj):
        bounds = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
        return {
            'min': bounds[0],
            'max': bounds[6]
        }

    def get_all_max_min(self):
        min_p = Vector([float('inf'), float('inf'), float('inf')])
        max_p = Vector([-float('inf'), -float('inf'), -float('inf')])
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            max_min = self.get_object_max_min(obj)
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
        self.commands = []

    def add_command(self, type_: str, tag: str, data: str):
        self.commands.append(NitroCommand(type_, tag, data))

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
    def __init__(self, material):
        self.material = material
        self.primitives = []
        self._previous_vecfx32 = []

    def is_empty(self):
        if not self.primitives:
            return True
        if not self.primitives[0].commands:
            return True
        return False

    def add_to_primitive(self, obj, polygon):
        verts_local = [v.co for v in obj.data.vertices.values()]
        verts_world = [obj.matrix_world @ v_local for v_local in verts_local]
        if len(polygon.vertices) == 3:
            primitive = self.get_primitive('triangles')
            output_info.vertex_size += 3
            output_info.triangle_size += 1
        elif len(polygon.vertices) == 4:
            primitive = self.get_primitive('quads')
            output_info.vertex_size += 4
            output_info.quad_size += 1

        for i in polygon.vertices:
            pos_scale = boundry_box.get_pos_scale()

            # Get vertex and convert it to VecFx32
            vertex = verts_world[i]
            vecfx32 = vector_to_vecfx32(Vector(vertex))

            # Apply pos_scale
            scaled_vecfx32 = apply_pos_scale_on_vecfx32(vecfx32, pos_scale)
            scaled_vec = vecfx32_to_vector(scaled_vecfx32)

            # Calculate difference from previous vertex
            if not self.is_empty():
                diff_vecfx32 = calculate_diff(
                    scaled_vecfx32,
                    self._previous_vecfx32)
                diff_vec = vecfx32_to_vector(diff_vecfx32)

            # PosYZ
            if not self.is_empty() and diff_vecfx32[0] == 0:
                primitive.add_pos_yz(scaled_vec)
            # PosXZ
            elif not self.is_empty() and diff_vecfx32[1] == 0:
                primitive.add_pos_xz(scaled_vec)
            # PosXY
            elif not self.is_empty() and diff_vecfx32[2] == 0:
                primitive.add_pos_xy(scaled_vec)
            # PosDiff
            elif not self.is_empty() and is_pos_diff(diff_vecfx32):
                primitive.add_pos_xz(diff_vec)
            # PosShort
            elif is_pos_s(scaled_vecfx32):
                primitive.add_pos_s(scaled_vec)
            # PosXYZ
            else:
                primitive.add_pos_xyz(scaled_vec)

            self._previous_vecfx32 = scaled_vecfx32

    def get_primitive(self, type_):
        for primitive in self.primitives:
            if primitive.type == type_:
                return primitive
        self.primitives.append(NitroPrimitive(type_))
        return self.primitives[-1]


class NitroModel():
    def __init__(self):
        self.output_info = None
        self.boundry_box = None
        self.polygons = []
        self.init_polygons()

    def init_polygons(self):
        for i in range(len(bpy.data.materials)):
            self.polygons.append(NitroPolygon(i))
        for obj in bpy.data.objects:
            if obj.type != 'MESH':
                continue
            for polygon in obj.data.polygons:
                index = get_material_index(obj, polygon.material_index)
                self.polygons[index].add_to_primitive(obj, polygon)


def get_nitro_model():
    global output_info
    global boundry_box
    output_info = NitroOuputInfo()
    boundry_box = NitroSceneBoundryBox()
    nitro_model = NitroModel()
    nitro_model.output_info = output_info
    nitro_model.boundry_box = boundry_box
    return nitro_model
