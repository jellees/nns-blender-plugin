import bpy
from bpy.props import (BoolProperty,
                       FloatProperty,
                       StringProperty,
                       EnumProperty,
                       IntProperty,
                       FloatVectorProperty)


bl_info = {
    "name": "Nitro IMD (.imd)",
    "author": "Jelle Streekstra, Gabriele Mercurio",
    "version": (0, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Import-Export",
    "description": "Export Nitro IMD",
    "category": "Import-Export"
}


class NTR_PT_material(bpy.types.Panel):
    bl_label = "NNS Material Options"
    bl_idname = "MATERIAL_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        row = layout.row(align=True)
        row.prop(mat, "nns_light0", toggle=True)
        row.prop(mat, "nns_light1", toggle=True)
        row.prop(mat, "nns_light2", toggle=True)
        row.prop(mat, "nns_light3", toggle=True)
        layout.prop(mat, "nns_use_srst")
        layout.prop(mat, "nns_fog")
        layout.prop(mat, "nns_wireframe")
        layout.prop(mat, "nns_depth_test")
        layout.prop(mat, "nns_update_depth_buffer")
        layout.prop(mat, "nns_render_1_pixel")
        layout.prop(mat, "nns_far_clipping")
        layout.prop(mat, "nns_polygonid")
        layout.prop(mat, "nns_display_face")
        layout.prop(mat, "nns_polygon_mode")
        layout.prop(mat, "nns_tex_gen_mode")
        if mat.nns_tex_gen_mode == 'nrm' or mat.nns_tex_gen_mode == 'pos':
            layout.prop(mat, "nns_tex_gen_st_src")
            box = layout.box()
            box.label(text="Texture effect matrix")
            row = box.row(align=True)
            row.prop(mat, "nns_tex_effect_mtx_0")
            row = box.row(align=True)
            row.prop(mat, "nns_tex_effect_mtx_1")
            row = box.row(align=True)
            row.prop(mat, "nns_tex_effect_mtx_2")
            row = box.row(align=True)
            row.prop(mat, "nns_tex_effect_mtx_3")


class ExportNitro(bpy.types.Operator):
    bl_idname = "export.nitro"
    bl_label = "Export Nitro"

    filepath = StringProperty(subtype="FILE_PATH")

    pretty_print = BoolProperty(name="Pretty print", default=True)

    magnification = FloatProperty(name="Magnification",
                                  default=0.0625,
                                  precision=4)

    use_primitive_strip = BoolProperty(name="Use primitive strip",
                                       default=True)

    def execute(self, context):
        from . import export_nitro
        settings = self.as_keywords()
        export_nitro.save(context, settings)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


def menu_func_export(self, context):
    self.layout.operator(ExportNitro.bl_idname, text="Nitro IMD (.imd)")


def register():
    bpy.types.Material.nns_light0 = BoolProperty(name="Light0", default=False)
    bpy.types.Material.nns_light1 = BoolProperty(name="Light1", default=False)
    bpy.types.Material.nns_light2 = BoolProperty(name="Light2", default=False)
    bpy.types.Material.nns_light3 = BoolProperty(name="Light3", default=False)
    bpy.types.Material.nns_use_srst = BoolProperty(
        name="Use Specular Reflection Table", default=False)
    bpy.types.Material.nns_fog = BoolProperty(
        name="Fog", default=False)
    bpy.types.Material.nns_wireframe = BoolProperty(
        name="Wireframe", default=False)
    bpy.types.Material.nns_depth_test = BoolProperty(
        name="Depth test for decal polygon", default=False)
    bpy.types.Material.nns_update_depth_buffer = BoolProperty(
        name="Translucent polygons update depth buffer", default=False)
    bpy.types.Material.nns_render_1_pixel = BoolProperty(
        name="Render 1-pixel polygon", default=False)
    bpy.types.Material.nns_far_clipping = BoolProperty(
        name="Far clipping", default=False)
    bpy.types.Material.nns_polygonid = IntProperty(
        name="Polygon ID", default=0)
    display_face_items = [
        ("front", "Front face", '', 1),
        ("back", "Back face", '', 2),
        ("both", "Both faces", '', 3)
    ]
    bpy.types.Material.nns_display_face = EnumProperty(
        name="Display face", items=display_face_items)
    polygon_mode_items = [
        ("modulate", "Modulate", '', 1),
        ("decal", "Decal", '', 2),
        ("toon_highlight", "Toon/highlight", '', 3),
        ("shadow", "Shadow", '', 4)
    ]
    bpy.types.Material.nns_polygon_mode = EnumProperty(
        name="Polygon mode", items=polygon_mode_items)
    tex_gen_mode_items = [
        ("none", "None", '', 1),
        ("tex", "Texcoord", '', 2),
        ("nrm", "Normal", '', 3),
        ("pos", "Vertex", '', 4)
    ]
    bpy.types.Material.nns_tex_gen_mode = EnumProperty(
        name="Tex gen mode", items=tex_gen_mode_items)
    tex_gen_st_src_items = [
        ("polygon", "Polygon", '', 1),
        ("material", "Material", '', 2),
    ]
    bpy.types.Material.nns_tex_gen_st_src = EnumProperty(
        name="Tex gen ST source", items=tex_gen_st_src_items)
    bpy.types.Material.nns_tex_effect_mtx_0 = FloatVectorProperty(size=2,
                                                                  name='')
    bpy.types.Material.nns_tex_effect_mtx_1 = FloatVectorProperty(size=2,
                                                                  name='')
    bpy.types.Material.nns_tex_effect_mtx_2 = FloatVectorProperty(size=2,
                                                                  name='')
    bpy.types.Material.nns_tex_effect_mtx_3 = FloatVectorProperty(size=2,
                                                                  name='')

    bpy.utils.register_class(ExportNitro)
    bpy.utils.register_class(NTR_PT_material)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(ExportNitro)
    bpy.utils.unregister_class(NTR_PT_material)

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()
