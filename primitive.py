import sys
import bpy
from mathutils.geometry import tessellate_polygon
from .util import *
from . import local_logger as logger


def bake_primitive_transform(prim, mtx):
    """Bake a transform directly into a Primitive's position and normal
    data. Used when a mesh doesn't get its own node (bones-only node
    mode) there's nowhere else for its own position/rotation/scale to
    live once the node is gone, so it gets applied to the raw vertex data
    instead. Normals go through the matrix's rotation only (via
    to_quaternion(), the same approach already used for skinning normals
    elsewhere in this plugin), so scale on the object doesn't skew them.
    """
    quat = mtx.to_quaternion()
    for i in range(len(prim.positions)):
        p = mtx @ prim.positions[i].to_vector()
        prim.positions[i] = VecFx32().from_vector(p)

        n = quat @ prim.normals[i].to_vector()
        prim.normals[i] = vector_to_vecfx10(n.normalized())


def triangulate_primitive(primitive):
    """Split an ngon or non-planar-quad Primitive into a list of
    'triangles'-type Primitives.

    Uses Blender's own polygon tessellation (mathutils.geometry's ear
    clipping, which correctly handles concave polygons) on the positions
    already collected on primitive, rather than touching the source
    mesh with bmesh. so there's no risk of custom data layers (UVs,
    vertex colors, custom split normals, vertex group weights) getting
    lost or altered during triangulation: each output triangle just reuses
    add_vtx() to copy its three corners' data straight from the original
    primitive.
    """
    points = [p.to_vector() for p in primitive.positions]
    triangle_indices = tessellate_polygon([points])

    triangles = []
    for (a, b, c) in triangle_indices:
        tri = Primitive()
        tri.type = 'triangles'
        tri.material_index = primitive.material_index
        tri.add_vtx(primitive, a)
        tri.add_vtx(primitive, b)
        tri.add_vtx(primitive, c)
        triangles.append(tri)
    return triangles


def _vertex_key(prim, idx):
    """A hashable key that is equal for two vertices only if
    is_extra_data_equal() AND position-equality would also consider them
    equal (it's a strictly finer-grained equality: same position, color,
    normal, texcoord and material). Used to build an inverted index so the
    strippers can find "triangles/quads that share a vertex with this one"
    in roughly O(1) instead of scanning every other triangle/quad.
    """
    p = prim.positions[idx]
    n = prim.normals[idx]
    t = prim.texcoords[idx]
    return (
        p.x, p.y, p.z,
        prim.colors[idx],
        prim.material_index,
        n.x, n.y, n.z,
        t.x, t.y, t.z,
    )


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

        # --- Candidate discovery ------------------------------------------
        # The original code compared every triangle against every other
        # triangle (an O(T^2) loop, each comparison itself doing up to 9
        # position/color/normal/uv checks) just to find the up-to-3
        # triangles that share an edge with it. For meshes with more than a
        # few hundred triangles this dominated export time.
        #
        # Any pair of triangles that is_suitable_tstrip_candidate() can
        # accept MUST share at least one vertex with matching position,
        # color, normal, texcoord and material (that's what "suitable"
        # requires, two shared vertices, in fact). So instead of scanning
        # every triangle, we first build an inverted index from vertex key
        # -> triangle indices, then only test the (usually tiny) set of
        # triangles that share at least one vertex key with the current
        # triangle. This is a strict prefilter, not an approximation: it
        # can only ever discard triangles that is_suitable_tstrip_candidate
        # would have rejected anyway, so the result is identical to the
        # original brute-force search, just much faster to compute.
        vertex_buckets = {}
        for t_idx, tri in enumerate(tris):
            for corner in range(3):
                vertex_buckets.setdefault(
                    _vertex_key(tri, corner), []).append(t_idx)

        for t_idx, tri in enumerate(tris):
            tri.next_candidate_count = 0
            tri.next_candidates = [-1] * 4
            candidate_idxs = set()
            for corner in range(3):
                candidate_idxs.update(
                    vertex_buckets[_vertex_key(tri, corner)])
            candidate_idxs.discard(t_idx)
            # Sorted so ties are broken in the same ascending-index order
            # the original enumerate(tris) scan used.
            for i in sorted(candidate_idxs):
                candidate = tris[i]
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

        # Same hashed-adjacency prefilter as TriStripper.process see the comment there for why this is safe (it can only discard candidates that is_suitable_qstrip_candidate would have rejected  anyway) and why it turns an O(Q^2) scan into roughly O(Q).
        vertex_buckets = {}
        for q_idx, quad in enumerate(quads):
            for corner in range(4):
                vertex_buckets.setdefault(
                    _vertex_key(quad, corner), []).append(q_idx)

        for q_idx, quad in enumerate(quads):
            quad.next_candidate_count = 0
            quad.next_candidates = [-1] * 4
            candidate_idxs = set()
            for corner in range(4):
                candidate_idxs.update(
                    vertex_buckets[_vertex_key(quad, corner)])
            candidate_idxs.discard(q_idx)
            for i in sorted(candidate_idxs):
                candidate = quads[i]
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
            self.groups = []
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
        # The group this vertex belongs to.
        # This is not important for stripping.
        self.groups = []
        self.processed = False
        self.next_candidate_count = 0
        # An array of indexes.
        self.next_candidates = []

        self.material_index = get_global_mat_index(
            obj, polygon.material_index)

        vertices = [v.co for v in obj.data.vertices.values()]

        if len(polygon.loop_indices) == 3:
            self.type = 'triangles'
            self.vertex_count = 3
        elif len(polygon.loop_indices) == 4:
            self.type = 'quads'
            self.vertex_count = 4
        else:
            # 5+ sided face. Never supported by the hardware. kept here as a distinct 'ngon' type only so process_mesh can hand it straight to triangulate_primitive(), it should never reach the stripper or the final output as anything but triangles.
            self.type = 'ngon'
            self.vertex_count = len(polygon.loop_indices)

        use_colors = False

        if bpy.app.version >= (3, 2, 0):
            if obj.data.color_attributes.active_color is not None:
                use_colors = True
        else:
            if len(obj.data.vertex_colors) > 0:
                use_colors = True

        for idx in polygon.loop_indices:
            # Get vertex and convert it to VecFx32.
            vertex_index = obj.data.loops[idx].vertex_index
            vecfx32 = VecFx32().from_floats(vertices[vertex_index])

            # Store position.
            self.positions.append(vecfx32)

            # Store group.
            groups = obj.data.vertices[vertex_index].groups
            if groups:
                self.groups.append(groups[0].group)
            else:
                self.groups.append(-1)

            # Color
            if use_colors:
                color = (0, 0, 0)

                # Use special function to get color because the vertex colors
                # may not align with the vertex loops.

                if bpy.app.version >= (3, 2, 0) and obj.data.color_attributes.active_color.domain == "POINT":
                    color = get_color_from_obj(obj, vertex_index)
                else:
                    color = get_color_from_obj(obj, idx)

                r = int(round(color[0] * 31))
                g = int(round(color[1] * 31))
                b = int(round(color[2] * 31))
                self.colors.append((r, g, b))
            else:
                self.colors.append((0, 0, 0))

            # Normal
            normal = obj.data.loops[idx].normal
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
        self.groups.append(src.groups[idx])

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
        return False

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
