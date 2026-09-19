import bpy
from bpy.props import EnumProperty, BoolProperty, IntProperty
from .util import safe_register_class


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
        layout.prop(obj, "nns_node_id")
        if obj.type == 'EMPTY':
            layout.prop(obj, "nns_skip_node")


class NTR_PT_bone(bpy.types.Panel):

    bl_label = "NNS Bone Options"
    bl_idname = "BONE_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "bone"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.bone is not None

    def draw(self, context):
        layout = self.layout
        bone = context.bone
        layout = layout.box()
        title = layout.column()
        title.box().label(text="NNS Bone Options")
        layout.prop(bone, "nns_node_id")


def object_register():
    billboard_items = [
        ("off", "Off", '', 1),
        ("on", "Always face camera", '', 2),
        ("y_on", "Only face camera on y axis", '', 3)
    ]
    bpy.types.Object.nns_billboard = EnumProperty(
        name="Billboard settings", items=billboard_items)

    bpy.types.Object.nns_skip_node = BoolProperty(
        name="Skip node (pass-through)",
        description=(
            "Don't give this object its own node on export. Its "
            "children get attached straight to its parent instead, with "
            "this object's transform folded into them, so the model "
            "looks exactly the same but you're not spending a node on a "
            "purely organizational Empty (a top level rig or scene root "
            "you only added to keep the outliner tidy, for example). "
            "Meant for Empty objects that don't carry any geometry "
            "themselves"
        ),
        default=False)

    bpy.types.Object.nns_node_id = IntProperty(
        name="Node ID (-1 = automatic)",
        description=(
            "Force where this object lands among its siblings on "
            "export. Lower numbers go first; anything left at -1 keeps "
            "Blender's own order and gets placed after all the numbered "
            "ones. Mainly useful for keeping node order (and therefore "
            "animation indices) the same across re-exports"
        ),
        default=-1,
        min=-1)

    bpy.types.Bone.nns_node_id = IntProperty(
        name="Node ID (-1 = automatic)",
        description=(
            "Force where this bone lands among its sibling bones on "
            "export. Lower numbers go first; anything left at -1 keeps "
            "Blender's own order and gets placed after all the numbered "
            "ones. Useful for keeping bone order consistent across "
            "re-exports of the same rig, since animation data (.ica) "
            "depends on that order to stay compatible between assets"
        ),
        default=-1,
        min=-1)

    safe_register_class(NTR_PT_object)
    safe_register_class(NTR_PT_bone)


def object_unregister():
    bpy.utils.unregister_class(NTR_PT_object)
    bpy.utils.unregister_class(NTR_PT_bone)

    del bpy.types.Object.nns_billboard
    del bpy.types.Object.nns_skip_node
    del bpy.types.Object.nns_node_id
    del bpy.types.Bone.nns_node_id
