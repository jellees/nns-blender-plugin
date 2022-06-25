import bpy
from bpy.props import EnumProperty,StringProperty
from bpy.app.handlers import persistent

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


NodeOffsetx = 0
Loca = (-2200, 0)

def find_viewport():
    screen=bpy.context.screen
    i = 0
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            return i
        i += 1
    return None


def create_driver(node):
    viewport = find_viewport()
    screen=bpy.context.screen.name
    for i in range(3):
        D = node.inputs[i].driver_add("default_value")  # bpy.data.screens[\"Layout\"].areas["+str(viewport)+"]
        D.driver.expression = "bpy.data.screens[\""+screen+"\"].areas["+str(viewport)+"].spaces.active.region_3d.view_rotation.to_euler()["+str(i)+"]"


def create_node(node_group, name, type, location=Loca):
    global NodeOffsetx

    nodes = node_group.nodes
    new_node = nodes.new(type=type)
    new_node.name = name
    new_node.label = name
    new_node.location = (location[0] + NodeOffsetx, location[1])
    NodeOffsetx += 300

    return new_node


def generate_billboard_nodes(object):
    obj = object
    mod = obj.modifiers["NNS billboard"]

    mod.node_group.name = "NNS billboard"

    nodes = mod.node_group.nodes
    links = mod.node_group.links

    gp = mod.node_group

    for node in nodes:
        nodes.remove(node)

    inputs_node = create_node(gp, "Group Input", "NodeGroupInput", (-1800, 0))
    Bmode_input = gp.inputs.new("NodeSocketInt", "billboard mode")

    NodeOffsetx = 0

    outputs_node = create_node(gp, "Group Output", "NodeGroupOutput", (3800, 0))

    Cam_node = create_node(gp, "Cam", "ShaderNodeCombineXYZ")
    create_driver(Cam_node)

    Comp1 = create_node(gp, "Comp1", "ShaderNodeMath")
    Comp1.operation = "COMPARE"
    Comp1.inputs[1].default_value = 2.0
    Comp1.inputs[2].default_value = 0.1

    VecMult1 = create_node(gp, "VecMult1", "ShaderNodeVectorMath")
    VecMult1.operation = "MULTIPLY"

    GeoRot1 = create_node(gp, "GeoRot1", "GeometryNodeTransform")

    links.new(inputs_node.outputs[0], GeoRot1.inputs[0])
    links.new(inputs_node.outputs[1], Comp1.inputs[0])
    links.new(Comp1.outputs[0], VecMult1.inputs[0])
    links.new(Cam_node.outputs[0], VecMult1.inputs[1])
    links.new(VecMult1.outputs[0], GeoRot1.inputs[2])

    VecX = create_node(gp, "Vec -1", "FunctionNodeInputVector")
    VecX.vector = (0, -1, 0)
    VecZ = create_node(gp, "Vec +1", "FunctionNodeInputVector")
    VecZ.vector = (0, 0, -1)

    VecRot = create_node(gp, "Vec rot", "ShaderNodeVectorRotate")
    VecRot.rotation_type = "EULER_XYZ"

    links.new(VecZ.outputs[0], VecRot.inputs[0])
    links.new(Cam_node.outputs[0], VecRot.inputs[4])

    Sep = create_node(gp, "Sep", "ShaderNodeSeparateXYZ")
    Comb = create_node(gp, "Sep", "ShaderNodeCombineXYZ")
    Sign = create_node(gp, "Sign", "ShaderNodeMath")
    Sign.operation = "SIGN"

    links.new(VecRot.outputs[0], Sep.inputs[0])
    links.new(Sep.outputs[0], Comb.inputs[0])
    links.new(Sep.outputs[1], Comb.inputs[1])
    links.new(Sep.outputs[0], Sign.inputs[0])

    Norm = create_node(gp, "Norm", "ShaderNodeVectorMath")
    Norm.operation = "NORMALIZE"

    DotP = create_node(gp, "Dot product", "ShaderNodeVectorMath")
    DotP.operation = "DOT_PRODUCT"

    Arcos = create_node(gp, "Arcos", "ShaderNodeMath")
    Arcos.operation = "ARCCOSINE"

    Mult = create_node(gp, "Multiply", "ShaderNodeMath")
    Mult.operation = "MULTIPLY"

    links.new(Comb.outputs[0], Norm.inputs[0])
    links.new(VecX.outputs[0], DotP.inputs[0])
    links.new(Norm.outputs[0], DotP.inputs[1])
    links.new(DotP.outputs[1], Arcos.inputs[0])
    links.new(Arcos.outputs[0], Mult.inputs[0])
    links.new(Sign.outputs[0], Mult.inputs[1])

    Comp2 = create_node(gp, "Comp2", "ShaderNodeMath")
    Comp2.operation = "COMPARE"
    Comp2.inputs[1].default_value = 3.0
    Comp2.inputs[2].default_value = 0.1

    VecMult2 = create_node(gp, "VecMult2", "ShaderNodeMath")
    VecMult2.operation = "MULTIPLY"

    Comb2 = create_node(gp, 'Comb2', "ShaderNodeCombineXYZ")
    Comb2.inputs[0].default_value = 3.14159
    Comb2.inputs[1].default_value = 3.14159

    GeoRot2 = create_node(gp, "GeoRot2", "GeometryNodeTransform")

    links.new(inputs_node.outputs[1], Comp2.inputs[0])
    links.new(Comp2.outputs[0], VecMult2.inputs[0])
    links.new(Mult.outputs[0], Comb2.inputs[1])
    links.new(Comb2.outputs[0], VecMult2.inputs[2])
    links.new(Comb2.outputs[0], GeoRot2.inputs[2])
    links.new(GeoRot1.outputs[0], GeoRot2.inputs[0])
    links.new(GeoRot2.outputs[0], outputs_node.inputs[0])


def create_billboard_modifier(object):
    obj = object
    if "NNS billboard" in obj.modifiers.keys():
        obj.modifiers.remove(obj.modifiers["NNS billboard"])
    mod = obj.modifiers.new("NNS billboard", "NODES")
    if "NNS billboard" in bpy.data.node_groups.keys() and "GeoRot2" in bpy.data.node_groups[
        "NNS billboard"].nodes.keys():
        gp = obj.modifiers["NNS billboard"].node_group
        bpy.data.node_groups.remove(gp)
        mod.node_group = bpy.data.node_groups["NNS billboard"]
    else:
        if "NNS billboard" in bpy.data.node_groups.keys():
            bpy.data.node_groups.remove(bpy.data.node_groups["NNS billboard"])
        generate_billboard_nodes(obj)

    Bmode = 1
    Bm = obj.nns_billboard
    if Bm == "off":
        Bmode = 1
    elif Bm == "on":
        Bmode = 2
    elif Bm == "y_on":
        Bmode = 3

    mod["Input_2"] = Bmode


def update_billboard_mode(self,context):
    obj = bpy.context.object
    if not ("NNS billboard" in obj.modifiers.keys()):
        create_billboard_modifier(obj)
    elif not (obj.modifiers["NNS billboard"].node_group is None):
        if obj.modifiers["NNS billboard"].node_group.name == "NNS billboard" and "GeoRot2" in obj.modifiers[
            "NNS billboard"].node_group.nodes.keys():

            Bmode = 1
            Bm = obj.nns_billboard
            if Bm == "off":
                Bmode = 1
            elif Bm == "on":
                Bmode = 2
            elif Bm == "y_on":
                Bmode = 3

            obj.modifiers["NNS billboard"]["Input_2"] = Bmode

            Cam_node = obj.modifiers["NNS billboard"].node_group.nodes.get("Cam")
            create_driver(Cam_node)
        else:
            create_billboard_modifier(obj)
    else:
        create_billboard_modifier(obj)

def update_drivers(context):
    scene=context.scene
    if not len(scene.objects.keys())==0:
        Nfound=True
        i=0
        while(Nfound):
            if scene.objects[i].type=="MESH":
                obj=scene.objects[0]
                Nfound=False
        if not Nfound:
            if "Cam" not in obj.modifiers["NNS billboard"].node_group.nodes.keys():
                update_billboard_mode(self,context)
            else:
                create_driver(obj.modifiers["NNS billboard"].node_group.nodes["Cam"])

def check_screen_name(context):
    scene = context.scene
    if scene.name == scene.screen:
        return None
    else:
        scene.screen = context.screen.name
        update_drivers(context)

@persistent
def update_scene_screen(self):
    context=bpy.context
    if "temp" in context.screen.name:
        return None
    else:
        check_screen_name(context)



def object_register():
    billboard_items = [
        ("off", "Off", '', 1),
        ("on", "Always face camera", '', 2),
        ("y_on", "Only face camera on y axis", '', 3)
    ]
    bpy.types.Object.nns_billboard = EnumProperty(
        name="Billboard settings", items=billboard_items,update=update_billboard_mode)
    bpy.types.Scene.screen=StringProperty(name="current_window",default="Layout")
    bpy.utils.register_class(NTR_PT_object)
    if update_scene_screen not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(update_scene_screen)

def object_unregister():
    bpy.utils.unregister_class(NTR_PT_object)
    if update_scene_screen in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(update_scene_screen)