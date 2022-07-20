import bpy
from bpy.props import EnumProperty, StringProperty
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


node_offset_x = 0
loca = (-2200, 0)


def find_viewport():
    screen = bpy.context.screen
    i = 0
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            return i
        i += 1
    return None


def create_driver(node):
    viewport = find_viewport()
    if viewport is not None:
        screen = bpy.context.screen.name
        if bpy.data.screens[screen].areas[viewport].spaces.active is not None:
            for i in range(3):
                d = node.inputs[i].driver_add("default_value")
                d.driver.expression = "bpy.data.screens[\"" + screen + "\"].areas[" + str(
                    viewport) + "].spaces.active.region_3d.view_rotation.to_euler()[" + str(i) + "]"


def create_node(node_group, name, type, location=loca):
    global node_offset_x

    nodes = node_group.nodes
    new_node = nodes.new(type=type)
    new_node.name = name
    new_node.label = name
    new_node.location = (location[0] + node_offset_x, location[1])
    node_offset_x += 300

    return new_node


def generate_billboard_nodes(gp):
    nodes = gp.nodes
    links = gp.links

    for node in nodes:
        nodes.remove(node)

    inputs_node = create_node(gp, "Group Input", "NodeGroupInput", (-1800, 0))
    geo_input = gp.inputs.new("NodeSocketGeometry", "Geometry")
    bmode_input = gp.inputs.new("NodeSocketInt", "billboard mode")

    node_offset_x = 0

    outputs_node = create_node(gp, "Group Output", "NodeGroupOutput", (3800, 0))

    cam_node = create_node(gp, "Cam", "ShaderNodeCombineXYZ")
    create_driver(cam_node)

    comp1 = create_node(gp, "Comp1", "ShaderNodeMath")
    comp1.operation = "COMPARE"
    comp1.inputs[1].default_value = 2.0
    comp1.inputs[2].default_value = 0.1

    vec_add = create_node(gp, "VecAdd", "ShaderNodeVectorMath")
    vec_add.operation = "ADD"
    vec_add.inputs[1].default_value[0] = -1.5708

    vec_mult1 = create_node(gp, "VecMult1", "ShaderNodeVectorMath")
    vec_mult1.operation = "MULTIPLY"

    geo_rot1 = create_node(gp, "GeoRot1", "GeometryNodeTransform")

    links.new(inputs_node.outputs[0], geo_rot1.inputs[0])
    links.new(inputs_node.outputs[1], comp1.inputs[0])
    links.new(comp1.outputs[0], vec_mult1.inputs[0])
    links.new(cam_node.outputs[0], vec_add.inputs[0])
    links.new(vec_add.outputs[0], vec_mult1.inputs[1])
    links.new(vec_mult1.outputs[0], geo_rot1.inputs[2])

    vec_x = create_node(gp, "Vec -1", "FunctionNodeInputVector")
    vec_x.vector = (0, -1, 0)
    vec_z = create_node(gp, "Vec +1", "FunctionNodeInputVector")
    vec_z.vector = (0, 0, -1)

    vec_rot = create_node(gp, "Vec rot", "ShaderNodeVectorRotate")
    vec_rot.rotation_type = "EULER_XYZ"

    links.new(vec_z.outputs[0], vec_rot.inputs[0])
    links.new(cam_node.outputs[0], vec_rot.inputs[4])

    sep = create_node(gp, "Sep", "ShaderNodeSeparateXYZ")
    comb = create_node(gp, "Sep", "ShaderNodeCombineXYZ")
    sign = create_node(gp, "Sign", "ShaderNodeMath")
    sign.operation = "SIGN"

    links.new(vec_rot.outputs[0], sep.inputs[0])
    links.new(sep.outputs[0], comb.inputs[0])
    links.new(sep.outputs[1], comb.inputs[1])
    links.new(sep.outputs[0], sign.inputs[0])

    norm = create_node(gp, "Norm", "ShaderNodeVectorMath")
    norm.operation = "NORMALIZE"

    dot_p = create_node(gp, "Dot product", "ShaderNodeVectorMath")
    dot_p.operation = "DOT_PRODUCT"

    arcos = create_node(gp, "Arcos", "ShaderNodeMath")
    arcos.operation = "ARCCOSINE"

    mult = create_node(gp, "Multiply", "ShaderNodeMath")
    mult.operation = "MULTIPLY"

    links.new(comb.outputs[0], norm.inputs[0])
    links.new(vec_x.outputs[0], dot_p.inputs[0])
    links.new(norm.outputs[0], dot_p.inputs[1])
    links.new(dot_p.outputs[1], arcos.inputs[0])
    links.new(arcos.outputs[0], mult.inputs[0])
    links.new(sign.outputs[0], mult.inputs[1])

    comp2 = create_node(gp, "Comp2", "ShaderNodeMath")
    comp2.operation = "COMPARE"
    comp2.inputs[1].default_value = 3.0
    comp2.inputs[2].default_value = 0.1

    vec_mult2 = create_node(gp, "VecMult2", "ShaderNodeVectorMath")
    vec_mult2.operation = "MULTIPLY"

    comb2 = create_node(gp, 'Comb2', "ShaderNodeCombineXYZ")
    comb2.inputs[0].default_value = 3.14159
    comb2.inputs[1].default_value = 3.14159

    geo_rot2 = create_node(gp, "GeoRot2", "GeometryNodeTransform")

    links.new(inputs_node.outputs[1], comp2.inputs[0])
    links.new(comp2.outputs[0], vec_mult2.inputs[0])
    links.new(mult.outputs[0], comb2.inputs[2])
    links.new(comb2.outputs[0], vec_mult2.inputs[1])
    links.new(vec_mult2.outputs[0], geo_rot2.inputs[2])
    links.new(geo_rot1.outputs[0], geo_rot2.inputs[0])
    links.new(geo_rot2.outputs[0], outputs_node.inputs[0])

    node_offset_x = 0

    return gp


def create_billboard_node_group():
    gps = bpy.data.node_groups
    if "NNS billboard" not in gps.keys():
        gp = gps.new("NNS billboard", "GeometryNodeTree")
        generate_billboard_nodes(gp)
    else:
        gp = gps["NNS billboard"]
        if "Cam" not in gp.nodes:
            generate_billboard_nodes(gp)

    return gp


def create_billboard_modifier(obj):
    if "NNS billboard" in obj.modifiers.keys():
        obj.modifiers.remove(obj.modifiers["NNS billboard"])
    mod = obj.modifiers.new("NNS billboard", "NODES")
    gp = create_billboard_node_group()
    mod.node_group = gp

    bmode = 1
    bm = obj.nns_billboard
    if bm == "off":
        bmode = 1
    elif bm == "on":
        bmode = 2
    elif bm == "y_on":
        bmode = 3

    mod["Input_1"] = bmode


def update_billboard_mode(self, context):
    obj = context.object
    if bpy.app.version[0] <= 2:
        return None
    else:
        if not ("NNS billboard" in obj.modifiers.keys()):
            create_billboard_modifier(obj)
        elif not (obj.modifiers["NNS billboard"].node_group is None):
            if obj.modifiers["NNS billboard"].node_group.name == "NNS billboard" and "GeoRot2" in obj.modifiers[
                "NNS billboard"].node_group.nodes.keys():

                bmode = 1
                bm = obj.nns_billboard
                if bm == "off":
                    bmode = 1
                elif bm == "on":
                    bmode = 2
                elif bm == "y_on":
                    bmode = 3

                obj.modifiers["NNS billboard"]["Input_1"] = bmode

                cam_node = obj.modifiers["NNS billboard"].node_group.nodes.get("Cam")
                create_driver(cam_node)
            else:
                create_billboard_modifier(obj)
        else:
            create_billboard_modifier(obj)


def update_drivers(context):
    if "temp" not in context.screen.name:
        if not len(context.scene.objects.keys()) == 0:
            gps = bpy.data.node_groups
            if "NNS billboard" in gps.keys():
                gp = gps["NNS billboard"]
                if "Cam" in gp.nodes.keys():
                    create_driver(gp.nodes["Cam"])
                else:
                    generate_billboard_nodes(gp)


def check_screen_name(context):
    scene = context.scene
    if scene.name == scene.screen:
        return None
    else:
        scene.screen = context.screen.name
        update_drivers(context)


@persistent
def update_scene_screen(self):
    if bpy.context.screen.name == bpy.context.scene.screen:
        return None
    else:
        bpy.context.scene.screen = bpy.context.screen.name
        update_drivers(bpy.context)


def object_register():
    billboard_items = [
        ("off", "Off", '', 1),
        ("on", "Always face camera", '', 2),
        ("y_on", "Only face camera on y axis", '', 3)
    ]
    bpy.types.Object.nns_billboard = EnumProperty(
        name="Billboard settings", items=billboard_items, update=update_billboard_mode)

    if bpy.app.version[0] > 2:
        bpy.types.Scene.screen = StringProperty(name="current_window", default="Layout", update=update_billboard_mode)
        bpy.utils.register_class(NTR_PT_object)
        if update_scene_screen not in bpy.app.handlers.frame_change_post:
            bpy.app.handlers.frame_change_post.append(update_scene_screen)
    else:
        bpy.types.Scene.screen = StringProperty(name="current_window", default="Layout")
        bpy.utils.register_class(NTR_PT_object)


def object_unregister():
    bpy.utils.unregister_class(NTR_PT_object)
    if update_scene_screen in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(update_scene_screen)
