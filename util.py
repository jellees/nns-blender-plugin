import bpy
from mathutils import Vector


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
    matrix = obj.matrix_world
    bounds = [matrix @ Vector(v) for v in obj.bound_box]
    return {
        'min': bounds[0],
        'max': bounds[6]
    }


def get_all_max_min():
    min_p = Vector([float('inf'), float('inf'), float('inf')])
    max_p = Vector([-float('inf'), -float('inf'), -float('inf')])
    for obj in bpy.context.view_layer.objects:
        if obj.type != 'MESH':
            continue
        max_min = get_object_max_min(obj)
        # Max
        max_p.x = max(max_p.x, max_min['max'].x)
        max_p.x = max(max_p.x, max_min['min'].x)
        max_p.y = max(max_p.y, max_min['max'].y)
        max_p.y = max(max_p.y, max_min['min'].y)
        max_p.z = max(max_p.z, max_min['max'].z)
        max_p.z = max(max_p.z, max_min['min'].z)
        # Min
        min_p.x = min(min_p.x, max_min['min'].x)
        min_p.x = min(min_p.x, max_min['max'].x)
        min_p.y = min(min_p.y, max_min['min'].y)
        min_p.y = min(min_p.y, max_min['max'].y)
        min_p.z = min(min_p.z, max_min['min'].z)
        min_p.z = min(min_p.z, max_min['max'].z)

    return {
        'min': min_p,
        'max': max_p
    }


def get_global_mat_index(obj, index):
    if len(obj.material_slots) <= index:
        # If an object doesn't have (enough) material slots, the polygon
        # with the requested index shouldn't be converted.
        return -1
    if obj.material_slots[index].material is None:
        # Material doesn't have any material in the slot.
        return -1
    name = obj.material_slots[index].material.name
    return bpy.data.materials.find(name)


def lin2s(x):
    """
    Le color correction function. From some guy on blender stackexchange.
    http://entropymine.com/imageworsener/srgbformula/
    """
    if x <= 0.0031308:
        y = x * 12.92
    elif 0.0031308 < x <= 1:
        y = 1.055 * x ** (1 / 2.4) - 0.055
    return y


def float_to_fx32(value):
    return int(round(value * 4096))


def fx32_to_float(value):
    return float(value) / 4096


def float_to_fx10(value):
    return max(min(int(round(value * 512)), 511), -512)


def fx10_to_float(value):
    return float(value) / 512


def vector_to_vecfx10(vector):
    return Vecfx10([
        float_to_fx10(vector.x),
        float_to_fx10(vector.y),
        float_to_fx10(vector.z),
    ])


class Vecfx10():
    def __init__(self, vector=[0, 0, 0]):
        self.x = vector[0]
        self.y = vector[1]
        self.z = vector[2]

    def to_vector(self):
        return Vector([
            fx10_to_float(self.x),
            fx10_to_float(self.y),
            fx10_to_float(self.z),
        ])

    def __eq__(self, other):
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )


class VecFx32(object):
    def __init__(self, vector=[0, 0, 0]):
        self.x = vector[0]
        self.y = vector[1]
        self.z = vector[2]

    def from_floats(self, floats):
        return VecFx32([
            float_to_fx32(floats[0]),
            float_to_fx32(floats[1]),
            float_to_fx32(floats[2])
        ])

    def from_vector(self, vector):
        return VecFx32([
            float_to_fx32(vector.x),
            float_to_fx32(vector.y),
            float_to_fx32(vector.z)
        ])

    def to_vector(self):
        return Vector([
            fx32_to_float(self.x),
            fx32_to_float(self.y),
            fx32_to_float(self.z),
        ])

    def __str__(self):
        return str(self.x), str(self.y), str(self.z)

    def __sub__(self, other):
        if isinstance(other, self.__class__):
            return VecFx32([
                self.x - other.x,
                self.y - other.y,
                self.z - other.z
            ])
        elif isinstance(other, int):
            return VecFx32([
                self.x - other,
                self.y - other,
                self.z - other
            ])
        else:
            raise TypeError(
                "unsupported operand type(s) for -: '{}' and '{}'"
            ).format(self.__class__, type(other))

    def __rshift__(self, other):
        if isinstance(other, self.__class__):
            return VecFx32([
                self.x >> other.x,
                self.y >> other.y,
                self.z >> other.z
            ])
        elif isinstance(other, int):
            return VecFx32([
                self.x >> other,
                self.y >> other,
                self.z >> other
            ])
        else:
            raise TypeError(
                "unsupported operand type(s) for >>: '{}' and '{}'"
            ).format(self.__class__, type(other))

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.x < other.x and
                self.y < other.y and
                self.z < other.z
            )
        elif isinstance(other, int):
            return (
                self.x < other and
                self.y < other and
                self.z < other
            )
        else:
            raise TypeError(
                "unsupported operand type(s) for <: '{}' and '{}'"
            ).format(self.__class__, type(other))

    def __eq__(self, other):
        if other is None:
            return False
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )