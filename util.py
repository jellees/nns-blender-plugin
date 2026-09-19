import bpy
import os
import contextlib
from mathutils import Vector


# Blender's context.mode strings (e.g. 'EDIT_MESH', 'PAINT_VERTEX') don't match what bpy.ops.object.mode_set(mode=...) expects (e.g. 'EDIT', 'VERTEX_PAINT'). this maps the ones that matter for restoring the user's mode after force_object_mode() is done.
_RESTORE_MODE = {
    'EDIT_MESH': 'EDIT',
    'EDIT_CURVE': 'EDIT',
    'EDIT_SURFACE': 'EDIT',
    'EDIT_TEXT': 'EDIT',
    'EDIT_ARMATURE': 'EDIT',
    'EDIT_METABALL': 'EDIT',
    'EDIT_LATTICE': 'EDIT',
    'EDIT_CURVES': 'EDIT',
    'EDIT_POINTCLOUD': 'EDIT',
    'EDIT_GREASE_PENCIL': 'EDIT',
    'POSE': 'POSE',
    'SCULPT': 'SCULPT',
    'SCULPT_CURVES': 'SCULPT_CURVES',
    'PAINT_WEIGHT': 'WEIGHT_PAINT',
    'PAINT_VERTEX': 'VERTEX_PAINT',
    'PAINT_TEXTURE': 'TEXTURE_PAINT',
    'PAINT_GPENCIL': 'PAINT_GPENCIL',
    'PARTICLE_EDIT': 'PARTICLE_EDIT',
}


@contextlib.contextmanager
def force_object_mode(context):
    """Temporarily forces Object Mode for the duration of the with
    block, then restores whatever mode was active before.

    Blender doesn't write Edit Mode changes (vertex colors, UVs, custom
    normals, edited bones, mesh topology, ...) back to the underlying
    obj.data until the object actually leaves Edit Mode. Anything that
    reads or writes obj.data directly, exporting, or the UV/position
    bounds check and fix tools, gets stale or inconsistent data if it
    runs while still in Edit Mode. This is the same fix originally
    written for ExportNitro.execute(), pulled out here so every operator
    that touches obj.data directly can share it instead of each having
    its own copy of the same mode-juggling logic.
    """
    original_mode = context.mode
    original_active = context.view_layer.objects.active
    switched = False

    if original_mode != 'OBJECT' and bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')
        switched = True

    try:
        yield
    finally:
        if switched:
            context.view_layer.objects.active = original_active
            target_mode = _RESTORE_MODE.get(original_mode)
            if target_mode and bpy.ops.object.mode_set.poll():
                try:
                    bpy.ops.object.mode_set(mode=target_mode)
                except RuntimeError:
                    # Restoring the mode is a nicety, not worth failing the whole operation over if it doesn't succeed for some reason.
                    pass


def safe_register_class(cls):
    """Registers a class with Blender, recovering on its own if the
    class is already registered.

    If any register() call in this plugin ever raises partway through
    (a bug, or Blender itself rejecting something), whatever classes it
    already got through stay registered in Blender's internal registry
    disabling the plugin or even it just failing to fully enable
    doesn't automatically clean those up, only a full Blender restart
    does. The next attempt to enable the addon then dies immediately on
    "already registered" for the first of those classes, which is a
    confusing error that has nothing to do with whatever the original
    problem was. Recovering here (unregister the stale entry, then
    register fresh) means a retry can actually get far enough to hit
    the real error instead of masking it with this one.
    """
    try:
        bpy.utils.register_class(cls)
    except ValueError:
        bpy.utils.unregister_class(cls)
        bpy.utils.register_class(cls)


def get_filepath_and_extension(image):
    filepath = image.filepath
    path = os.path.realpath(bpy.path.abspath(filepath))
    _, extension = os.path.splitext(path)
    return path, extension

def get_color_from_obj(obj, idx):
    """
    This function exists because we cannot trust blender to have the vertex colors
    to be aligned with the vertex loops. Possibly this happens when you import a
    wrong model.
    """

    if bpy.app.version >= (3, 2, 0):
        if (len(obj.data.color_attributes.active_color.data) <= idx):
            return(0, 0, 0)
        else:
            entry = obj.data.color_attributes.active_color.data[idx]
            return getattr(entry, 'color_srgb', entry.color)
    else:
        if len(obj.data.vertex_colors[0].data) <= idx:
            return(0, 0, 0)
        else:
            return(obj.data.vertex_colors[0].data[idx].color)


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
    # Values slightly outside [0, 1] can reach here (e.g. from color management, filtering, or float rounding), and the original code had no branch for x < 0 or x > 1, leaving `y` unassigned and raising an UnboundLocalError instead of just producing a valid color. Clamp first so every input has a defined, in-range output.
    x = min(max(x, 0.0), 1.0)
    if x <= 0.0031308:
        y = x * 12.92
    else:
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
        if other is None:
            return False
        return (
            self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )

    def __hash__(self):
        # Defining __eq__ makes Python 3 drop the default identity-based __hash__, silently making instances unusable as dict keys / set members (e.g. in a vertex-adjacency cache). Restore it explicitly.
        return hash((self.x, self.y, self.z))


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

    def __hash__(self):
        # Defining __eq__ makes Python 3 drop the default identity-based __hash__, silently making VecFx32 unusable as a dict key / set member (needed for the hashed vertex-adjacency lookup used by the triangle/quad stripper). Restore it explicitly.
        return hash((self.x, self.y, self.z))
