import bpy
import bmesh
from bpy.props import IntProperty, FloatProperty
from .util import force_object_mode, safe_register_class


def _get_uv_islands(bm, uv_layer):
    """Groups a bmesh's faces into UV islands: connected groups of faces
    where crossing from one face to its neighbor doesn't cross a UV seam
    (the two faces' UVs actually line up along the shared edge). Standard
    flood-fill island detection.

    Returns a list of lists of BMFace.
    """
    visited = set()
    islands = []

    def uv_at_vert(face, vert):
        for loop in face.loops:
            if loop.vert == vert:
                return loop[uv_layer].uv
        return None

    def faces_connected(f1, f2, edge):
        for v in edge.verts:
            uv1 = uv_at_vert(f1, v)
            uv2 = uv_at_vert(f2, v)
            if uv1 is None or uv2 is None:
                return False
            if (uv1 - uv2).length > 1e-6:
                return False
        return True

    for seed in bm.faces:
        if seed.index in visited:
            continue
        island = []
        stack = [seed]
        visited.add(seed.index)
        while stack:
            face = stack.pop()
            island.append(face)
            for loop in face.loops:
                edge = loop.edge
                for other in edge.link_faces:
                    if other.index in visited:
                        continue
                    if faces_connected(face, other, edge):
                        visited.add(other.index)
                        stack.append(other)
        islands.append(island)

    return islands


def _get_mesh_pieces(bm):
    """Groups a bmesh's faces into connected pieces (loose parts): faces
    reachable from each other by crossing shared edges, regardless of UV
    seams. Same flood-fill idea as _get_uv_islands, just using plain mesh
    connectivity instead of UV connectivity.
    """
    visited = set()
    pieces = []

    for seed in bm.faces:
        if seed.index in visited:
            continue
        piece = []
        stack = [seed]
        visited.add(seed.index)
        while stack:
            face = stack.pop()
            piece.append(face)
            for edge in face.edges:
                for other in edge.link_faces:
                    if other.index not in visited:
                        visited.add(other.index)
                        stack.append(other)
        pieces.append(piece)

    return pieces


def _texture_size_for_material(material):
    """Returns (width, height) for the texture this NNS material uses,
    or None if it doesn't have one. Matches how NitroModelMtxPrim.
    add_primitive computes pixel-space UVs during export (uv * width,
    following the same convention), so "in bounds here" and "in bounds
    at export time" agree.
    """
    if material is None or not getattr(material, 'is_nns', False):
        return None
    image = getattr(material, 'nns_image', None)
    if image is None:
        return None
    width, height = image.size[0], image.size[1]
    if width == 0 or height == 0:
        return None
    return width, height


def _iter_scene_mesh_objects(context):
    for obj in context.view_layer.objects:
        if obj.type == 'MESH':
            yield obj


def _pixel_bounds(min_u, max_u, min_v, max_v, width, height):
    """Converts a UV-space bounding box to pixel-space S/T bounds, using
    the same formula export uses (s = u * width, t = v * -height +
    height). The V-flip means the min/max in T can come out swapped
    relative to the min/max in V, so this sorts them back out.
    """
    s_values = (min_u * width, max_u * width)
    t_values = (min_v * -height + height, max_v * -height + height)
    return min(s_values), max(s_values), min(t_values), max(t_values)


def _out_of_bounds(min_s, max_s, min_t, max_t, limit):
    return (abs(min_s) > limit or abs(max_s) > limit
            or abs(min_t) > limit or abs(max_t) > limit)


def _split_island(island, uv_layer):
    """Splits an island roughly in half along whichever UV axis it's
    bigger on, based on each face's own UV centroid. This is a plain
    geometric bisection of the connectivity group, not a "smart" seam
    placement decision, it doesn't try to pick a seam that looks good,
    just makes progress toward pieces small enough to fit.

    Two adjacent faces end up on opposite sides of the cut simply
    because their halves get shifted by different amounts afterward
    (see _fix_island_recursive), their UVs stop matching across that
    edge, which is exactly what makes them read back as separate islands
    next time. No mesh topology changes and no vertices get duplicated;
    UVs are already stored per face-corner, not per vertex, so two faces
    sharing a 3D vertex can already have independent UV values there.

    Returns two lists of BMFace, both guaranteed non-empty (as long as
    the input has at least 2 faces) so recursion always makes progress.
    """
    centroids = []
    for face in island:
        us = [loop[uv_layer].uv.x for loop in face.loops]
        vs = [loop[uv_layer].uv.y for loop in face.loops]
        centroids.append((sum(us) / len(us), sum(vs) / len(vs)))

    all_u = [c[0] for c in centroids]
    all_v = [c[1] for c in centroids]
    u_span = max(all_u) - min(all_u)
    v_span = max(all_v) - min(all_v)

    axis = 0 if u_span >= v_span else 1
    values = all_u if axis == 0 else all_v
    mid = (max(values) + min(values)) / 2

    group_a, group_b = [], []
    for face, centroid in zip(island, centroids):
        (group_a if centroid[axis] <= mid else group_b).append(face)

    # Degenerate case (e.g. every face's centroid landed on exactly the same point), fall back to a plain positional split so we always make progress instead of ever looping forever.
    if not group_a or not group_b:
        half = len(island) // 2
        group_a, group_b = island[:half], island[half:]

    return group_a, group_b


def _fix_island_recursive(island, uv_layer, width, height, limit,
                           depth=0, max_depth=12):
    """Tries to bring island into bounds, splitting it if a single
    shift isn't enough. Mutates the UV data of whichever pieces get
    fixed in place.

    Returns (fixed_count, unfixable_face_count, splits_made).
    fixed_count counts leaf pieces that got a successful shift
    (whether or not they came from a split), unfixable_face_count
    counts individual faces that are still out of bounds even alone
    (meaning that one face's own UV footprint is bigger than the valid
    range. Splitting can't help, it needs an actual UV rescale),
    splits_made counts how many bisection cuts happened.
    """
    us = [loop[uv_layer].uv.x for face in island for loop in face.loops]
    vs = [loop[uv_layer].uv.y for face in island for loop in face.loops]
    min_u, max_u = min(us), max(us)
    min_v, max_v = min(vs), max(vs)

    shift_u = round((min_u + max_u) / 2)
    shift_v = round((min_v + max_v) / 2)

    new_min_s, new_max_s, new_min_t, new_max_t = _pixel_bounds(
        min_u - shift_u, max_u - shift_u,
        min_v - shift_v, max_v - shift_v,
        width, height)
    fits_with_shift = not _out_of_bounds(
        new_min_s, new_max_s, new_min_t, new_max_t, limit)

    if fits_with_shift:
        for face in island:
            for loop in face.loops:
                uv = loop[uv_layer].uv
                uv.x -= shift_u
                uv.y -= shift_v
        return 1, 0, 0

    # A single face that still doesn't fit on its own needs an actual UV rescale, not more splitting. There's nothing left to cut. Same deal if we've hit the recursion depth safety cap (2**12 = 4096 pieces, well past anything a real island should ever need).
    if len(island) <= 1 or depth >= max_depth:
        for face in island:
            face.select = True
        return 0, len(island), 0

    group_a, group_b = _split_island(island, uv_layer)
    fixed_a, unfixable_a, splits_a = _fix_island_recursive(
        group_a, uv_layer, width, height, limit, depth + 1, max_depth)
    fixed_b, unfixable_b, splits_b = _fix_island_recursive(
        group_b, uv_layer, width, height, limit, depth + 1, max_depth)

    return (fixed_a + fixed_b, unfixable_a + unfixable_b,
            splits_a + splits_b + 1)


class NNS_OT_check_uv_bounds(bpy.types.Operator):
    """Selects every face whose UV goes past the pixel threshold below.
    Doesn't change anything, just shows you what's out of bounds.
    same check the exporter itself warns about, just interactive.
    """
    bl_idname = "nns.check_uv_bounds"
    bl_label = "Check UV Bounds"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with force_object_mode(context):
            limit = context.scene.nns_uv_max_pixel
            flagged_faces = 0
            flagged_objects = 0

            for obj in _iter_scene_mesh_objects(context):
                mesh = obj.data
                if not mesh.uv_layers.active:
                    continue
                tex_size = None
                for slot in obj.material_slots:
                    tex_size = _texture_size_for_material(slot.material)
                    if tex_size is not None:
                        break
                if tex_size is None:
                    continue
                width, height = tex_size

                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.faces.ensure_lookup_table()
                uv_layer = bm.loops.layers.uv.active
                if uv_layer is None:
                    bm.free()
                    continue

                obj.select_set(False)
                any_flagged = False
                for face in bm.faces:
                    face.select = False
                    out_of_bounds = False
                    for loop in face.loops:
                        u, v = loop[uv_layer].uv
                        s = u * width
                        t = v * -height + height
                        if abs(s) > limit or abs(t) > limit:
                            out_of_bounds = True
                            break
                    if out_of_bounds:
                        face.select = True
                        flagged_faces += 1
                        any_flagged = True

                # face.select alone doesn't cascade to the vertices/edges that make it up. Without this, Blender shows a half-lit result (edges highlighted from whichever neighboring selection happens to touch them, but no face fill), since vert/edge/face selection state can get out of sync if only one of them is set directly.
                bm.select_flush(True)
                bm.to_mesh(mesh)
                mesh.update()
                bm.free()

                if any_flagged:
                    obj.select_set(True)
                    flagged_objects += 1

            if flagged_faces:
                self.report(
                    {'WARNING'},
                    f"NNS: {flagged_faces} face(s) across {flagged_objects} "
                    f"object(s) have UVs past {limit}px. Selected them.",
                )
            else:
                self.report({'INFO'}, "NNS: All UVs are within bounds.")

            return {'FINISHED'}


class NNS_OT_fix_uv_bounds(bpy.types.Operator):
    """Recenters any UV island that's out of bounds by a whole number
    of texture widths/heights (i.e. exact multiples of 1.0 in UV space),
    not an arbitrary offset. Under the DS's default wrapping texture
    mode, shifting by a whole texture size shows the exact same part of
    the texture so this brings the numbers back in range without
    changing what's actually displayed. Islands that are already in
    bounds are left untouched.

    If a single shift isn't enough to fit the whole island, it gets
    split in half (roughly, along whichever UV axis it's bigger on) and
    each half is fixed independently, splitting again if a half is
    still too big. This is a plain geometric bisection, not a "smart"
    seam placement decision, so it isn't going to pick the prettiest
    possible cut but it keeps almost all of the island's original
    vertex sharing intact (only the faces right at each cut lose it),
    which is a lot cheaper than treating the whole island as a pile of
    disconnected single faces. Only a single face that's still too big
    completely on its own (an oversized UV footprint on one
    polygon) can't be helped by any of this. That gets selected and
    reported as needing an actual UV rescale by hand.
    """
    bl_idname = "nns.fix_uv_bounds"
    bl_label = "Fix UV Bounds"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with force_object_mode(context):
            limit = context.scene.nns_uv_max_pixel
            fixed_islands = 0
            unfixable_faces = 0
            splits_made = 0
            touched_objects = 0

            for obj in _iter_scene_mesh_objects(context):
                mesh = obj.data
                if not mesh.uv_layers.active:
                    continue
                tex_size = None
                for slot in obj.material_slots:
                    tex_size = _texture_size_for_material(slot.material)
                    if tex_size is not None:
                        break
                if tex_size is None:
                    continue
                width, height = tex_size

                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.faces.ensure_lookup_table()
                uv_layer = bm.loops.layers.uv.active
                if uv_layer is None:
                    bm.free()
                    continue

                obj.select_set(False)
                for face in bm.faces:
                    face.select = False
                any_touched = False

                for island in _get_uv_islands(bm, uv_layer):
                    us = [loop[uv_layer].uv.x
                          for face in island for loop in face.loops]
                    vs = [loop[uv_layer].uv.y
                          for face in island for loop in face.loops]
                    min_s, max_s, min_t, max_t = _pixel_bounds(
                        min(us), max(us), min(vs), max(vs), width, height)
                    if not _out_of_bounds(min_s, max_s, min_t, max_t, limit):
                        continue

                    fixed, unfixable, splits = _fix_island_recursive(
                        island, uv_layer, width, height, limit)
                    fixed_islands += fixed
                    unfixable_faces += unfixable
                    splits_made += splits
                    any_touched = True

                if any_touched:
                    bm.select_flush(True)
                    bm.to_mesh(mesh)
                    mesh.update()
                    obj.select_set(True)
                    touched_objects += 1
                bm.free()

            if fixed_islands or unfixable_faces:
                parts = []
                if fixed_islands:
                    piece_note = (
                        f" ({splits_made} cut(s) needed along the way)"
                        if splits_made else ""
                    )
                    parts.append(
                        f"recentered {fixed_islands} island(s)/piece(s)"
                        f"{piece_note}"
                    )
                if unfixable_faces:
                    parts.append(
                        f"couldn't fix {unfixable_faces} face(s), each "
                        "one's own UV footprint is bigger than the "
                        "valid range on its own (selected them, these "
                        "need an actual UV rescale by hand)"
                    )
                self.report(
                    {'WARNING'} if unfixable_faces else {'INFO'},
                    f"NNS: {'; '.join(parts)}, across {touched_objects} "
                    "object(s).",
                )
            else:
                self.report({'INFO'}, "NNS: Nothing needed fixing.")

            return {'FINISHED'}


class NNS_OT_check_position_bounds(bpy.types.Operator):
    """Selects every face belonging to a connected piece of mesh whose
    bounding box center sits farther than the threshold below from the
    object's origin. Doesn't change anything.
    """
    bl_idname = "nns.check_position_bounds"
    bl_label = "Check Model Location"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with force_object_mode(context):
            limit = context.scene.nns_position_max_distance
            flagged_faces = 0
            flagged_objects = 0

            for obj in _iter_scene_mesh_objects(context):
                mesh = obj.data
                obj.select_set(False)
                any_flagged = False

                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.faces.ensure_lookup_table()

                for face in bm.faces:
                    face.select = False

                for piece in _get_mesh_pieces(bm):
                    verts = {v for face in piece for v in face.verts}
                    xs = [v.co.x for v in verts]
                    ys = [v.co.y for v in verts]
                    zs = [v.co.z for v in verts]
                    center = (
                        (min(xs) + max(xs)) / 2,
                        (min(ys) + max(ys)) / 2,
                        (min(zs) + max(zs)) / 2,
                    )
                    distance = (
                        center[0] ** 2 + center[1] ** 2 + center[2] ** 2
                    ) ** 0.5
                    if distance > limit:
                        for face in piece:
                            face.select = True
                        flagged_faces += len(piece)
                        any_flagged = True

                bm.select_flush(True)
                bm.to_mesh(mesh)
                mesh.update()
                bm.free()

                if any_flagged:
                    obj.select_set(True)
                    flagged_objects += 1

            if flagged_faces:
                self.report(
                    {'WARNING'},
                    f"NNS: {flagged_faces} face(s) across {flagged_objects} "
                    f"object(s) are farther than {limit} units from the "
                    "origin. Selected them.",
                )
            else:
                self.report({'INFO'}, "NNS: Everything is within bounds.")

            return {'FINISHED'}


class NNS_OT_fix_position_bounds(bpy.types.Operator):
    """Moves any connected piece of mesh that's out of bounds back
    toward the object's origin, a straight translation, so the piece's
    own shape doesn't change, only where it sits. Pieces already in
    bounds are left untouched.

    If a piece's own size is bigger than the valid range (its farthest
    point from its own center is already past the threshold), no
    translation can bring all of it in bounds that gets selected and
    reported separately instead of silently claiming success.
    """
    bl_idname = "nns.fix_position_bounds"
    bl_label = "Fix Model Location"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        with force_object_mode(context):
            limit = context.scene.nns_position_max_distance
            fixed_pieces = 0
            unfixable_pieces = 0
            touched_objects = 0

            for obj in _iter_scene_mesh_objects(context):
                mesh = obj.data

                bm = bmesh.new()
                bm.from_mesh(mesh)
                bm.faces.ensure_lookup_table()

                obj.select_set(False)
                for face in bm.faces:
                    face.select = False
                any_touched = False

                for piece in _get_mesh_pieces(bm):
                    verts = {v for face in piece for v in face.verts}
                    xs = [v.co.x for v in verts]
                    ys = [v.co.y for v in verts]
                    zs = [v.co.z for v in verts]
                    center = (
                        (min(xs) + max(xs)) / 2,
                        (min(ys) + max(ys)) / 2,
                        (min(zs) + max(zs)) / 2,
                    )
                    distance = (
                        center[0] ** 2 + center[1] ** 2 + center[2] ** 2
                    ) ** 0.5
                    if distance <= limit:
                        continue

                    # The farthest any point in this piece sits from its OWN center even after perfectly centering the piece on the origin, its farthest point would still be at least this far away.
                    radius = max(
                        ((x - center[0]) ** 2 + (y - center[1]) ** 2
                         + (z - center[2]) ** 2) ** 0.5
                        for x, y, z in zip(xs, ys, zs)
                    )

                    if radius > limit:
                        for face in piece:
                            face.select = True
                        unfixable_pieces += 1
                        any_touched = True
                        continue

                    for v in verts:
                        v.co.x -= center[0]
                        v.co.y -= center[1]
                        v.co.z -= center[2]

                    fixed_pieces += 1
                    any_touched = True

                if any_touched:
                    bm.select_flush(True)
                    bm.to_mesh(mesh)
                    mesh.update()
                    obj.select_set(True)
                    touched_objects += 1
                bm.free()

            if fixed_pieces or unfixable_pieces:
                parts = []
                if fixed_pieces:
                    parts.append(f"moved {fixed_pieces} piece(s)")
                if unfixable_pieces:
                    parts.append(
                        f"couldn't fix {unfixable_pieces} piece(s), "
                        "they're bigger than the valid range on their "
                        "own (selected them)"
                    )
                self.report(
                    {'WARNING'} if unfixable_pieces else {'INFO'},
                    f"NNS: {'; '.join(parts)}, across {touched_objects} "
                    "object(s).",
                )
            else:
                self.report({'INFO'}, "NNS: Nothing needed fixing.")

            return {'FINISHED'}


class NNS_PT_bounds_panel(bpy.types.Panel):
    bl_label = "NNS Bounds Check"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "NNS Scene"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="UV bounds:")
        box.prop(scene, "nns_uv_max_pixel")
        row = box.row(align=True)
        row.operator("nns.check_uv_bounds", text="Check UV")
        row.operator("nns.fix_uv_bounds", text="Fix UV")

        box = layout.box()
        box.label(text="Model location bounds:")
        box.prop(scene, "nns_position_max_distance")
        row = box.row(align=True)
        row.operator("nns.check_position_bounds", text="Check Location")
        row.operator("nns.fix_position_bounds", text="Fix Location")


_classes = (
    NNS_OT_check_uv_bounds,
    NNS_OT_fix_uv_bounds,
    NNS_OT_check_position_bounds,
    NNS_OT_fix_position_bounds,
    NNS_PT_bounds_panel,
)


def bounds_register():
    bpy.types.Scene.nns_uv_max_pixel = IntProperty(
        name="Max UV pixel",
        description=(
            "How far a UV is allowed to sit from the origin, in pixels, "
            "before Check/Fix UV treat it as out of bounds. The "
            "hardware's own hard limit is 2048, the default here, "
            "lower it if you want to catch things earlier"
        ),
        default=2048,
        min=0,
        max=2048)
    bpy.types.Scene.nns_position_max_distance = FloatProperty(
        name="Max location distance",
        description=(
            "How far a piece of mesh is allowed to sit from the "
            "object's origin, in world units, before Check/Fix Location "
            "treat it as out of bounds. There's no confirmed hard "
            "number from g3dcvtr for this one, tune it to your model's "
            "actual scale"
        ),
        default=500.0,
        min=0.0)

    for cls in _classes:
        safe_register_class(cls)


def bounds_unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.nns_uv_max_pixel
    del bpy.types.Scene.nns_position_max_distance
