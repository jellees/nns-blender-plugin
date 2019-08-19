import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty, EnumProperty


bl_info = {
    "name": "Nitro IMD (.imd)",
    "author": "Jelle Streekstra",
    "version": (0, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "description": "Export Nitro IMD",
    "category": "Import-Export"
}


class ExportNitro(bpy.types.Operator):
    bl_idname = "export.nitro"
    bl_label = "Export Nitro"

    filepath = StringProperty(subtype="FILE_PATH")

    pretty_print = BoolProperty(name="Pretty print", default=True)

    def execute(self, context):
        from . import export_nitro
        keywords = self.as_keywords()
        export_nitro.save(context, **keywords)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def menu_func_export(self, context):
    self.layout.operator(ExportNitro.bl_idname, text="Nitro IMD (.imd)")


def register():
    bpy.utils.register_class(ExportNitro)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportNitro)

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
