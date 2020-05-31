import os
import bpy
from bpy_extras import node_shader_utils
from .util import *
from .primitive import *
from . import local_logger as logger
from . import nitro_tga


class NitroModelInfo():
    def __init__(self, global_matrix):
        box = get_all_max_min(global_matrix)
        max_max = abs(max(box['max'].x, box['max'].y, box['max'].z))
        min_min = abs(min(box['min'].x, box['min'].y, box['min'].z))
        max_coord = max(max_max, min_min)
        self.pos_scale = calculate_pos_scale(max_coord)


class NitroModelBoxTest():
    def __init__(self, global_matrix):
        box = get_all_max_min(global_matrix)
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
                [str(int(lin2s(x) * 31)) for x in material.nns_diffuse])
            self.specular = ' '.join(
                [str(int(lin2s(x) * 31)) for x in material.nns_specular])
            self.ambient = ' '.join(
                [str(int(lin2s(x) * 31)) for x in material.nns_ambient])
            self.emission = ' '.join(
                [str(int(lin2s(x) * 31)) for x in material.nns_emission])
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
                str(int(lin2s(wrap.base_color[0]) * 31)),
                str(int(lin2s(wrap.base_color[1]) * 31)),
                str(int(lin2s(wrap.base_color[2]) * 31))
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


class NitroModelMatrix():
    def __init__(self, index):
        self.index = index
        self.weight = 1
        self.node_idx = 0


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


class NitroModelMtxPrim():
    def __init__(self, index):
        self.index = index
        self.use_normals = False
        self.use_colors = False
        self.use_texcoords = False
        self.mtx_list = []
        self.primitives = []

    def add_matrix_reference(self, index):
        if index not in self.mtx_list:
            self.mtx_list.append(index)
    
    def add_primitive(self, obj, prim: Primitive, material):
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

        if len(obj.data.vertex_colors) > 0 and "vc" in material.type:
            self.use_colors = True

        if material.image_idx != -1 and "tx" in material.type and \
                material.tex_gen_mode != "nrm":
            self.use_texcoords = True

        if ((material.light0 == 'on' or
            material.light1 == 'on' or
            material.light2 == 'on' or
            material.light3 == 'on') and "nr" in material.type) or \
                material.tex_gen_mode == "nrm":
            self.use_normals = True

        for idx in range(len(prim.positions)):
            # Color
            if self.use_colors:
                r, g, b = prim.colors[idx]
                primitive.add_command('clr', 'rgb', f'{r} {g} {b}')

            # Normal
            if self.use_normals:
                normal = prim.normals[idx].to_vector()
                primitive.add_command('nrm', 'xyz',
                                      f'{normal.x} {normal.y} {normal.z}')

            # Texture coordinate.
            if self.use_texcoords:
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
        self.primitives.append(NitroModelPrimitive(type_))
        return self.primitives[-1]

    def set_initial_mtx(self):
        self.primitives[0].insert_mtx(0, 0)


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
        self.mtx_prims.append(NitroModelMtxPrim(index))
        return self.mtx_prims[-1]
    
    def collect_statistics(self):
        for mtx_prim in self.mtx_prims:
            for primitive in mtx_prim.primitives:
                self.vertex_size += primitive.vertex_size
                size = primitive.quad_size + primitive.triangle_size
                self.polygon_size += size
                self.triangle_size += primitive.triangle_size
                self.quad_size += primitive.quad_size


class NitroModelDisplay():
    def __init__(self, index, material):
        self.index = index
        self.material = material
        self.polygon = -1
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
        self.billboard = False
        self.scale = (1, 1, 1)
        self.rotate = (0, 0, 0)
        self.translate = (0, 0, 0)
        self.visibility = True
        self.displays = []
        self.vertex_size = 0
        self.polygon_size = 0
        self.triangle_size = 0
        self.quad_size = 0
    
    def collect_statistics(self, model):
        for display in self.displays:
            polygon = model.polygons[display.polygon]
            self.vertex_size += polygon.vertex_size
            self.polygon_size += polygon.polygon_size
            self.triangle_size += polygon.triangle_size
            self.quad_size += polygon.quad_size

    def find_display(self, material_index):
        for display in self.displays:
            if display.material == material_index:
                return display
        index = len(self.displays)
        self.displays.append(NitroModelDisplay(index, material_index))
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
    def __init__(self, global_matrix, settings):
        self.info = NitroModelInfo(global_matrix)
        self.box_test = NitroModelBoxTest(global_matrix)
        self.textures = []
        self.palettes = []
        self.materials = []
        self.matrices = []
        self.polygons = []
        self.nodes = []
        self.output_info = NitroModelOutputInfo()
        self.global_matrix = global_matrix
        self.settings = settings
    
    def collect(self):
        root = self.find_node('root')
        root_objects = []
        for obj in bpy.context.view_layer.objects:
            if obj.parent:
                continue
            if obj.type == 'EMPTY' or obj.type == 'ARMATURE' or obj.type == 'MESH':
                root_objects.append(obj)
        children = self.process_children(root, root_objects)
        root.child = children[0].index

        # Sort and collect statistics.
        for polygon in self.polygons:
            polygon.collect_statistics()
            for mtx_prim in polygon.mtx_prims:
                mtx_prim.primitives.sort(key=lambda x: x.sort_key)
                mtx_prim.set_initial_mtx()
        for node in self.nodes:
            node.collect_statistics(self)
        self.output_info.collect(self)
    
    def process_children(self, parent, objs):
        """
        Recursively go through every child of every object.
        This will make a node for every object it will find.
        """
        brothers = []
        for obj in objs:
            if obj.type == 'EMPTY' or obj.type == 'ARMATURE':
                node = self.find_node(obj.name)
                children = self.process_children(node, obj.children)
                if children:
                    node.child = children[0].index
                node.parent = parent.index
                brothers.append(node)
            elif obj.type == 'MESH':
                node = self.find_node(obj.name)
                node.kind = 'mesh'
                self.process_mesh(node, obj)
                children = self.process_children(node, obj.children)
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
    
    def process_mesh(self, node, obj):
        primitives = []
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
            # ADD pos_scale
            pos_scale = self.info.pos_scale
            primitives.append(Primitive(
                self.global_matrix, pos_scale, obj, polygon))

        if self.settings['imd_use_primitive_strip']:
            quad_stripper = QuadStripper()
            primitives = quad_stripper.process(primitives)

            tri_stripper = TriStripper()
            primitives = tri_stripper.process(primitives)
        
        poly_mats = []
        for primitive in primitives:
            material = self.find_material(primitive.material_index)
            polygon_name = obj.name + '_' + str(material.index)
            polygon = self.find_polygon(polygon_name)
            poly_mats.append((polygon, material))
            mtx_prim = polygon.find_mtx_prim(0)
            # This is stupid and it should change.
            # Perhaps a matrix should be found based on the node index?
            matrix = self.find_matrix(0)
            mtx_prim.add_matrix_reference(matrix.index)
            logger.log(f"Add primitive. {primitive.type}")
            mtx_prim.add_primitive(obj, primitive, material)
        
        for polygon, material in poly_mats:
            display = node.find_display(material.index)
            display.polygon = polygon.index

    def add_palette(self, name, data, size):
        self.palettes.append(
            NitroModelPalette(name, data, size, len(self.palettes)))
        return self.palettes[-1]

    def find_texture(self, path):
        for texture in self.textures:
            if texture.path == path:
                return texture
        self.textures.append(NitroModelTexture(path, len(self.textures)))
        return self.textures[-1]

    def find_material(self, blender_index):
        for material in self.materials:
            if material.blender_index == blender_index:
                return material
        index = len(self.materials)
        self.materials.append(NitroModelMaterial(self, blender_index, index))
        return self.materials[-1]

    def find_matrix(self, index):
        for matrix in self.matrices:
            if matrix.index == index:
                return matrix
        index = len(self.matrices)
        self.matrices.append(NitroModelMatrix(index))
        return self.matrices[-1]

    def find_polygon(self, name):
        for polygon in self.polygons:
            if polygon.name == name:
                return polygon
        index = len(self.polygons)
        self.polygons.append(NitroModelPolygon(index, name))
        return self.polygons[-1]

    def find_node(self, name):
        for node in self.nodes:
            if node.name == name:
                return display
        index = len(self.nodes)
        self.nodes.append(NitroModelNode(index, name))
        return self.nodes[-1]
