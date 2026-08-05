import bpy
import math
from bpy.props import (BoolProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       IntProperty,
                       StringProperty,
                       EnumProperty)
from bpy_extras.io_utils import ExportHelper
from .nns_material import material_register, material_unregister
from .nns_object import object_register, object_unregister
from .nns_bounds import bounds_register, bounds_unregister
from .util import safe_register_class
from . import version


bl_info = {
    "name": "NNS Nitro Intermediate Exporter",
    "author": "Jelle, Ermelber, Perlite, Golden Glitch",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Export",
    "description": (
        "Export models, textures, and animations to Nitro (Nintendo DS) "
        "intermediate formats"
    ),
    "category": "Export"
}


class NTR_PT_export_imd(bpy.types.Panel):
    """Export to a Nitro Intermediate"""

    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Intermediate Model Data (.imd)"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_nitro"

    def draw(self, context):
        layout = self.layout
        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'imd_export')
        layout.prop(operator, 'imd_magnification')
        layout.prop(operator, 'imd_use_primitive_strip')
        layout.prop(operator, 'imd_compress_nodes')
        layout.prop(operator, 'imd_root_name')
        layout.prop(operator, 'imd_root_rotation')
        layout.prop(operator, 'imd_node_mode')
        layout.prop(operator, 'imd_skip_identity_armature_node')
        layout.prop(operator, 'imd_force_apply_transforms')
        layout.prop(operator, 'imd_triangulate_quads')
        if operator.imd_triangulate_quads:
            layout.prop(operator, 'imd_quad_flatness_tolerance')
        layout.prop(operator, 'imd_max_pos_scale')


class NTR_PT_export_ita(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Intermediate Texture Animation (.ita)"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_nitro"

    def draw(self, context):
        layout = self.layout
        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'ita_export')
        layout.prop(operator, 'ita_rotate_tolerance')
        layout.prop(operator, 'ita_scale_tolerance')
        layout.prop(operator, 'ita_translate_tolerance')


class NTR_PT_export_ica(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Intermediate Character Animation (.ica)"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_nitro"

    def draw(self, context):
        layout = self.layout
        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'ica_export')
        layout.prop(operator, 'ica_frame_step')
        layout.prop(operator, 'ica_rotate_tolerance')
        layout.prop(operator, 'ica_scale_tolerance')
        layout.prop(operator, 'ica_translate_tolerance')


class NTR_PT_export_itp(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Intermediate Texture Pattern (.itp)"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_nitro"

    def draw(self, context):
        layout = self.layout
        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'itp_export')


class NTR_PT_export_ima(bpy.types.Panel):
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Intermediate Material Animation (.ima)"
    bl_parent_id = "FILE_PT_operator"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        sfile = context.space_data
        operator = sfile.active_operator

        return operator.bl_idname == "EXPORT_OT_nitro"

    def draw(self, context):
        layout = self.layout
        sfile = context.space_data
        operator = sfile.active_operator

        layout.prop(operator, 'ima_export')
        layout.prop(operator, 'ima_tolerance_color')


class ExportNitro(bpy.types.Operator, ExportHelper):
    bl_idname = "export.nitro"
    bl_label = "Export Nitro"
    bl_options = {'PRESET'}

    filename_ext = ""
    filter_glob: StringProperty(
        default="*.imd;*.ita;*.ica;*.itp;*.ima",
        options={'HIDDEN'},
        )

    pretty_print: BoolProperty(name="Pretty print", default=True)

    generate_log: BoolProperty(name="Generate log file", default=False)

    imd_export: BoolProperty(name="Export .imd", default=True)
    imd_magnification: FloatProperty(name="Magnification",
                                     default=0.0625,
                                     precision=4)
    imd_use_primitive_strip: BoolProperty(name="Use primitive strip",
                                          default=True)
    imd_compress_nodes: EnumProperty(
        name="Compress nodes",
        items=[
            ("none", "None", '', 1),
            ("cull", "Cull", '', 2),
            ("merge", "Merge", '', 3),
            ("unite", "Unite", '', 4),
            ("unite_combine", "Unite and combine polygon", '', 5),
        ])
    imd_root_name: StringProperty(
        name="Root node name",
        description=(
            "Name for the top level node the exporter always creates. "
            "Rename it if you want it to follow your own naming scheme, "
            "or just to tell exported models apart at a glance"
        ),
        default="root_scene")
    imd_root_rotation: FloatVectorProperty(
        name="Root rotation",
        description=(
            "Rotation baked into the top level node. This is what lines "
            "the model up correctly on hardware; the default (-90 on X) "
            "is right for most models, but if one of yours comes out "
            "rotated 90 degrees on an axis it shouldn't be, try changing "
            "this instead of rotating the mesh itself"
        ),
        subtype='EULER',
        size=3,
        default=(math.radians(-90), 0.0, 0.0))
    imd_node_mode: EnumProperty(
        name="Node creation",
        description="Which objects get turned into their own node",
        items=[
            ("per_object", "One per object",
             "Every Empty and Mesh becomes its own node, same as "
             "Blender's outliner. An Armature gets one too, unless "
             "Skip redundant armature node (below) removes it. This is "
             "the classic behavior", 1),
            ("bones_only", "Bones only",
             "Only the root node and bones become nodes. Empties and "
             "Meshes don't get one; their position, rotation and scale "
             "get baked straight into the geometry instead. This is how "
             "the original NSBMD models are built. If a specific part "
             "needs its own node (for a runtime effect, a visibility "
             "toggle, etc), parent or weight paint it to a bone instead",
             2),
        ],
        default="per_object")
    imd_skip_identity_armature_node: BoolProperty(
        name="Skip redundant armature node",
        description=(
            "An Armature always gets its own node on top of the nodes "
            "for its bones, even though the armature itself has no "
            "geometry. That's a wasted node on hardware this limited. "
            "If the armature sits at the origin with no rotation or "
            "scale, this skips its node and attaches its bones straight "
            "to its parent, with no visible change to the model. See "
            "'Auto apply object transforms' below if you want that to "
            "happen even when the armature isn't at the origin yet"
        ),
        default=True)
    imd_force_apply_transforms: BoolProperty(
        name="Auto apply object transforms",
        description=(
            "An Armature only avoids getting its own wasted node (see "
            "above) when it sits at the origin with no rotation or "
            "scale. Rather than leaving that up to you, this applies the "
            "armature's transform for you before exporting, the same as "
            "pressing Ctrl+A > All Transforms in the viewport, so the "
            "node gets dropped either way. The model looks exactly the "
            "same afterward; only the armature's location/rotation/scale "
            "values reset to zero, same as if you'd applied them "
            "yourself"
        ),
        default=True)
    imd_triangulate_quads: BoolProperty(
        name="Triangulate non-planar quads",
        description=(
            "A quad that isn't flat renders wrong on real hardware, "
            "which only draws flat quads correctly. Turning this on "
            "checks every quad and automatically splits the ones that "
            "aren't flat enough into two triangles. Off by default so "
            "quads only get changed with your say-so; N-gons (5+ sided "
            "faces) always get triangulated regardless of this setting, "
            "since the hardware can't draw those at all no matter what"
        ),
        default=False)
    imd_quad_flatness_tolerance: FloatProperty(
        name="Quad flatness tolerance (degrees)",
        description=(
            "How far a quad is allowed to bend before it gets split "
            "into two triangles"
        ),
        default=5.0,
        min=0.0,
        max=90.0,
        precision=2)
    imd_max_pos_scale: IntProperty(
        name="Max position scale warning",
        description=(
            "A model needs a bigger position scale the bigger its "
            "bounding box is, and a bigger scale means coarser position "
            "precision for the WHOLE model, not just the far away part. "
            "You'll get a warning if the model needs more than this. "
            "There's no confirmed hard limit here (unlike the texcoord "
            "one above), this is just a heads up that something's "
            "probably placed way outside where the rest of the model "
            "is, tune it to whatever's actually a problem for you"
        ),
        default=8,
        min=0,
        max=31)

    ita_export: BoolProperty(name="Export .ita")
    ita_rotate_tolerance: FloatProperty(
        name="Rotation tolerance",
        description=(
            "How much a texture's rotation keyframes can drift from a "
            "straight line before they're kept as real animation data. "
            "Smaller keeps more detail, bigger makes a smaller file"
        ),
        default=0.100000,
        precision=6)
    ita_scale_tolerance: FloatProperty(
        name="Scale tolerance",
        description=(
            "Same idea as rotation tolerance, but for texture scale "
            "keyframes"
        ),
        default=0.100000,
        precision=6)
    ita_translate_tolerance: FloatProperty(
        name="Translation tolerance",
        description=(
            "Same idea as rotation tolerance, but for texture position "
            "(scroll) keyframes"
        ),
        default=0.010000,
        precision=6)

    ica_export: BoolProperty(name="Export .ica")
    ica_frame_step: EnumProperty(
        name="Frame step mode",
        items=[
            ("1", "1", '', 1),
            ("2", "2", '', 2),
            ("4", "4", '', 3),
        ])
    ica_rotate_tolerance: FloatProperty(name="Rotation tolerance",
                                        default=0.100000,
                                        precision=6)
    ica_scale_tolerance: FloatProperty(name="Scale tolerance",
                                       default=0.100000,
                                       precision=6)
    ica_translate_tolerance: FloatProperty(name="Translation tolerance",
                                           default=0.010000,
                                           precision=6)

    itp_export: BoolProperty(name="Export .itp")

    ima_export: BoolProperty(name="Export .ima")
    ima_tolerance_color: IntProperty(
        name="Color tolerance",
        description=(
            "How close a channel's animated values need to stay to "
            "count as \"not really animated.\" A material color channel "
            "that never strays further than this from its starting "
            "value gets written as one constant value instead of a full "
            "per frame animation, keeping the file smaller. Raise this "
            "if a channel with tiny keyframe noise is bloating the file "
            "for no visual difference"
        ),
        default=2,
        min=0,
        max=31)

    # Blender's context.mode strings (e.g. 'EDIT_MESH', 'PAINT_VERTEX') don't match what bpy.ops.object.mode_set(mode=...) expects (e.g. 'EDIT', 'VERTEX_PAINT'), see force_object_mode() in util.py, which handles this for both this operator and the bounds tools.

    def execute(self, context):
        from . import export_nitro
        from .util import force_object_mode

        # See force_object_mode()'s docstring in util.py: exporting while still in Edit Mode corrupted the output.
        with force_object_mode(context):
            settings = self.as_keywords()
            warnings = export_nitro.save(context, settings)
            self.report({'INFO'}, 'NNS: Exported scene.')
            if warnings:
                # Every individual warning is already in the console/log file (see local_logger), this is just a visible pointer that something needs a look, shown right in Blender's UI (status bar + Info log) instead of only somewhere the person might not be watching.
                count = len(warnings)
                noun = 'issue' if count == 1 else 'issues'
                self.report(
                    {'WARNING'},
                    f"NNS: {count} {noun} found during export (see the "
                    "system console, or turn on 'Generate log file' for "
                    "details).",
                )

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        sfile = context.space_data
        operator = sfile.active_operator
        layout.prop(operator, 'pretty_print')
        layout.prop(operator, 'generate_log')


def menu_func_export(self, context):
    self.layout.operator(
        ExportNitro.bl_idname,
        text="NNS Nitro Intermediate")


def register():
    version.addon_version = bl_info["version"]
    safe_register_class(ExportNitro)
    safe_register_class(NTR_PT_export_imd)
    safe_register_class(NTR_PT_export_ita)
    safe_register_class(NTR_PT_export_ica)
    safe_register_class(NTR_PT_export_itp)
    safe_register_class(NTR_PT_export_ima)
    material_register()
    object_register()
    bounds_register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportNitro)
    bpy.utils.unregister_class(NTR_PT_export_imd)
    bpy.utils.unregister_class(NTR_PT_export_ita)
    bpy.utils.unregister_class(NTR_PT_export_ica)
    bpy.utils.unregister_class(NTR_PT_export_itp)
    bpy.utils.unregister_class(NTR_PT_export_ima)
    material_unregister()
    object_unregister()
    bounds_unregister()
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
