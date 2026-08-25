import os
import math
import decimal
from mathutils import Matrix
import bpy
from bpy_extras import node_shader_utils
from bpy_extras.io_utils import axis_conversion
from .util import *
from .primitive import *
from . import local_logger as logger
from . import nns_tga


# The hardware's texture coordinate range: g3dcvtr rejects a face outright if any of its UVs fall outside +/-2048 pixels from the origin. See the warning in NitroModelMtxPrim.add_primitive below.
NDS_TEXCOORD_LIMIT = 2048

# The DS geometry engine's position/vector matrix stack depth. See NitroModel._check_hardware_limits below.
NDS_MATRIX_STACK_DEPTH = 31


def is_identity_matrix(mtx, epsilon=1e-6):
    """True if `mtx` is (within floating point tolerance) the 4x4 identity
    matrix. Used to decide whether an Armature object's own transform can
    be safely dropped (see process_children's pass-through handling)
    without needing to bake/fold it into anything. If it's already
    identity, there's nothing to fold."""
    identity = Matrix.Identity(4)
    for i in range(4):
        for j in range(4):
            if abs(mtx[i][j] - identity[i][j]) > epsilon:
                return False
    return True


def is_quad_flat(obj, polygon, tolerance_degrees):
    """True if a 4-vertex polygon is planar enough to keep as a hardware
    quad. Splits it along one diagonal and compares the normals of the
    two resulting triangles; if they don't agree within `tolerance_degrees`,
    the quad isn't flat and needs triangulating for correct rendering on
    hardware that only supports flat quads.
    """
    loop_indices = list(polygon.loop_indices)
    verts = [
        obj.data.vertices[obj.data.loops[i].vertex_index].co
        for i in loop_indices
    ]

    def diagonal_normals(v0, v1, v2, v3):
        n1 = (v1 - v0).cross(v2 - v0)
        n2 = (v2 - v0).cross(v3 - v0)
        return n1, n2

    n1, n2 = diagonal_normals(*verts)
    if n1.length < 1e-12 or n2.length < 1e-12:
        # Degenerate triangle on this diagonal (e.g. three near-collinear
        # points) -- try the other diagonal before giving up.
        n1, n2 = diagonal_normals(verts[1], verts[2], verts[3], verts[0])
        if n1.length < 1e-12 or n2.length < 1e-12:
            # Degenerate either way; nothing meaningful to split.
            return True

    angle = math.degrees(n1.angle(n2))
    return angle <= tolerance_degrees


def force_apply_object_transform(obj):
    """Applies obj's location/rotation/scale the same way Ctrl+A > All
    Transforms does in the viewport, so obj.matrix_basis becomes
    identity afterward. Used so an Armature can always drop its
    redundant node in bones only mode (or whenever "Skip redundant
    armature node" is on) without us having to hand-roll baking that
    transform into every bone's bind matrix ourselves. Blender's own
    operator already does this correctly, so we just call it instead of
    re-implementing it.

    Restores the previous selection/active object afterward so this
    doesn't leave the user's selection in a different state than before
    they clicked export.
    """
    view_layer = bpy.context.view_layer
    prev_active = view_layer.objects.active
    prev_selected = [o for o in view_layer.objects if o.select_get()]

    for o in prev_selected:
        o.select_set(False)
    obj.select_set(True)
    view_layer.objects.active = obj

    try:
        bpy.ops.object.transform_apply(
            location=True, rotation=True, scale=True)
    finally:
        obj.select_set(False)
        for o in prev_selected:
            o.select_set(True)
        view_layer.objects.active = prev_active


def sort_by_node_id(items, get_id, get_label=None):
    """Stable-sort items by an optional manually-assigned node ID
    (get_id(item) -> int, or -1/None for "unset"). Items with an explicit
    ID (>= 0) come first, in ascending order, everything left unset keeps
    Blender's original relative order (Python's sort is stable) and is
    placed after all explicitly numbered siblings.

    This exists so modders can force a specific, reproducible node/bone
    order across re-exports (Blender doesn't guarantee bone iteration
    order stays stable across edits, which otherwise breaks reusing
    animation data between separately-exported assets that share a rig).
    """
    if get_label is None:
        get_label = lambda item: getattr(item, 'name', str(item))

    seen_ids = {}
    for item in items:
        node_id = get_id(item)
        if node_id is not None and node_id >= 0:
            label = get_label(item)
            if node_id in seen_ids:
                logger.log(
                    f"Warning: duplicate NNS node ID {node_id} used by "
                    f"both '{seen_ids[node_id]}' and '{label}'. "
                    "Their relative order is not guaranteed.",
                    debug_only=False,
                )
            else:
                seen_ids[node_id] = label

    def sort_key(item):
        node_id = get_id(item)
        return node_id if node_id is not None and node_id >= 0 else float('inf')

    return sorted(items, key=sort_key)


class NitroModelInfo():
    def __init__(self):
        self.pos_scale = 0
        self.max_coord = 0

    def add(self, vertex):
        max_coord = max(abs(vertex.x), abs(vertex.y), abs(vertex.z))
        if max_coord > self.max_coord:
            self.max_coord = max_coord

    def calculate(self):
        self.pos_scale = calculate_pos_scale(self.max_coord)


class NitroModelBoxTest():
    def __init__(self):
        box = get_all_max_min()
        self.xyz = box['min']
        self.whd = box['max'] - box['min']

        max_whd = abs(max(self.whd.x, self.whd.y, self.whd.z))
        min_xyz = abs(min(self.xyz.x, self.xyz.y, self.xyz.z))
        max_coord = max(max_whd, min_xyz)
        self.pos_scale = calculate_pos_scale(max_coord)


class NitroModelTexture():
    def __init__(self, model, path, index):
        self.path = path
        self.index = index
        self.name = str(os.path.splitext(os.path.basename(path))[0])[0:15]

        # Load Nitro TGA Data from path
        tga = None
        try:
            tga = nns_tga.read_nitro_tga(path)
        except UnicodeDecodeError as error:
            error.reason = f"{path} is not a valid Nitro TGA"
            raise error

        # Set TexImage properties
        self.format = tga['nitro_data']['tex_format']
        self.width = tga['header']['image_width']
        self.height = tga['header']['image_heigth']
        self.original_width = tga['header']['image_width']
        self.original_height = tga['header']['image_heigth']

        # Color 0 Mode
        transp = tga['nitro_data']['color_0_transp']
        if self.format in ('palette4', 'palette16', 'palette256'):
            self.color0_mode = 'transparency' if transp else 'color'

        # Get Bitmap Data
        self.bitmap_data = nns_tga.get_bitmap_data(tga)
        self.bitmap_size = nns_tga.get_bitmap_size(tga)

        # Get Tex4x4 Palette Index Data
        if self.format == 'tex4x4':
            self.tex4x4_palette_idx_data = nns_tga.get_pltt_idx_data(tga)
            self.tex4x4_palette_idx_size = nns_tga.get_pltt_idx_size(tga)

        # Store the palette index that model.add_palette returns in here or leave it -1.
        self.palette_idx = -1

        # Get Palette Data
        if self.format != 'direct':
            self.palette_name = tga['nitro_data']['palette_name'][0:15]
            plt_data = nns_tga.get_palette_data(tga)
            plt_size = nns_tga.get_palette_size(tga)
            palette = model.add_palette(self.palette_name, plt_data, plt_size)
            self.palette_idx = palette.index


class NitroModelPalette():
    def __init__(self, name, data, size, index):
        self.index = index
        self.name = name
        self.data = data
        self.size = size


class NitroModelMaterial():
    def __init__(self, model, blender_index, index):
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
        self.priority_id = material.nns_priorityid
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
                [str(int(round(lin2s(x) * 31)))
                 for x in material.nns_diffuse])
            self.specular = ' '.join(
                [str(int(round(lin2s(x) * 31)))
                 for x in material.nns_specular])
            self.ambient = ' '.join(
                [str(int(round(lin2s(x) * 31)))
                 for x in material.nns_ambient])
            self.emission = ' '.join(
                [str(int(round(lin2s(x) * 31)))
                 for x in material.nns_emission])
            if material.nns_image is not None \
                    and "tx" in material.nns_mat_type:

                path,extension = get_filepath_and_extension(material.nns_image)

                if extension.lower() == '.tga':
                    texture = model.find_texture(path)
                    self.image_idx = texture.index
                    self.palette_idx = texture.palette_idx
                else: 
                    # Prevents confusion due to non-tga textures not generating any texture data
                    raise Exception(f"{path} is not a Nitro TGA file")

                for texframe in material.nns_texframe_reference:

                    path_tx, extension_tx = get_filepath_and_extension(texframe.image)

                    if extension_tx.lower() == '.tga':
                        model.find_texture(path_tx)
                    else: 
                        # Prevents confusion due to non-tga textures not generating any texture data
                        raise Exception(f"{path_tx} is not a Nitro TGA file")

            elif ("tx" in material.nns_mat_type
                    and material.nns_texframe_reference):
                # The base "Texture" field (main material tab) is empty, but the Texture Pattern tab (used for .itp texture pattern animation) has entries. Previously this left image_idx at -1, flagging the material as texture-less even though textures exist for it. so the model would render untextured in-game. Use the first texture pattern entry as the base/display texture instead: that's what the material should show before any pattern animation kicks in, or permanently if this material has no animation on it at all.
                first_tex = material.nns_texframe_reference[0]
                first_path, first_ext = get_filepath_and_extension(
                    first_tex.image)

                if first_ext.lower() == '.tga':
                    texture = model.find_texture(first_path)
                    self.image_idx = texture.index
                    self.palette_idx = texture.palette_idx
                else:
                    raise Exception(
                        f"{first_path} is not a Nitro TGA file")

                for texframe in material.nns_texframe_reference:

                    path_tx, extension_tx = get_filepath_and_extension(
                        texframe.image)

                    if extension_tx.lower() == '.tga':
                        model.find_texture(path_tx)
                    else:
                        raise Exception(
                            f"{path_tx} is not a Nitro TGA file")

        else:
            # For now let's use PrincipledBSDF to get the color and image.
            wrap = node_shader_utils.PrincipledBSDFWrapper(material)
            self.alpha = int(wrap.alpha * 31)
            self.diffuse = ' '.join([
                str(int(round(lin2s(wrap.base_color[0]) * 31))),
                str(int(round(lin2s(wrap.base_color[1]) * 31))),
                str(int(round(lin2s(wrap.base_color[2]) * 31)))
            ])
            self.specular = ' '.join(
                [str(int(round(wrap.specular * 31))) for _ in range(3)])
            self.ambient = '31 31 31'
            self.emission = '0 0 0'

            tex_wrap = getattr(wrap, 'base_color_texture', None)
            if tex_wrap is not None and tex_wrap.image is not None:
                
                path = os.path.realpath(bpy.path.abspath(
                    tex_wrap.image.filepath, library=tex_wrap.image.library))
                _, extension = os.path.splitext(path)

                if extension.lower() == '.tga':
                    texture = model.find_texture(path)
                    self.image_idx = texture.index
                    self.palette_idx = texture.palette_idx
                else: 
                    # Prevents confusion due to non-tga textures not generating any texture data
                    raise Exception(f"{path} is not a Nitro TGA file")


class NitroModelMatrix():
    def __init__(self, index, node_idx, transform):
        self.index = index
        self.weight = 1
        self.node_idx = node_idx
        self.transform = transform


class NitroModelCommand():
    def __init__(self, type_, tag, data):
        self.type = type_
        self.tag = tag
        self.data = data


class NitroModelPrimitive():
    def __init__(self, type_):
        self.type = type_
        self.vertex_size = 0
        self.triangle_size = 0
        self.quad_size = 0
        self.commands = []
        self._previous_vecfx32 = None
        self._previous_mtx = -1
        self._previous_nrm = None
        self._previous_tex = None
        self._previous_clr = None
        # for after sort
        # quad_strip=0 triangle_strip=1 quads=2 triangles=3
        self.sort_key = 0

    def is_empty(self):
        return self._previous_vecfx32 is None

    def add_command(self, type_: str, tag: str, data: str):
        self.commands.append(NitroModelCommand(type_, tag, data))

    def insert_mtx(self, position, idx: int):
        self.commands.insert(
            position, NitroModelCommand('mtx', 'idx', str(idx)))

    def add_mtx(self, idx: int):
        self.add_command('mtx', 'idx', str(idx))

    def add_pos_xyz(self, vec: Vector):
        floats = [str(round(v, 6)) for v in vec]
        self.add_command('pos_xyz', 'xyz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_s(self, vec: Vector):
        floats = [str(round(v, 6)) for v in vec]
        self.add_command('pos_s', 'xyz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_diff(self, vec: Vector):
        floats = [str(round(v, 6)) for v in vec]
        self.add_command('pos_diff', 'xyz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_yz(self, vec: Vector):
        floats = [str(round(v, 6)) for v in [vec.y, vec.z]]
        self.add_command('pos_yz', 'yz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_xz(self, vec: Vector):
        floats = [str(round(v, 6)) for v in [vec.x, vec.z]]
        self.add_command('pos_xz', 'xz', ' '.join(floats))
        self.vertex_size += 1

    def add_pos_xy(self, vec: Vector):
        floats = [str(round(v, 6)) for v in [vec.x, vec.y]]
        self.add_command('pos_xy', 'xy', ' '.join(floats))
        self.vertex_size += 1


class NitroModelMtxPrim():
    def __init__(self, index, parent_polygon):
        self.index = index
        self.mtx_list = []
        # add_matrix_reference() used to do "if index not in self.mtx_list" followed by "self.mtx_list.index(index)", two linear scans over a list that grows with every distinct matrix referenced in this primitive group, called once per vertex whenever the bone changes. Same class of bug as the find_matrix_by_node_name fix above, just missed in this one spot. This dict mirrors mtx_list purely for O(1) lookups, mtx_list itself is untouched and still used exactly as before by every reader.
        self._mtx_index_map = {}
        self.primitives = []
        self.parent_polygon = parent_polygon

    def add_matrix_reference(self, index):
        if index not in self._mtx_index_map:
            self._mtx_index_map[index] = len(self.mtx_list)
            self.mtx_list.append(index)
        return self._mtx_index_map[index]

    def add_primitive(self, model, obj, prim: Primitive, material,
                       display_node):
        if prim.type == 'triangles':
            primitive = self.get_primitive('triangles')
            primitive.sort_key = 3
            primitive.triangle_size += 1
        elif prim.type == 'quads':
            primitive = self.get_primitive('quads')
            primitive.sort_key = 2
            primitive.quad_size += 1
        elif prim.type == 'triangle_strip':
            primitive = self.get_primitive('triangle_strip')
            primitive.sort_key = 1
            primitive.triangle_size += prim.vertex_count - 1
        elif prim.type == 'quad_strip':
            primitive = self.get_primitive('quad_strip')
            primitive.sort_key = 0
            primitive.quad_size += int((prim.vertex_count - 2) / 2)

        if bpy.app.version >= (3, 2, 0):
            if obj.data.color_attributes.active_color is not None and "vc" in material.type:
                self.parent_polygon.use_clr = True
        else:
            if len(obj.data.vertex_colors) > 0 and "vc" in material.type:
                self.parent_polygon.use_clr = True

        if material.image_idx != -1 and "tx" in material.type \
                and material.tex_gen_mode != "nrm" \
                and material.tex_gen_st_src != "material":
            self.parent_polygon.use_tex = True

        if ((material.light0 == 'on' or
            material.light1 == 'on' or
            material.light2 == 'on' or
            material.light3 == 'on') and "nr" in material.type) or \
                material.tex_gen_mode == "nrm":
            self.parent_polygon.use_nrm = True

        for idx in range(len(prim.positions)):
            # Find transform.
            group = prim.groups[idx]
            matrix = None
            if (model.settings['imd_compress_nodes']
               in ['unite', 'unite_combine']):
                matrix = model.find_matrix_by_node_name(model.root_name)
                group = -1
            elif group != -1:
                name = obj.vertex_groups[group].name
                matrix = model.find_matrix_by_node_name(name)

                weight = prim.weights[idx]
                if abs(weight - round(weight)) > 0.001:
                    warning = (
                        f"Vertex on '{obj.name}' is weighted "
                        f"{weight:.3f} to vertex group '{name}', not 0 "
                        "or 1. The DS can't blend a vertex between "
                        "bones, so it'll be exported fully rigid to "
                        "this bone instead, which can look different "
                        "in-game (most visible at a joint) than the "
                        "smooth blend shown in Blender. Exporting "
                        "anyway."
                    )
                    logger.log(warning, debug_only=False)
                    model.warnings.append(warning)
            else:
                matrix = model.find_matrix_by_node_name(display_node.name)

            node = model.find_node_by_index(matrix.node_idx)
            node.draw_mtx = True

            # Add mtx command.
            if matrix is not None and primitive._previous_mtx != matrix.index:
                index = self.add_matrix_reference(matrix.index)
                primitive.add_mtx(index)
                primitive._previous_mtx = matrix.index
                primitive._previous_nrm = None

            # Texture coordinate.
            if (self.parent_polygon.use_tex
               and primitive._previous_tex != prim.texcoords[idx]):
                primitive._previous_tex = prim.texcoords[idx]
                tex = model.textures[material.image_idx]
                uv = prim.texcoords[idx].to_vector()
                s = uv.x * tex.width
                t = uv.y * -tex.height + tex.height

                # The hardware (and g3dcvtr) only accepts texture coordinates from -2048 to 2048 pixels, starting at (0, 0). Outside that range g3dcvtr rejects the whole face with a "texcoord" error that just states the offending value, not which face or why. Export it anyway, but say clearly which face/material it was and by how much it's out of range so it's easy to track down and fix in Blender.
                if abs(s) > NDS_TEXCOORD_LIMIT or abs(t) > NDS_TEXCOORD_LIMIT:
                    warning = (
                        f"UV on '{obj.name}' (material '{material.name}') "
                        f"is out of the hardware's "
                        f"{NDS_TEXCOORD_LIMIT} pixel range: "
                        f"s={s:.2f}, t={t:.2f}. g3dcvtr will likely "
                        "reject this face with a texcoord error if the "
                        "UVs aren't fixed before converting. Exporting "
                        "it anyway."
                    )
                    logger.log(warning, debug_only=False)
                    # Collected so ExportNitro.execute() can surface a visible summary through Blender's own report system (status bar + Info log), not just the system console, which is easy to miss.
                    model.warnings.append(warning)

                primitive.add_command('tex', 'st', f'{s} {t}')

            # Color
            if (self.parent_polygon.use_clr
               and primitive._previous_clr != prim.colors[idx]):
                primitive._previous_clr = prim.colors[idx]
                r, g, b = prim.colors[idx]
                primitive.add_command('clr', 'rgb', f'{r} {g} {b}')

            # Normal
            if (self.parent_polygon.use_nrm
               and primitive._previous_nrm != prim.normals[idx]):
                primitive._previous_nrm = prim.normals[idx]
                normal = prim.normals[idx].to_vector()
                primitive.add_command('nrm', 'xyz',
                                      f'{normal.x} {normal.y} {normal.z}')

            # Recalculate vertex.
            scaled_vecfx32 = prim.positions[idx] >> model.info.pos_scale
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
        self.primitives.append(NitroModelPrimitive(type_))
        return self.primitives[-1]

    def set_initial_mtx(self):
        self.primitives[0].insert_mtx(0, 0)

    def optimize(self):
        previous_mtx = None
        for primitive in self.primitives:
            for command in primitive.commands:
                if command.type != 'mtx':
                    continue
                if previous_mtx == command.data:
                    primitive.commands.remove(command)
                else:
                    previous_mtx = command.data


class NitroModelPolygon():
    def __init__(self, index, name):
        self.index = index
        self.name = name
        self.use_nrm = False
        self.use_clr = False
        self.use_tex = False
        self.mtx_prims = []
        self.vertex_size = 0
        self.polygon_size = 0
        self.triangle_size = 0
        self.quad_size = 0

    def find_mtx_prim(self, index):
        for prim in self.mtx_prims:
            if prim.index == index:
                return prim
        index = len(self.mtx_prims)
        self.mtx_prims.append(NitroModelMtxPrim(index, self))
        return self.mtx_prims[-1]

    def collect_statistics(self):
        for mtx_prim in self.mtx_prims:
            for primitive in mtx_prim.primitives:
                self.vertex_size += primitive.vertex_size
                size = primitive.quad_size + primitive.triangle_size
                self.polygon_size += size
                self.triangle_size += primitive.triangle_size
                self.quad_size += primitive.quad_size

    def optimize(self):
        for mtx_prim in self.mtx_prims:
            mtx_prim.optimize()


class NitroModelDisplay():
    def __init__(self, index, material, polygon):
        self.index = index
        self.material = material
        self.polygon = polygon
        self.priority = 0


class NitroModelNode():
    def __init__(self, index, name):
        self.index = index
        self.name = name
        self.kind = 'null'
        self.parent = -1
        self.child = -1
        self.brother_next = -1
        self.brother_prev = -1
        self.draw_mtx = False
        self.billboard = 'off'
        self.scale = (1, 1, 1)
        self.rotate = (0, 0, 0)
        self.translate = (0, 0, 0)
        self.mtx = None
        self.visibility = True
        self.displays = []
        self.vertex_size = 0
        self.polygon_size = 0
        self.triangle_size = 0
        self.quad_size = 0

    def set_scale_rot_trans(self, mag):
        euler = self.mtx.to_euler('XYZ')
        self.rotate = [decimal.Decimal(math.degrees(e)) for e in euler]
        self.translate = self.mtx.to_translation() * mag
        self.scale = self.mtx.to_scale()

    def collect_statistics(self, model):
        for display in self.displays:
            polygon = model.polygons[display.polygon]
            self.vertex_size += polygon.vertex_size
            self.polygon_size += polygon.polygon_size
            self.triangle_size += polygon.triangle_size
            self.quad_size += polygon.quad_size

    def find_display(self, material_index, polygon_index):
        for display in self.displays:
            if (display.material == material_index
               and display.polygon == polygon_index):
                return display
        index = len(self.displays)
        self.displays.append(NitroModelDisplay(
            index, material_index, polygon_index))
        return self.displays[-1]


class NitroModelOutputInfo():
    def __init__(self):
        self.vertex_size = 0
        self.polygon_size = 0
        self.triangle_size = 0
        self.quad_size = 0

    def collect(self, model):
        for polygon in model.polygons:
            self.vertex_size += polygon.vertex_size
            size = polygon.quad_size + polygon.triangle_size
            self.polygon_size += size
            self.triangle_size += polygon.triangle_size
            self.quad_size += polygon.quad_size



class NitroModel():
    def __init__(self, settings):
        self.info = NitroModelInfo()
        self.box_test = NitroModelBoxTest()
        self.textures = []
        self.palettes = []
        self.materials = []
        self.matrices = []
        self.polygons = []
        self.nodes = []
        self.output_info = NitroModelOutputInfo()
        self.settings = settings
        # Array with primitives and their objects.
        self.primitives = []

        # Name of the always-present top-level node. Used to be hardcoded to 'root_scene' everywhere, now it's user-configurable (someone exporting several models wants a way to tell them apart at a glance instead of every single one showing "root_scene").
        self.root_name = settings.get('imd_root_name') or 'root_scene'

        # Non-fatal problems found while building the model (e.g. UVs outside the hardware's texcoord range). Always logged to the console/log file as they're found; also collected here so ExportNitro.execute() can show a visible summary through Blender's own report system once the export finishes.
        self.warnings = []

        # --- Lookup caches -------------------------------------------------
        # find_node/find_material/find_matrix/etc. used to be plain linear scans over the lists above. That's cheap when there are only a handful of nodes/materials, but find_matrix_by_node_name() is called *per vertex* while building primitives, so on any mesh with more than a trivial vertex count those linear scans dominated export time (O(vertices * nodes) or worse). These dicts mirror the lists and turn every "find_*" lookup below into O(1), while the public list attributes (self.nodes, self.materials, ...) keep working exactly as before for anything that iterates them.
        self._node_by_name = {}
        self._node_by_index = {}
        self._material_by_blender_index = {}
        self._matrix_by_node_idx = {}
        self._polygon_by_name = {}
        self._texture_by_path = {}

    def collect(self):
        if self.settings['imd_compress_nodes'] in ['none', 'cull', 'merge']:
            self.collect_none()
        elif self.settings['imd_compress_nodes'] == 'unite':
            self.collect_unite()
        elif self.settings['imd_compress_nodes'] == 'unite_combine':
            self.collect_unite_combine()

        # Sort and collect statistics.
        for polygon in self.polygons:
            polygon.collect_statistics()
            for mtx_prim in polygon.mtx_prims:
                mtx_prim.primitives.sort(key=lambda x: x.sort_key)
        for node in self.nodes:
            node.collect_statistics(self)

        self._apply_material_order()

        # Optimise polygons.
        for polygon in self.polygons:
            polygon.optimize()

        self.output_info.collect(self)
        self._check_hardware_limits()

    def _apply_material_order(self):
        if not self.materials:
            return

        def sort_key(pair):
            position, material = pair
            forced = getattr(
                bpy.data.materials[material.blender_index],
                'nns_material_id', -1)
            if forced is None or forced < 0:
                return (1, position, position)
            return (0, forced, position)

        ordered = [m for _, m in sorted(enumerate(self.materials), key=sort_key)]
        if all(m.index == i for i, m in enumerate(ordered)):
            return

        seen = {}
        for material in ordered:
            forced = getattr(
                bpy.data.materials[material.blender_index],
                'nns_material_id', -1)
            if forced is not None and forced >= 0:
                if forced in seen:
                    warning = (
                        "Materials '%s' and '%s' both use Material ID %d. "
                        "Give them different IDs, otherwise which one comes "
                        "first is left to Blender's own ordering."
                        % (seen[forced], material.name, forced))
                    logger.log(warning, debug_only=False)
                    self.warnings.append(warning)
                else:
                    seen[forced] = material.name

        remap = {}
        for new_index, material in enumerate(ordered):
            remap[material.index] = new_index
            material.index = new_index
        self.materials = ordered

        for node in self.nodes:
            for display in node.displays:
                display.material = remap.get(display.material, display.material)

        self._reorder_textures_and_palettes()

    def _reorder_textures_and_palettes(self):
        tex_order = []
        for material in self.materials:
            if material.image_idx >= 0 and material.image_idx not in tex_order:
                tex_order.append(material.image_idx)
        for i in range(len(self.textures)):
            if i not in tex_order:
                tex_order.append(i)

        if tex_order != list(range(len(self.textures))):
            tex_remap = {}
            new_textures = []
            for new_index, old_index in enumerate(tex_order):
                texture = self.textures[old_index]
                tex_remap[old_index] = new_index
                texture.index = new_index
                new_textures.append(texture)
            self.textures = new_textures
            for material in self.materials:
                if material.image_idx >= 0:
                    material.image_idx = tex_remap.get(
                        material.image_idx, material.image_idx)

        plt_order = []
        for material in self.materials:
            if material.palette_idx >= 0 and material.palette_idx not in plt_order:
                plt_order.append(material.palette_idx)
        for i in range(len(self.palettes)):
            if i not in plt_order:
                plt_order.append(i)

        if plt_order != list(range(len(self.palettes))):
            plt_remap = {}
            new_palettes = []
            for new_index, old_index in enumerate(plt_order):
                palette = self.palettes[old_index]
                plt_remap[old_index] = new_index
                palette.index = new_index
                new_palettes.append(palette)
            self.palettes = new_palettes
            for material in self.materials:
                if material.palette_idx >= 0:
                    material.palette_idx = plt_remap.get(
                        material.palette_idx, material.palette_idx)
            for texture in self.textures:
                if getattr(texture, 'palette_idx', -1) >= 0:
                    texture.palette_idx = plt_remap.get(
                        texture.palette_idx, texture.palette_idx)

    def _check_hardware_limits(self):
        # The DS geometry engine keeps a 31-entry stack for position/vector matrices. Every distinct bone/node this model actually binds a vertex to needs a slot in that stack while it's being drawn. This model doesn't get the stack to itself either. whatever else the game loads that frame (other models, the camera, ...) shares it too, so going over (or getting close to) 31 distinct matrices is a real, well-documented hardware ceiling, not just a rule of thumb.
        matrix_count = len(self.matrices)
        if matrix_count > NDS_MATRIX_STACK_DEPTH:
            warning = (
                f"This model uses {matrix_count} distinct bone/node "
                f"matrices, which is over the DS's "
                f"{NDS_MATRIX_STACK_DEPTH}-entry position matrix stack "
                "on its own, before anything else sharing the stack "
                "that frame. It'll likely glitch or fail to render "
                "correctly on real hardware. Exporting anyway."
            )
            logger.log(warning, debug_only=False)
            self.warnings.append(warning)

        # Unlike the matrix stack, there's no confirmed hard number here from g3dcvtr itself. this is a tunable warning about precision, not a known reject threshold. A model that needs a large pos_scale to fit its own bounding box (usually because one vertex sits much farther from the rest than everything else) loses position precision across the WHOLE model, not just near that vertex, since pos_scale applies uniformly.
        max_pos_scale = self.settings.get('imd_max_pos_scale', 8)
        if self.info.pos_scale > max_pos_scale:
            step = fx32_to_float(1 << self.info.pos_scale)
            warning = (
                f"This model needs a position scale of "
                f"{self.info.pos_scale} to fit its own bounding box "
                f"(over the {max_pos_scale} this is set to warn at), "
                f"which rounds every vertex position to steps of about "
                f"{step:.3f} world units. If that's much bigger than "
                "your smallest detail, check for a stray vertex placed "
                "far from the rest of the model. That alone can force "
                "this up for the entire mesh. Exporting anyway."
            )
            logger.log(warning, debug_only=False)
            self.warnings.append(warning)

        max_position = self.settings.get('imd_max_position', 4096.0)
        if max_position > 0 and self.info.max_coord > max_position:
            warning = (
                f"This model's largest vertex position is "
                f"{self.info.max_coord:.3f} units (after Magnification "
                f"is applied), over the {max_position:.3f} unit limit "
                "g3dcvtr enforces. This isn't a precision heads up like "
                "the position scale warning above, it's a hard reject: "
                "g3dcvtr will refuse to convert this file with a "
                "parameter out of bounds error. Lower Magnification or "
                "scale the model down in Blender to bring it back under "
                "the limit. Exporting anyway, but this file is expected "
                "to fail in g3dcvtr as-is."
            )
            logger.log(warning, debug_only=False)
            self.warnings.append(warning)


    def collect_none(self):
        root = self.find_node(self.root_name)
        root.rotate = tuple(
            math.degrees(a) for a in
            self.settings.get('imd_root_rotation', (math.radians(-90), 0, 0))
        )
        root_objects = []
        for obj in bpy.context.view_layer.objects:
            if obj.parent:
                continue
            if obj.type in ['EMPTY', 'ARMATURE', 'MESH']:
                root_objects.append(obj)
        children = self.process_children(root, root_objects)
        root.child = children[0].index if children else -1
        self.apply_transformations()
        self.info.calculate()
        for item in self.primitives:
            self.compile_primitives(
                item['primitives'],
                item['obj'],
                item['node'],
            )

        if self.settings['imd_compress_nodes'] in ['cull', 'merge']:
            self.cull_nodes()

    def cull_nodes(self):
        root = self.find_node(self.root_name)
        while True:
            node = self.get_childless_node()
            if node is not None:
                root.displays = node.displays
                self.remove_node(node)
            else:
                break
        child = self.find_node_by_index(root.child)
        if child.brother_next == -1:
            mtx = Matrix.Rotation(math.radians(-90), 4, 'X')
            child.mtx = mtx @ child.mtx
            child.set_scale_rot_trans(self.settings['imd_magnification'])
            child.displays = root.displays
            child.parent = -1
            self._discard_node(root)
        self._compact_node_indices()

    def _compact_node_indices(self):
        """Reassign node indices to a contiguous 0..N-1 range and fix up
        every child/parent/brother_next/brother_prev reference and every
        matrix's node_idx to match.

        This replaces a previous implementation that called
        node_replace_index() once per node, sequentially, while iterating
        self.nodes. That was buggy: as soon as one node got relabeled to a
        new index, that new index could collide with the *old* (not yet
        processed) index of a different node still waiting in the loop,
        because node_replace_index() matches purely on integer index
        values with no way to tell "old" and "new" apart mid-loop. A link
        that had already been correctly updated to point at the first
        node's new index could then be incorrectly rewritten again when the
        second node's turn came up, silently repointing it at the wrong
        node.

        Building the full old-index -> new-index map first (before
        mutating anything) and only then rewriting every reference in a
        single pass avoids that ambiguity entirely.
        """
        remap = {node.index: new_index
                  for new_index, node in enumerate(self.nodes)}

        def remapped(value):
            return remap[value] if value != -1 else -1

        for node in self.nodes:
            node.child = remapped(node.child)
            node.parent = remapped(node.parent)
            node.brother_next = remapped(node.brother_next)
            node.brother_prev = remapped(node.brother_prev)

        for matrix in self.matrices:
            if matrix.node_idx in remap:
                matrix.node_idx = remap[matrix.node_idx]

        for node in self.nodes:
            node.index = remap[node.index]

        # Rebuild the index-keyed caches from scratch, name-keyed ones (_node_by_name) are untouched since names didn't change.
        self._node_by_index = {node.index: node for node in self.nodes}
        self._matrix_by_node_idx = {
            matrix.node_idx: matrix for matrix in self.matrices
        }

    def collect_unite(self):
        root = self.find_node(self.root_name)
        for obj in bpy.context.view_layer.objects:
            if obj.type != 'MESH':
                continue
            self.process_mesh(root, obj)
        self.apply_transformations()
        self.info.calculate()
        for item in self.primitives:
            self.compile_primitives(
                item['primitives'],
                item['obj'],
                item['node'],
            )

    def collect_unite_combine(self):
        root = self.find_node(self.root_name)
        for obj in bpy.context.view_layer.objects:
            if obj.type != 'MESH':
                continue
            self.process_mesh(root, obj)
        self.apply_transformations()
        self.info.calculate()
        for item in self.primitives:
            self.compile_primitives_combined(
                item['primitives'],
                item['obj'],
                item['node'],
            )

    def compile_primitives_combined(self, primitives, obj, node):
        poly_mats = []
        for primitive in primitives:
            material = self.find_material(primitive.material_index)
            polygon = self.find_polygon('polygon' + str(material.index))
            poly_mats.append((polygon, material))
            mtx_prim = polygon.find_mtx_prim(0)
            mtx_prim.add_primitive(self, obj, primitive, material, node)
        for polygon, material in poly_mats:
            display = node.find_display(material.index, polygon.index)
            display.polygon = polygon.index

    def compile_primitives(self, primitives, obj, node):
        # A list of polygons and materials.
        poly_mats = []
        # Make materials and polygons and add the primitives to their respective mtx_prim elements.
        for primitive in primitives:
            material = self.find_material(primitive.material_index)
            polygon_name = obj.name + '_' + str(material.index)
            polygon = self.find_polygon(polygon_name)
            poly_mats.append((polygon, material))
            mtx_prim = polygon.find_mtx_prim(0)
            logger.log(f"Add primitive. {primitive.type}")
            mtx_prim.add_primitive(self, obj, primitive, material, node)
        # Hook up each polygon to the proper display depending on material index.
        for polygon, material in poly_mats:
            display = node.find_display(material.index, polygon.index)
            display.polygon = polygon.index

    def apply_transformations(self):
        # axis_conversion(...).to_4x4() only depends on the fixed '-Z'/'Y' arguments, never on the object or vertex, so it was being recomputed from scratch on every single vertex and every single normal for no reason when using the 'unite'/ 'unite_combine' node compression settings. Same for its per-object combination with obj.matrix_world and the quaternion derived from it, both only vary per object, not per vertex, so both get computed once per object now instead of once per vertex/normal.
        axis_transform = axis_conversion(to_forward='-Z', to_up='Y').to_4x4()
        compress = self.settings['imd_compress_nodes'] in ['unite', 'unite_combine']
        for item in self.primitives:
            obj = item['obj']
            if compress:
                obj_transform = axis_transform @ obj.matrix_world
                obj_quat = obj_transform.to_quaternion()
            for primitive in item['primitives']:
                for idx in range(len(primitive.positions)):
                    vertex = primitive.positions[idx].to_vector()
                    if compress:
                        vertex = obj_transform @ vertex
                    else:
                        matrix = None
                        group = primitive.groups[idx]
                        if group != -1:
                            name = obj.vertex_groups[group].name
                            matrix = self.find_matrix_by_node_name(name)
                        if matrix:
                            vertex = matrix.transform.inverted() @ vertex
                    vertex = vertex * self.settings['imd_magnification']
                    self.info.add(vertex)
                    vecfx32_vertex = VecFx32().from_vector(vertex)
                    primitive.positions[idx] = vecfx32_vertex
                for idx in range(len(primitive.normals)):
                    if compress:
                        normal = primitive.normals[idx].to_vector()
                        normal = obj_quat @ normal
                        primitive.normals[idx] = vector_to_vecfx10(normal)
                    else:
                        group = primitive.groups[idx]
                        if group != -1:
                            name = obj.vertex_groups[group].name
                            matrix = self.find_matrix_by_node_name(name)
                            normal = primitive.normals[idx].to_vector()
                            quat = matrix.transform.inverted().to_quaternion()
                            normal = quat @ normal
                            primitive.normals[idx] = vector_to_vecfx10(normal)

    def process_children(self, parent, objs, extra_mtx=None):
        """
        Recursively go through every child of every object.
        This will make a node for every object it will find, except for
        objects that get folded away as pass-through (see
        _process_object below): a skip-marked Empty, or (by default) an
        Armature object whose own transform is identity, since neither
        one carries any geometry of its own and both are otherwise pure
        overhead for hardware this limited.

        extra_mtx is an additional transform inherited from a
        pass-through ancestor that got folded away, it's composed into
        each direct child's own matrix so the end result is identical to
        what it would have been with the pass-through node still present.
        """
        if extra_mtx is None:
            extra_mtx = Matrix.Identity(4)

        objs = sort_by_node_id(
            objs, lambda o: getattr(o, 'nns_node_id', -1))

        brothers = []
        for obj in objs:
            brothers.extend(self._process_object(parent, obj, extra_mtx))

        length = len(brothers)

        for index, brother in enumerate(brothers):
            if index > 0:
                brother.brother_prev = brothers[index - 1].index
            if index < (length - 1):
                brother.brother_next = brothers[index + 1].index

        return brothers

    def _process_object(self, parent, obj, extra_mtx):
        """Process a single object and return the list of top-level
        NitroModelNode(s) it produced as direct siblings at this level of
        the hierarchy. This is normally exactly one node, but can be zero
        (a pass-through object with no children. it simply disappears)
        or more than one (a pass-through object's own children get
        spliced directly into the caller's sibling list, in its place).
        """
        if obj.type not in ['EMPTY', 'ARMATURE', 'MESH']:
            return []

        node_mode = self.settings.get('imd_node_mode', 'per_object')

        if obj.type == 'EMPTY' and (
                getattr(obj, 'nns_skip_node', False)
                or node_mode == 'bones_only'):
            combined_mtx = extra_mtx @ obj.matrix_basis
            result = []
            for child in sort_by_node_id(
                    obj.children, lambda o: getattr(o, 'nns_node_id', -1)):
                result.extend(self._process_object(
                    parent, child, combined_mtx))
            return result

        if obj.type == 'MESH' and node_mode == 'bones_only':
            # No node for this mesh, its own position/rotation/scale (plus anything inherited from a pass-through ancestor) gets baked directly into its vertex data instead, and its geometry is attached to the nearest real node above it (the root, or an enclosing bone) rather than a node of its own. This is what "bones only" node mode means: parent or weight-paint a mesh to a bone if it needs a node.
            combined_mtx = extra_mtx @ obj.matrix_basis
            if obj.nns_billboard in ['on', 'y_on']:
                logger.log(
                    f"'{obj.name}' has billboard enabled but node "
                    "creation is set to Bones only, so there's no node "
                    "for it to billboard. This setting will be ignored. "
                    "Parent or weight-paint it to a bone if you need it "
                    "to billboard.",
                    debug_only=False,
                )
            self.process_mesh(parent, obj, bake_mtx=combined_mtx)

            result = []
            for child in sort_by_node_id(
                    obj.children, lambda o: getattr(o, 'nns_node_id', -1)):
                result.extend(self._process_object(
                    parent, child, combined_mtx))
            return result

        if obj.type == 'ARMATURE':
            want_to_skip = (
                self.settings.get('imd_skip_identity_armature_node', True)
                or node_mode == 'bones_only'
            )
            already_identity = (
                is_identity_matrix(extra_mtx)
                and is_identity_matrix(obj.matrix_basis))

            # If the armature isn't at the origin yet, and there's no pass-through ancestor transform in the way (force-applying the armature's own transform can't fix an ancestor's), try applying its transform with Blender's own operator instead of just giving up on dropping its node. This is the the user is supposed to apply transforms anyway case: rather than requiring that as manual prep work, do it for them.
            if (want_to_skip and not already_identity
                    and is_identity_matrix(extra_mtx)
                    and self.settings.get(
                        'imd_force_apply_transforms', True)):
                force_apply_object_transform(obj)
                already_identity = is_identity_matrix(obj.matrix_basis)

            if want_to_skip and already_identity:
                # Nothing left to fold in, so splice its bones/children directly into the parent's child list instead of spending a node on the armature object itself.
                root_bones = []
                if obj.data.bones:
                    for bone in obj.data.bones:
                        if bone.parent is None:
                            root_bones.append(bone)
                bones = self.process_bones(parent, root_bones)

                children = []
                for child in sort_by_node_id(
                        obj.children,
                        lambda o: getattr(o, 'nns_node_id', -1)):
                    children.extend(
                        self._process_object(parent, child, extra_mtx))

                return bones + children

            if node_mode == 'bones_only' and not already_identity:
                # Either "Auto apply object transforms" is off, or applying the transform didn't leave it at the origin (a driver/constraint could prevent that, for example). We could still bake the remaining offset into every bone's bind matrix ourselves, but that math feeds directly into skin deformation. getting it wrong would distort the mesh in a way that's easy to miss until it's animated. Keeping the node here is the safe choice.
                logger.log(
                    f"'{obj.name}' isn't at the origin (no rotation, no "
                    "scale), so it still gets a node even with Bones "
                    "only selected. Turn on 'Auto apply object "
                    "transforms', or apply its transform yourself "
                    "(Ctrl+A in the viewport), to remove it.",
                    debug_only=False,
                )

        node = self.find_node(obj.name)

        # Transform, is equal for all objects. Also store the matrix for culling and merging.
        node.mtx = extra_mtx @ obj.matrix_basis
        node.set_scale_rot_trans(self.settings['imd_magnification'])

        if obj.type == 'EMPTY':
            children = self.process_children(node, obj.children)
            if children:
                node.child = children[0].index

        elif obj.type == 'ARMATURE':
            # Process bones first.
            root_bones = []

            if obj.data.bones:
                for bone in obj.data.bones:
                    if bone.parent is None:
                        root_bones.append(bone)
            bones = self.process_bones(node, root_bones)

            # Process children and add bones.
            children = self.process_children(node, obj.children)

            if bones:
                if children:
                    bones[-1].brother_next = children[0].index
                    children[0].brother_prev = bones[-1].index
                    children = bones + children
                else:
                    children.extend(bones)

            if children:
                node.child = children[0].index

        elif obj.type == 'MESH':
            node.kind = 'mesh'
            node.billboard = obj.nns_billboard
            if node.billboard in ['on', 'y_on']:
                # Not sure if this is a good fix.
                mtx = Matrix.Rotation(math.radians(-90), 4, 'X')
                node.mtx = node.mtx @ mtx
                node.set_scale_rot_trans(self.settings['imd_magnification'])
            self.process_mesh(node, obj)
            children = self.process_children(node, obj.children)
            if children:
                node.child = children[0].index

        node.parent = parent.index
        return [node]

    def process_bones(self, parent, bones):
        bones = sort_by_node_id(
            bones, lambda b: getattr(b, 'nns_node_id', -1))

        brothers = []

        for bone in bones:
            node = self.find_node(bone.name)
            node.kind = 'joint'

            # Make matrix for node.
            self.find_matrix(node.index, bone.matrix_local.copy())

            # Calculate transform.
            transform = bone.matrix_local if bone else Matrix.Identity(4)
            if bone and bone.parent:
                transform = bone.parent.matrix_local.inverted() @ transform

            # Transform node.
            euler = transform.to_euler('XYZ')
            node.rotate = [decimal.Decimal(math.degrees(e)) for e in euler]
            mag = self.settings['imd_magnification']
            node.translate = transform.to_translation() * mag

            # Get children.
            children = self.process_bones(node, bone.children)
            if children:
                node.child = children[0].index
            node.parent = parent.index

            brothers.append(node)

        length = len(brothers)

        for index, brother in enumerate(brothers):
            if index > 0:
                brother.brother_prev = brothers[index - 1].index
            if index < (length - 1):
                brother.brother_next = brothers[index + 1].index

        return brothers

    def process_mesh(self, node, obj, bake_mtx=None):
        primitives = []

        # fix copied from fast64 repo, in blender version 4.1 func was removed, in 4.1+ normals are always calculated
        if bpy.app.version < (4, 1, 0):
            obj.data.calc_normals_split()

        triangulate_quads = self.settings.get('imd_triangulate_quads', False)
        flatness_tolerance = self.settings.get(
            'imd_quad_flatness_tolerance', 5.0)

        needs_baking = (
            bake_mtx is not None and not is_identity_matrix(bake_mtx))

        for polygon in obj.data.polygons:
            if len(polygon.loop_indices) < 3:
                logger.log("Polygon is a line. Skipped.")
                continue
            index = get_global_mat_index(obj, polygon.material_index)
            if index == -1:
                logger.log("Polygon doesn't have material. Skipped.")
                continue

            prim = Primitive(obj, polygon)

            if needs_baking:
                bake_primitive_transform(prim, bake_mtx)

            # Real hardware doesn't support n-gons at all, so those always get triangulated (using Blender's own polygon tessellation, which handles concave n-gons correctly). Quads are left untouched by default even if they're not flat. whether to auto-fix those is the person's call, made with "Triangulate non-planar quads" above, since changing quads without being asked isn't something this addon should just do on its own.
            if prim.vertex_count > 4:
                primitives.extend(triangulate_primitive(prim))
                logger.log(f"Ngon triangulated ({prim.vertex_count} sides).")
            elif (prim.vertex_count == 4 and triangulate_quads
                    and not is_quad_flat(
                        obj, polygon, flatness_tolerance)):
                primitives.extend(triangulate_primitive(prim))
                logger.log("Non-planar quad triangulated.")
            else:
                primitives.append(prim)

        if self.settings['imd_use_primitive_strip']:
            quad_stripper = QuadStripper()
            primitives = quad_stripper.process(primitives)

            tri_stripper = TriStripper()
            primitives = tri_stripper.process(primitives)

        self.primitives.append({
            'obj': obj,
            'node': node,
            'primitives': primitives
        })

    def add_palette(self, name, data, size):
        self.palettes.append(
            NitroModelPalette(name, data, size, len(self.palettes)))
        return self.palettes[-1]

    def find_texture(self, path):
        texture = self._texture_by_path.get(path)
        if texture is not None:
            return texture
        texture = NitroModelTexture(self, path, len(self.textures))
        self.textures.append(texture)
        self._texture_by_path[path] = texture
        return texture

    def find_material(self, blender_index):
        material = self._material_by_blender_index.get(blender_index)
        if material is not None:
            return material
        index = len(self.materials)
        material = NitroModelMaterial(self, blender_index, index)
        self.materials.append(material)
        self._material_by_blender_index[blender_index] = material
        return material

    def find_matrix(self, node_idx, matrix_):
        matrix = self._matrix_by_node_idx.get(node_idx)
        if matrix is not None:
            return matrix
        index = len(self.matrices)
        matrix = NitroModelMatrix(index, node_idx, matrix_)
        self.matrices.append(matrix)
        self._matrix_by_node_idx[node_idx] = matrix
        return matrix

    def find_matrix_by_node_name(self, name):
        node = self._node_by_name.get(name)
        if node is None:
            raise ValueError(
                f"'{name}' is used as a vertex group name but there's no "
                "node with that name in the exported model. This usually "
                "means a bone was deleted without also deleting or "
                "renaming the vertex group that referenced it."
            )
        matrix = self._matrix_by_node_idx.get(node.index)
        if matrix is not None:
            return matrix
        return self.find_matrix(node.index, Matrix.Identity(4))

    def get_childless_node(self):
        for node in self.nodes:
            if node.child == -1 and not self.node_has_matrix(node):
                return node
        return None

    def remove_node(self, node):
        for other in self.nodes:
            if other.child == node.index:
                if node.brother_next == -1:
                    other.child = -1
                else:
                    other.child = node.brother_next
            if other.brother_next == node.index:
                other.brother_next = node.brother_next
            if other.brother_prev == node.index:
                other.brother_prev = node.brother_prev
            if other.parent == node.index:
                raise Exception("Attempting to delete a parent node")
        self._discard_node(node)

    def _discard_node(self, node):
        """Remove a node from the model's list and lookup caches only. Does
        not touch other nodes' child/parent/brother links. callers are
        responsible for that (remove_node() does it above; cull_nodes()
        handles the root node specially before calling this)."""
        self.nodes.remove(node)
        if self._node_by_name.get(node.name) is node:
            del self._node_by_name[node.name]
        if self._node_by_index.get(node.index) is node:
            del self._node_by_index[node.index]

    def node_replace_index(self, node, index):
        for other in self.nodes:
            if other.index == node.index:
                continue
            if other.child == node.index:
                other.child = index
            if other.brother_next == node.index:
                other.brother_next = index
            if other.brother_prev == node.index:
                other.brother_prev = index
            if other.parent == node.index:
                other.parent = index
        for matrix in self.matrices:
            if matrix.node_idx == node.index:
                matrix.node_idx = index
        old_index = node.index
        node.index = index
        if self._node_by_index.get(old_index) is node:
            del self._node_by_index[old_index]
        self._node_by_index[index] = node
        matrix = self._matrix_by_node_idx.pop(old_index, None)
        if matrix is not None:
            self._matrix_by_node_idx[index] = matrix

    def node_has_matrix(self, node):
        return node.index in self._matrix_by_node_idx

    def find_polygon(self, name):
        polygon = self._polygon_by_name.get(name)
        if polygon is not None:
            return polygon
        index = len(self.polygons)
        polygon = NitroModelPolygon(index, name)
        self.polygons.append(polygon)
        self._polygon_by_name[name] = polygon
        return polygon

    def find_node(self, name):
        node = self._node_by_name.get(name)
        if node is not None:
            return node
        index = len(self.nodes)
        node = NitroModelNode(index, name)
        self.nodes.append(node)
        self._node_by_name[name] = node
        self._node_by_index[index] = node
        return node

    def find_node_by_index(self, index):
        return self._node_by_index.get(index)
