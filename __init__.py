import bpy
from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty)
from bpy_extras.io_utils import ExportHelper
from .nns_material import material_register, material_unregister
from .nns_object import object_register, object_unregister


bl_info = {
    "name": "Nitro Intermediate (.imd, .ita, .ica)",
    "author": "Jelle Streekstra, Gabriele Mercurio",
    "version": (0, 0, 3),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "description": "Export intermediate files for Nitro system",
    "category": "Import-Export"
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
        # layout.prop(operator, 'ita_rotate_tolerance')
        # layout.prop(operator, 'ita_scale_tolerance')
        # layout.prop(operator, 'ita_translate_tolerance')


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


class ExportNitro(bpy.types.Operator, ExportHelper):
    bl_idname = "export.nitro"
    bl_label = "Export Nitro"

    filename_ext = ""
    filter_glob: StringProperty(
        default="*.imd;*.ita",
        options={'HIDDEN'},
        )

    pretty_print = BoolProperty(name="Pretty print", default=True)

    generate_log = BoolProperty(name="Generate log file", default=False)

    imd_export = BoolProperty(name="Export .imd", default=True)
    imd_magnification = FloatProperty(name="Magnification",
                                      default=0.0625,
                                      precision=4)
    imd_use_primitive_strip = BoolProperty(name="Use primitive strip",
                                           default=True)
    imd_compress_nodes = EnumProperty(
        name="Compress nodes",
        items=[
            ("none", "None", '', 1),
            ("unite", "Unite", '', 2),
            ("unite_combine", "Unite and combine polygon", '', 3),
        ])

    ita_export = BoolProperty(name="Export .ita")
    ita_rotate_tolerance = FloatProperty(name="Rotation tolerance",
                                         default=0.100000,
                                         precision=6)
    ita_scale_tolerance = FloatProperty(name="Scale tolerance",
                                        default=0.100000,
                                        precision=6)
    ita_translate_tolerance = FloatProperty(name="Translation tolerance",
                                            default=0.010000,
                                            precision=6)

    ica_export = BoolProperty(name="Export .ica")

    def execute(self, context):
        from . import export_nitro

        settings = self.as_keywords()
        export_nitro.save(context, settings)
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
        text="Nitro Intermediate (.imd, .ita, .ica)")


def register():
    bpy.utils.register_class(ExportNitro)
    bpy.utils.register_class(NTR_PT_export_imd)
    bpy.utils.register_class(NTR_PT_export_ita)
    bpy.utils.register_class(NTR_PT_export_ica)
    material_register()
    object_register()

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportNitro)
    bpy.utils.unregister_class(NTR_PT_export_imd)
    bpy.utils.unregister_class(NTR_PT_export_ita)
    bpy.utils.unregister_class(NTR_PT_export_ica)
    material_unregister()
    object_unregister()

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
