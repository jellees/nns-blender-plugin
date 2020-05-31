import bpy
from bpy.props import EnumProperty

class NTR_PT_object(bpy.types.Panel):
    bl_label = "NNS Object Options"
    bl_idname = "OBJECT_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        obj = context.object
        layout = layout.box()
        title = layout.column()
        title.box().label(text="NNS Object Options")
        layout.prop(obj, "nns_billboard")

def object_register():
    billboard_items = [
        ("off", "Off", '', 1),
        ("on", "Always face camera", '', 2),
        ("y_on", "Only face camera on y axis", '', 3)
    ]
    bpy.types.Object.nns_billboard = EnumProperty(
        name="Billboard settings", items=billboard_items)

    bpy.utils.register_class(NTR_PT_object)

def object_unregister():
    bpy.utils.unregister_class(NTR_PT_object)