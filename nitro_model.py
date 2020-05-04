import bpy
import sys
import os
from mathutils import Vector, Matrix
from bpy_extras.io_utils import axis_conversion
from bpy_extras import node_shader_utils
from .util import VecFx32, float_to_fx32, Vecfx10, vector_to_vecfx10
from . import local_logger as logger
from . import nitro_tga


model = None


settings = {}


global_matrix = None


class TriStripper():
    def get_previous_tri_edge(self, a, b):
        if b == 0:
            return (2 - (0 if a == 1 else 1), a)
        if b == 1:
            return (0 if a == 2 else 2, a)
        return (1 if a == 0 else 0, a)

    def try_strip_in_direction(self, tris, tri_idx, vtxa, vtxb):
        processed_tmp = [x.processed for x in tris]
        processed_tmp[tri_idx] = True
        tri = tris[tri_idx]
        vtxb, vtxa = self.get_previous_tri_edge(vtxb, vtxa)
        tri_count = 1
        while True:
            i = -1
            while i < 3:
                i += 1
                if i >= 3:
                    break
                if tri.next_candidates[i] == -1:
                    continue
                candidate = tris[tri.next_candidates[i]]
                if processed_tmp[tri.next_candidates[i]]:
                    continue
                if not tri.is_suitable_tstrip_candidate_edge(candidate,
                                                             vtxa,
                                                             vtxb):
                    continue
                pos_a = tri.positions[vtxa]
                vtxa = 0
                while vtxa < 3:
                    if candidate.positions[vtxa] == pos_a:
                        break
                    vtxa += 1
                pos_b = tri.positions[vtxb]
                vtxb = 0
                while vtxb < 3:
                    if candidate.positions[vtxb] == pos_b:
                        break
                    vtxb += 1
                if vtxa != 3 and vtxb != 3:
                    vtxb, vtxa = self.get_previous_tri_edge(vtxb, vtxa)
                    processed_tmp[tri.next_candidates[i]] = True
                    tri_count += 1
                    tri = candidate
                    break
            if i == 3:
                break
        return tri_count

    def make_tstrip_primitive(self, tris, tri_idx, vtxa, vtxb):
        result = Primitive()
        result.type = 'triangle_strip'
        tri = tris[tri_idx]
        tri.processed = True
        result.material_index = tri.material_index
        result.add_vtx(tri, vtxa)
        result.add_vtx(tri, vtxb)
        vtxb, vtxa = self.get_previous_tri_edge(vtxb, vtxa)
        result.add_vtx(tri, vtxb)
        while True:
            i = -1
            while i < 3:
                i += 1
                if i >= 3:
                    break
                if tri.next_candidates[i] == -1:
                    continue
                candidate = tris[tri.next_candidates[i]]
                if candidate.processed:
                    continue
                if not tri.is_suitable_tstrip_candidate_edge(candidate,
                                                             vtxa,
                                                             vtxb):
                    continue
                pos_a = tri.positions[vtxa]
                vtxa = 0
                while vtxa < 3:
                    if candidate.positions[vtxa] == pos_a:
                        break
                    vtxa += 1
                pos_b = tri.positions[vtxb]
                vtxb = 0
                while vtxb < 3:
                    if candidate.positions[vtxb] == pos_b:
                        break
                    vtxb += 1
                if vtxa != 3 and vtxb != 3:
                    vtxb, vtxa = self.get_previous_tri_edge(vtxb, vtxa)
                    result.add_vtx(candidate, vtxb)
                    candidate.processed = True
                    tri = candidate
            if i == 3:
                break
        return result

    def process(self, primitives):
        result = []
        tris = [x for x in primitives if x.type == 'triangles']
        for tri in tris:
            tri.processed = False

        for tri in tris:
            tri.next_candidate_count = 0
            tri.next_candidates = [-1] * 4
            for i, candidate in enumerate(tris):
                if not tri.is_suitable_tstrip_candidate(candidate):
                    continue
                tri.next_candidates[tri.next_candidate_count] = i
                tri.next_candidate_count += 1
                if tri.next_candidate_count >= 3:
                    break
        while True:
            count = 0
            for tri in tris:
                if tri.processed:
                    continue
                count += 1
                if tri.next_candidate_count > 0:
                    cand_count = len([x for x in tri.next_candidates
                                      if x != -1 and not tris[x].processed])
                    tri.next_candidate_count = cand_count
            if count == 0:
                break
            min_cand_count_idx = -1
            min_cand_count = sys.maxsize
            for i, tri in enumerate(tris):
                if tri.processed:
                    continue
                if tri.next_candidate_count < min_cand_count:
                    min_cand_count = tri.next_candidate_count
                    min_cand_count_idx = i
                    if min_cand_count <= 1:
                        break
            max_tris = 0
            max_tris_vtx0 = -1
            max_tris_vtx1 = -1
            for i in range(3):
                vtx0 = i
                vtx1 = 0 if i == 2 else i + 1
                tri_count = self.try_strip_in_direction(
                    tris, min_cand_count_idx, vtx0, vtx1)
                if tri_count > max_tris:
                    max_tris = tri_count
                    max_tris_vtx0 = vtx0
                    max_tris_vtx1 = vtx1
            if max_tris <= 1:
                tri = tris[min_cand_count_idx]
                tri.processed = True
                result.append(tri)
            else:
                result.append(self.make_tstrip_primitive(tris,
                                                         min_cand_count_idx,
                                                         max_tris_vtx0,
                                                         max_tris_vtx1))
        result.extend([x for x in primitives if x.type != 'triangles'])
        return result


class QuadStripper():
    def get_opposite_quad_edge(self, a, b):
        if a == 3 and b == 0:
            return (2, 1)
        if a == 0 and b == 3:
            return (1, 2)
        if a >= b:
            return (
                0 if a == 3 else a + 1,
                3 if b == 0 else b - 1
            )
        return (
            3 if a == 0 else a - 1,
            0 if b == 3 else b + 1
        )

    def try_strip_in_direction(self, quads, quad_idx, vtxa, vtxb):
        processed_tmp = [x.processed for x in quads]
        processed_tmp[quad_idx] = True
        quad = quads[quad_idx]
        vtxa, vtxb = self.get_opposite_quad_edge(vtxa, vtxb)
        quad_count = 1
        while True:
            i = -1
            while i < 4:
                i += 1
                if i >= 4:
                    break
                if quad.next_candidates[i] == -1:
                    continue
                candidate = quads[quad.next_candidates[i]]
                if processed_tmp[quad.next_candidates[i]]:
                    continue
                if not quad.is_suitable_qstrip_candidate_edge(candidate,
                                                              vtxa,
                                                              vtxb):
                    continue
                pos_a = quad.positions[vtxa]
                vtxa = 0
                while vtxa < 4:
                    if candidate.positions[vtxa] == pos_a:
                        break
                    vtxa += 1
                pos_b = quad.positions[vtxb]
                vtxb = 0
                while vtxb < 4:
                    if candidate.positions[vtxb] == pos_b:
                        break
                    vtxb += 1
                if vtxa != 4 and vtxb != 4:
                    vtxa, vtxb = self.get_opposite_quad_edge(vtxa, vtxb)
                    processed_tmp[quad.next_candidates[i]] = True
                    quad_count += 1
                    quad = candidate
                    break
            if i == 4 or quad_count > 1706:
                break
        return quad_count

    def make_qstrip_primitive(self, quads, quad_idx, vtxa, vtxb):
        result = Primitive()
        result.type = 'quad_strip'
        quad = quads[quad_idx]
        quad.processed = True
        result.material_index = quad.material_index
        result.add_vtx(quad, vtxa)
        result.add_vtx(quad, vtxb)
        vtxa, vtxb = self.get_opposite_quad_edge(vtxa, vtxb)
        result.add_vtx(quad, vtxa)
        result.add_vtx(quad, vtxb)
        quad_count = 1
        while True:
            i = -1
            while i < 4:
                i += 1
                if i >= 4:
                    break
                if quad.next_candidates[i] == -1:
                    continue
                candidate = quads[quad.next_candidates[i]]
                if candidate.processed:
                    continue
                if not quad.is_suitable_qstrip_candidate_edge(candidate,
                                                              vtxa,
                                                              vtxb):
                    continue
                pos_a = quad.positions[vtxa]
                vtxa = 0
                while vtxa < 4:
                    if candidate.positions[vtxa] == pos_a:
                        break
                    vtxa += 1
                pos_b = quad.positions[vtxb]
                vtxb = 0
                while vtxb < 4:
                    if candidate.positions[vtxb] == pos_b:
                        break
                    vtxb += 1
                if vtxa != 4 and vtxb != 4:
                    vtxa, vtxb = self.get_opposite_quad_edge(vtxa, vtxb)
                    result.add_vtx(candidate, vtxa)
                    result.add_vtx(candidate, vtxb)
                    candidate.processed = True
                    quad_count += 1
                    quad = candidate
                    break
            if i == 4 or quad_count >= 1706:
                break
        return result

    def process(self, primitives):
        result = []
        quads = [x for x in primitives if x.type == 'quads']

        for quad in quads:
            quad.next_candidate_count = 0
            quad.next_candidates = [-1] * 4
            for i, candidate in enumerate(quads):
                if not quad.is_suitable_qstrip_candidate(candidate):
                    continue
                quad.next_candidates[quad.next_candidate_count] = i
                quad.next_candidate_count += 1
                if quad.next_candidate_count >= 4:
                    break

        while True:
            count = 0
            for quad in quads:
                if quad.processed:
                    continue
                count += 1
                if quad.next_candidate_count > 0:
                    cand_count = len([x for x in quad.next_candidates
                                      if x != -1 and not quads[x].processed])
                    quad.next_candidate_count = cand_count
            if count == 0:
                break
            min_cand_count_idx = -1
            min_cand_count = sys.maxsize
            for i, quad in enumerate(quads):
                if quad.processed:
                    continue
                if quad.next_candidate_count < min_cand_count:
                    min_cand_count = quad.next_candidate_count
                    min_cand_count_idx = i
                    if min_cand_count <= 1:
                        break
            max_quads = 0
            max_quads_vtx0 = -1
            max_quads_vtx1 = -1
            for i in range(4):
                vtx0 = i
                vtx1 = 0 if i == 3 else i + 1
                quad_count = self.try_strip_in_direction(
                    quads,
                    min_cand_count_idx,
                    vtx0,
                    vtx1)
                if quad_count > max_quads:
                    max_quads = quad_count
                    max_quads_vtx0 = vtx0
                    max_quads_vtx1 = vtx1
            if max_quads <= 1:
                quad = quads[min_cand_count_idx]
                quad.processed = True
                result.append(quad)
            else:
                result.append(self.make_qstrip_primitive(quads,
                                                         min_cand_count_idx,
                                                         max_quads_vtx0,
                                                         max_quads_vtx1))
        result.extend([x for x in primitives if x.type != 'quads'])
        return result


class Primitive():
    """
    Raw representation of blender data into a primitive used
    for stripping.
    """
    def __init__(self, obj=None, polygon=None):
        if obj is None and polygon is None:
            self.type = 'illegal'
            self.positions = []
            self.normals = []
            self.colors = []
            self.texcoords = []
            self.processed = False
            self.next_candidate_count = 0
            # An array of indexes.
            self.next_candidates = []
            self.material_index = -1
            self.vertex_count = 0
            return

        self.type = 'illegal'
        self.positions = []
        self.normals = []
        self.colors = []
        self.texcoords = []
        self.processed = False
        self.next_candidate_count = 0
        # An array of indexes.
        self.next_candidates = []

        self.material_index = get_global_mat_index(
            obj, polygon.material_index)

        verts_local = [v.co for v in obj.data.vertices.values()]
        matrix = global_matrix @ obj.matrix_world
        verts_world = [matrix @ v_local for v_local in verts_local]

        if len(polygon.loop_indices) == 3:
            self.type = 'triangles'
            self.vertex_count = 3
        elif len(polygon.loop_indices) == 4:
            self.type = 'quads'
            self.vertex_count = 4

        use_colors = False

        if len(obj.data.vertex_colors) > 0:
            use_colors = True

        for idx in polygon.loop_indices:
            pos_scale = model.model_info.pos_scale

            # Get vertex and convert it to VecFx32.
            vertex_index = obj.data.loops[idx].vertex_index
            vecfx32 = VecFx32().from_floats(verts_world[vertex_index])

            # Apply pos_scale.
            self.positions.append(vecfx32 >> pos_scale)

            # Color
            if use_colors:
                color = obj.data.vertex_colors[0].data[idx].color
                r = int(color[0] * 31)
                g = int(color[1] * 31)
                b = int(color[2] * 31)
                self.colors.append((r, g, b))
            else:
                self.colors.append((0, 0, 0))

            # Normal
            normal = matrix @ obj.data.loops[idx].normal
            self.normals.append(vector_to_vecfx10(normal.normalized()))

            # Texture coordinates
            if obj.data.uv_layers.active is not None:
                if len(obj.data.uv_layers.active.data) <= idx:
                    logger.log('Object uv layer not aligned, add zero coord:')
                    logger.log(f'UV layer: {obj.data.uv_layers.active.name}')
                    self.texcoords.append(VecFx32([0, 0, 0]))
                else:
                    uv = obj.data.uv_layers.active.data[idx].uv
                    self.texcoords.append(
                        VecFx32().from_vector(Vector([uv[0], uv[1], 0])))
            else:
                self.texcoords.append(VecFx32([0, 0, 0]))

    def add_vtx(self, src, idx):
        self.vertex_count += 1
        self.positions.append(src.positions[idx])
        self.colors.append(src.colors[idx])
        self.normals.append(src.normals[idx])
        self.texcoords.append(src.texcoords[idx])

    def is_extra_data_equal(self, a, other, b):
        return (
            self.colors[a] == other.colors[b]
            and self.material_index == other.material_index
            and self.normals[a] == other.normals[b]
            and self.texcoords[a] == other.texcoords[b]
        )

    def is_suitable_tstrip_candidate(self, candidate):
        equal_count = 0
        first_i = 0
        first_j = 0
        for i in range(3):
            for j in range(3):
                if (self.positions[i] != candidate.positions[j]
                        or not self.is_extra_data_equal(i, candidate, j)):
                    continue
                if equal_count == 0:
                    first_i = i
                    first_j = j
                elif equal_count == 1:
                    if first_i == 0 and i == 2:
                        return first_j < j or (first_j == 2 and j == 0)
                    return first_j > j or (first_j == 0 and j == 2)
                equal_count += 1

    def is_suitable_tstrip_candidate_edge(self, candidate, a, b):
        equal_count = 0
        for i in range(3):
            if (self.positions[a] == candidate.positions[i]
                    and self.is_extra_data_equal(a, candidate, i)):
                equal_count += 1
            if (self.positions[b] == candidate.positions[i]
                    and self.is_extra_data_equal(b, candidate, i)):
                equal_count += 1
        return equal_count == 2

    def is_suitable_qstrip_candidate(self, candidate):
        equal_count = 0
        first_i = 0
        first_j = 0
        for i in range(4):
            for j in range(4):
                if (self.positions[i] != candidate.positions[j]
                        or not self.is_extra_data_equal(i, candidate, j)):
                    continue
                if equal_count == 0:
                    first_i = i
                    first_j = j
                elif equal_count == 1:
                    if first_i == 0 and i == 3:
                        return first_j < j or (first_j == 3 and j == 0)
                    return first_j > j or (first_j == 0 and j == 3)
                equal_count += 1
        return False

    def is_suitable_qstrip_candidate_edge(self, candidate, a, b):
        equal_count = 0
        for i in range(4):
            if (self.positions[a] == candidate.positions[i]
                    and self.is_extra_data_equal(a, candidate, i)):
                equal_count += 1
            if (self.positions[b] == candidate.positions[i]
                    and self.is_extra_data_equal(b, candidate, i)):
                equal_count += 1
        return equal_count == 2


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


class NitroPalette():
    def __init__(self, name, data, size, index):
        self.index = index
        self.name = name
        self.data = data
        self.size = size


class NitroTexImage():
    def __init__(self, path, index):
        self.path = path
        self.index = index
        self.name = str(os.path.splitext(os.path.basename(path))[0])[0:15]

        # Load Nitro TGA Data from path
        tga = nitro_tga.read_nitro_tga(path)

        # Set TexImage properties
        self.format = tga['nitro_data']['tex_format']
        self.width = tga['header']['image_width']
        self.height = tga['header']['image_heigth']
        self.original_width = tga['header']['image_width']
        self.original_height = tga['header']['image_heigth']

        # Color 0 Mode
        transp = tga['nitro_data']['color_0_transp']
        if self.format in ('palette4', 'palette16', 'palette256'):
            self.color0_mode = 'transparent' if transp else 'color'

        # Get Bitmap Data
        self.bitmap_data = nitro_tga.get_bitmap_data(tga)
        self.bitmap_size = nitro_tga.get_bitmap_size(tga)

        # Get Tex4x4 Palette Index Data
        if self.format == 'tex4x4':
            self.tex4x4_palette_idx_data = nitro_tga.get_pltt_idx_data(tga)
            self.tex4x4_palette_idx_size = nitro_tga.get_pltt_idx_size(tga)

        # Store the palette index that model.add_palette returns in here or
        # leave it -1.
        self.palette_idx = -1

        # Get Palette Data
        if self.format != 'direct':
            self.palette_name = tga['nitro_data']['palette_name'][0:15]
            plt_data = nitro_tga.get_palette_data(tga)
            plt_size = nitro_tga.get_palette_size(tga)
            palette = model.add_palette(self.palette_name, plt_data, plt_size)
            self.palette_idx = palette.index


class NitroMaterial():
    def __init__(self, blender_index, index):
        self.blender_index = blender_index
        self.index = index
        material = bpy.data.materials[blender_index]
        self.name = material.name

        self.type = material.nns_mat_type

        self.light0 = 'on' if material.nns_light0 else 'off'
        self.light1 = 'on' if material.nns_light1 else 'off'
        self.light2 = 'on' if material.nns_light2 else 'off'
        self.light3 = 'on' if material.nns_light3 else 'off'
        self.shininess_table_flag = 'on' if material.nns_use_srst else 'off'
        self.fog_flag = 'on' if material.nns_fog else 'off'
        self.wire_mode = 'on' if material.nns_wireframe else 'off'
        self.depth_test_decal = 'on' if material.nns_depth_test else 'off'
        self.translucent_update_depth = ('on'
                                         if material.nns_update_depth_buffer
                                         else 'off')
        self.render_1_pixel = 'on' if material.nns_render_1_pixel else 'off'
        self.far_clipping = 'on' if material.nns_far_clipping else 'off'
        self.polygon_id = material.nns_polygonid
        self.face = material.nns_display_face
        self.polygon_mode = material.nns_polygon_mode
        self.tex_gen_mode = material.nns_tex_gen_mode
        self.tex_gen_st_src = material.nns_tex_gen_st_src
        self.tex_tiling_u = material.nns_tex_tiling_u
        self.tex_tiling_v = material.nns_tex_tiling_v
        row0 = material.nns_tex_effect_mtx_0
        row1 = material.nns_tex_effect_mtx_1
        row2 = material.nns_tex_effect_mtx_2
        row3 = material.nns_tex_effect_mtx_3
        matrix = f'{row0[0]} {row0[1]} 0.0 0.0 ' \
                 f'{row1[0]} {row1[1]} 0.0 0.0 ' \
                 f'{row2[0]} {row2[1]} 1.0 0.0 ' \
                 f'{row3[0]} {row3[1]} 0.0 1.0'
        self.tex_effect_mtx = matrix
        self.tex_scale = f'{material.nns_tex_scale[0]} ' \
                         f'{material.nns_tex_scale[1]}'
        self.tex_rotate = str(material.nns_tex_rotate)
        self.tex_translate = f'{material.nns_tex_translate[0]} ' \
                             f'{material.nns_tex_translate[1]}'

        self.image_idx = -1
        self.palette_idx = -1

        if material.is_nns:
            self.alpha = material.nns_alpha
            self.diffuse = ' '.join(
                [str(int(x * 31)) for x in material.nns_diffuse])
            self.specular = ' '.join(
                [str(int(x * 31)) for x in material.nns_specular])
            self.ambient = ' '.join(
                [str(int(x * 31)) for x in material.nns_ambient])
            self.emission = ' '.join(
                [str(int(x * 31)) for x in material.nns_emission])
            if material.nns_image is not None \
                    and "tx" in material.nns_mat_type:
                filepath = material.nns_image.filepath
                path = os.path.realpath(bpy.path.abspath(filepath))
                _, extension = os.path.splitext(path)
                if extension == '.tga':
                    texture = model.find_texture(path)
                    self.image_idx = texture.index
                    self.palette_idx = texture.palette_idx
        else:
            # For now let's use PrincipledBSDF to get the color and image.
            wrap = node_shader_utils.PrincipledBSDFWrapper(material)
            self.alpha = int(wrap.alpha * 31)
            self.diffuse = ' '.join([
                str(int(self.lin2s(wrap.base_color[0]) * 31)),
                str(int(self.lin2s(wrap.base_color[1]) * 31)),
                str(int(self.lin2s(wrap.base_color[2]) * 31))
            ])
            self.specular = ' '.join(
                [str(int(wrap.specular * 31)) for _ in range(3)])
            self.ambient = '31 31 31'
            self.emission = '0 0 0'

            tex_wrap = getattr(wrap, 'base_color_texture', None)
            if tex_wrap is not None and tex_wrap.image is not None:
                path = os.path.realpath(bpy.path.abspath(
                    tex_wrap.image.filepath, library=tex_wrap.image.library))
                _, extension = os.path.splitext(path)
                if extension == '.tga':
                    texture = model.find_texture(path)
                    self.image_idx = texture.index
                    self.palette_idx = texture.palette_idx

    def lin2s(self, x):
        """
        Le color correction function. From some guy on blender stackexchange.
        http://entropymine.com/imageworsener/srgbformula/
        """
        a = 0.055
        if x <= 0.0031308:
            y = x * 12.92
        elif 0.0031308 < x <= 1:
            y = 1.055 * x ** (1 / 2.4) - 0.055
        return y


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
        self.use_normals = 'off'
        self.use_texcoords = 'off'

    def is_empty(self):
        if not self.primitives:
            return True
        if not self.primitives[0].commands:
            return True
        return False

    def add_primitive(self, obj, prim: Primitive, material):
        if prim.type == 'triangles':
            primitive = self.get_primitive('triangles')
            primitive.sort_key = 3
            model.output_info.vertex_size += 3
            model.output_info.triangle_size += 1
            model.output_info.polygon_size += 1
            primitive.triangle_size += 1
        elif prim.type == 'quads':
            primitive = self.get_primitive('quads')
            primitive.sort_key = 2
            model.output_info.vertex_size += 4
            model.output_info.quad_size += 1
            model.output_info.polygon_size += 1
            primitive.quad_size += 1
        elif prim.type == 'triangle_strip':
            primitive = self.get_primitive('triangle_strip')
            primitive.sort_key = 1
            model.output_info.vertex_size += prim.vertex_count
            model.output_info.triangle_size += 1
            model.output_info.polygon_size += 1
            primitive.triangle_size += 1
        elif prim.type == 'quad_strip':
            primitive = self.get_primitive('quad_strip')
            primitive.sort_key = 0
            model.output_info.vertex_size += prim.vertex_count
            model.output_info.quad_size += 1
            model.output_info.polygon_size += 1
            primitive.quad_size += 1

        if len(obj.data.vertex_colors) > 0 and "vc" in material.type:
            self.use_colors = 'on'

        if material.image_idx != -1 and "tx" in material.type and \
                material.tex_gen_mode != "nrm":
            self.use_texcoords = 'on'

        if ((material.light0 == 'on' or
            material.light1 == 'on' or
            material.light2 == 'on' or
            material.light3 == 'on') and "nr" in material.type) or \
                material.tex_gen_mode == "nrm":
            self.use_normals = 'on'

        for idx in range(len(prim.positions)):
            # Color
            if self.use_colors == 'on':
                r, g, b = prim.colors[idx]
                primitive.add_command('clr', 'rgb', f'{r} {g} {b}')

            # Normal
            if self.use_normals == 'on':
                normal = prim.normals[idx].to_vector()
                primitive.add_command('nrm', 'xyz',
                                      f'{normal.x} {normal.y} {normal.z}')

            # Texture coordinate.
            if self.use_texcoords == 'on':
                tex = model.textures[material.image_idx]
                uv = prim.texcoords[idx].to_vector()
                s = uv.x * tex.width
                t = uv.y * -tex.height + tex.height
                primitive.add_command('tex', 'st', f'{s} {t}')

            # Apply pos_scale.
            scaled_vecfx32 = prim.positions[idx]
            scaled_vec = scaled_vecfx32.to_vector()

            # Calculate difference from previous vertex.
            if not primitive.is_empty():
                diff_vecfx32 = scaled_vecfx32 - primitive._previous_vecfx32
                diff_vec = diff_vecfx32.to_vector()

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
        if type_ != 'quad_strip' and type_ != 'triangle_strip':
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
        self.textures = []
        self.palettes = []

    def collect(self):
        for obj in bpy.context.view_layer.objects:
            if obj.type != 'MESH':
                continue

            logger.log('Object: ' + obj.name)
            primitives = []

            obj.data.calc_normals_split()

            for polygon in obj.data.polygons:
                if len(polygon.loop_indices) > 4:
                    logger.log("Polygon is ngon. Skipped.")
                    continue
                if len(polygon.loop_indices) < 3:
                    logger.log("Polygon is a line. Skipped.")
                    continue
                index = get_global_mat_index(obj, polygon.material_index)
                if index == -1:
                    logger.log("Polygon doesn't have material. Skipped.")
                    continue
                primitives.append(Primitive(obj, polygon))

            if settings['use_primitive_strip']:
                quad_stripper = QuadStripper()
                primitives = quad_stripper.process(primitives)

                tri_stripper = TriStripper()
                primitives = tri_stripper.process(primitives)

            for primitive in primitives:
                material = self.find_material(primitive.material_index)
                pol = self.find_polgyon(material.index)
                logger.log(f"Add primitive. {primitive.type}")
                pol.add_primitive(obj, primitive, material)

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

    def find_texture(self, path):
        for texture in self.textures:
            if texture.path == path:
                return texture
        self.textures.append(NitroTexImage(path, len(self.textures)))
        return self.textures[-1]

    def add_palette(self, name, data, size):
        self.palettes.append(
            NitroPalette(name, data, size, len(self.palettes)))
        return self.palettes[-1]


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
