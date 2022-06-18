import bpy
from bpy.props import (BoolProperty,
                       FloatProperty,
                       EnumProperty,
                       IntProperty,
                       FloatVectorProperty,
                       PointerProperty,
                       CollectionProperty)
from bpy.types import Image
from bpy.app.handlers import persistent


def generate_output_node(material, input):
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    if material.nns_hdr_add_self:
        add_shader1 = nodes.new(type='ShaderNodeAddShader')
        add_shader2 = nodes.new(type='ShaderNodeAddShader')
        links.new(input.outputs[0], add_shader1.inputs[0])
        links.new(input.outputs[0], add_shader1.inputs[1])
        links.new(add_shader1.outputs[0], add_shader2.inputs[0])
        links.new(add_shader1.outputs[0], add_shader2.inputs[1])
        links.new(add_shader2.outputs[0], node_output.inputs[0])
    else:
        links.new(input.outputs[0], node_output.inputs[0])


def generate_culling_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_geo = nodes.new(type='ShaderNodeNewGeometry')
    node_invert = nodes.new(type='ShaderNodeInvert')
    if material.nns_display_face == "front":
        node_invert.inputs[0].default_value = 1.0
    elif material.nns_display_face == "back":
        node_invert.inputs[0].default_value = 0.0
    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.inputs[0].default_value = 1.0
    links.new(node_geo.outputs[6], node_invert.inputs[1])
    links.new(node_invert.outputs[0], node_mix_rgb.inputs[1])

    return node_mix_rgb


def generate_srt_nodes(material, input):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_sub = nodes.new(type='ShaderNodeVectorMath')
    node_sub.operation = 'SUBTRACT'
    node_sub.location = (-100, 0)

    if material.nns_tex_gen_mode == "nrm":
        node_sub.inputs[1].default_value = (0, 0, 0)
    else:
        node_sub.inputs[1].default_value = (0.5, 0.5, 0.5)

    node_rt_mapping = nodes.new(type='ShaderNodeMapping')
    node_rt_mapping.name = 'nns_node_rt'
    node_rt_mapping.location = (0, 0)
    node_rt_mapping.inputs[3].default_value = (1, 1, 1)

    node_add = nodes.new(type='ShaderNodeVectorMath')
    node_add.operation = 'ADD'
    node_add.location = (100, 0)
    node_add.inputs[1].default_value = (0.5, 0.5, 0.5)

    node_s_mapping = nodes.new(type='ShaderNodeMapping')
    node_s_mapping.name = 'nns_node_s'
    node_s_mapping.location = (200, 0)
    node_s_mapping.inputs[3].default_value = (1, 1, 1)

    links.new(input.outputs[0], node_sub.inputs[0])
    links.new(node_sub.outputs[0], node_rt_mapping.inputs[0])
    links.new(node_rt_mapping.outputs[0], node_add.inputs[0])
    links.new(node_add.outputs[0], node_s_mapping.inputs[0])

    return node_s_mapping

NodeOffsetx=0
NodeOffsety=0
Loca=(0,0)


def create_node(mat,name,nodeType,location,offsetMode=1):
    global NodeOffsetx
    global NodeOffsety
    nodes = mat.node_tree.nodes
    newnode = nodes.new(type=nodeType)
    newnode.name=name
    newnode.label=name
    if offsetMode==0:
        newnode.location=location
    elif offsetMode==1:
        newnode.location=(location[0]+NodeOffsetx, location[1]+NodeOffsety)
        NodeOffsetx+=180
    elif offsetMode==2:
        newnode.location=(location[0],location[1]+NodeOffsety)
        NodeOffsety-=150
    elif offsetMode==3:
        newnode.location=(location[0]+NodeOffsetx, location[1]+NodeOffsety)
        NodeOffsetx+=180
        newnode.location=(location[0],location[1]+NodeOffsety)
        NodeOffsety-=150
    return newnode


def create_light_nodes(mat,index,location):
    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    #get inputs
    
    #lights

    LightVec=nodes.get("Light"+str(index)+" Vector")
    LightSpec=nodes.get("Light"+str(index)+" Specular")
    LightCol=nodes.get("Light"+str(index)+" Color Filtered")
    
    #materials
    
    NodeDiffuse=nodes.get("df")
    NodeAmbient=nodes.get("amb")
    NodeSpecular=nodes.get("spec")
    
    #transform inputs
    #normals to camera space
    
    NormalVecNode = create_node(mat,"normal vector(N)",'ShaderNodeNewGeometry',location)
    
    VecMult1 = create_node(mat,"Fix backface","ShaderNodeVectorMath",location)
    VecMult1.operation="MULTIPLY"
    
    MultAdd1=create_node(mat,"remap backface factor","ShaderNodeMath",location)
    MultAdd1.operation="MULTIPLY_ADD"
    MultAdd1.inputs[1].default_value=-2.0
    MultAdd1.inputs[2].default_value=1.0
    
    VecTrans = create_node(mat,"transform to camera space",'ShaderNodeVectorTransform',location)
    VecTrans.convert_from="WORLD"
    VecTrans.convert_to="CAMERA"
    
    links.new(NormalVecNode.outputs[6],MultAdd1.inputs[0])
    links.new(NormalVecNode.outputs[1],VecMult1.inputs[0])
    links.new(MultAdd1.outputs[0],VecMult1.inputs[1])
    links.new(VecMult1.outputs[0],VecTrans.inputs[0])
    
    #LightVector in camera space
    VecMult2=create_node(mat,"inverse light angle","ShaderNodeVectorMath",location)
    VecMult2.inputs[1].default_value=(-1,-1,-1)
    VecMult2.operation="MULTIPLY"
    
    VecNorm1=create_node(mat,"Normalize","ShaderNodeVectorMath",location)
    VecNorm1.operation="NORMALIZE"
    
    links.new(LightVec.outputs[0],VecMult2.inputs[0])
    links.new(VecMult2.outputs[0],VecNorm1.inputs[0])
    
    SepXYZ1=create_node(mat,"SepXYZ","ShaderNodeSeparateXYZ",location)
    CombXYZ1=create_node(mat,"CombXYZ","ShaderNodeCombineXYZ",location)
    
    links.new(VecNorm1.outputs[0],SepXYZ1.inputs[0])
    links.new(SepXYZ1.outputs[0],CombXYZ1.inputs[0])
    links.new(SepXYZ1.outputs[1],CombXYZ1.inputs[2])
    links.new(SepXYZ1.outputs[2],CombXYZ1.inputs[1])
    
    
    #ld : Diffuse reflection shininess
    #ls : Specular reflection shininess
    
    #calculation of ld 
    
    DotProd1=create_node(mat,"Dot Prod1","ShaderNodeVectorMath",location)
    DotProd1.operation="DOT_PRODUCT"
    
    links.new(VecTrans.outputs[0],DotProd1.inputs[0])
    links.new(CombXYZ1.outputs[0],DotProd1.inputs[1])
    
    Clamp1=create_node(mat,"Clamp1","ShaderNodeClamp",location)
    Clamp1.inputs[1].default_value=0.0
    Clamp1.inputs[2].default_value=1.0
    
    ld=create_node(mat,"ld","ShaderNodeMath",location)
    ld.operation="POWER"
    ld.inputs[1].default_value=1.50
    
    links.new(DotProd1.outputs[1],Clamp1.inputs[0])
    links.new(Clamp1.outputs[0],ld.inputs[0])
    
    #half angle vector
    
    VecAdd1=create_node(mat,"VecAdd1","ShaderNodeVectorMath",location)
    VecAdd1.operation="ADD"
    VecAdd1.inputs[1].default_value=(0,0.99,0)
    
    VecNorm2=create_node(mat,"VecNorm2","ShaderNodeVectorMath",location)
    VecNorm2.operation="NORMALIZE"
    
    links.new(CombXYZ1.outputs[0],VecAdd1.inputs[0])
    links.new(VecAdd1.outputs[0],VecNorm2.inputs[0])
    
    #calculation of ls (may not be 100% accurate due to me not knowing how to search for tables in the ida db but it's accurate enough for preview purpose)
    #may be updated if i find a better approwimation or get the exact formula
    
    DotProd2=create_node(mat,"DotProd2","ShaderNodeVectorMath",location)
    DotProd2.operation="DOT_PRODUCT"
    
    #specular corrective mask
    
    Sign1=create_node(mat,"Sign1","ShaderNodeMath",location)
    Sign1.operation="SIGN"
    Sign1.use_clamp=True
    
    #end of mask
    
    Pow1=create_node(mat,"Pow1","ShaderNodeMath",location)
    Pow1.operation="POWER"
    Pow1.inputs[1].default_value=2.0
    
    links.new(VecNorm2.outputs[0],DotProd2.inputs[0])
    links.new(VecTrans.outputs[0],DotProd2.inputs[1])
    links.new(DotProd2.outputs[1],Pow1.inputs[0])
    links.new(DotProd2.outputs[1],Sign1.inputs[0])
    
    Mult1=create_node(mat,"Mult1","ShaderNodeMath",location)
    Mult1.operation="MULTIPLY"
    Mult1.inputs[1].default_value=2.0
    
    Sub1=create_node(mat,"Sub1","ShaderNodeMath",location)
    Sub1.operation="SUBTRACT"
    Sub1.inputs[1].default_value=1.0
    Sub1.use_clamp=True
    
    links.new(Pow1.outputs[0],Mult1.inputs[0])
    links.new(Mult1.outputs[0],Sub1.inputs[0]) 
    
    #applying the spec corrective mask
    
    Mult3=create_node(mat,"Mult3","ShaderNodeMath",location)
    Mult3.operation="MULTIPLY"
    links.new(Sign1.outputs[0],Mult3.inputs[0])
    links.new(Sub1.outputs[0],Mult3.inputs[1])
    
    ls=create_node(mat,"Specular brightness","ShaderNodeMath",location)
    ls.operation="POWER"
    ls.inputs[1].default_value=2.0
    links.new(Mult3.outputs[0],ls.inputs[0])
    
    #Diffuse color
     
    Di=create_node(mat,"Diffuse "+str(index),"ShaderNodeMixRGB",location)
    Di.blend_type="MULTIPLY"
    Di.inputs[0].default_value=1.0
    
    links.new(NodeDiffuse.outputs[0],Di.inputs[1])
    links.new(ld.outputs[0],Di.inputs[2])
    
    #Specular color
    
    Pow2=create_node(mat,"Pow2","ShaderNodeMath",location)
    Pow2.operation="POWER"
    Pow2.inputs[1].default_value=1.5
    
    Mult4=create_node(mat,"Mult4","ShaderNodeMath",location)
    Mult4.operation="MULTIPLY"
    
    Si=create_node(mat,"Specular "+str(index),"ShaderNodeMixRGB",location)
    Si.blend_type="MULTIPLY"
    Si.inputs[0].default_value=1.0
    
    links.new(NodeSpecular.outputs[0],Si.inputs[1])
    links.new(LightSpec.outputs[0],Pow2.inputs[0])
    links.new(ls.outputs[0],Mult4.inputs[0])
    links.new(Pow2.outputs[0],Mult4.inputs[1])
    links.new(Mult4.outputs[0],Si.inputs[2])
    
    #addition of the three colors (all except emission)
    
    ColAdd1=create_node(mat,"Ambient "+str(index),"ShaderNodeMixRGB",location)
    ColAdd1.blend_type="ADD"
    ColAdd1.inputs[0].default_value=1.0
    
    
    ColAdd2=create_node(mat,"ColAdd2","ShaderNodeMixRGB",location)
    ColAdd2.blend_type="ADD"
    ColAdd2.inputs[0].default_value=1.0
    
    links.new(NodeAmbient.outputs[0],ColAdd1.inputs[2])
    links.new(Di.outputs[0],ColAdd1.inputs[1])
    links.new(ColAdd1.outputs[0],ColAdd2.inputs[1])
    links.new(Si.outputs[0],ColAdd2.inputs[2])

    #multiply with light color
    
    ColMult1=create_node(mat,"Result "+str(index),"ShaderNodeMixRGB",location)
    ColMult1.blend_type="MULTIPLY"
    ColMult1.inputs[0].default_value=1.0
    
    links.new(LightCol.outputs[0],ColMult1.inputs[2])
    links.new(ColAdd2.outputs[0],ColMult1.inputs[1])
    LightNode=ColMult1
        
    return LightNode


def generate_normal_lightning_color_nodes(material):
    global NodeOffsety
    global NodeOffsetx
    global Loca
    
    NodeOffsetx=0
    NodeOffsety=0
    
    mat = material
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    Matcols = {"df": (material.nns_diffuse[0],
                            material.nns_diffuse[1],
                            material.nns_diffuse[2],
                            1.0),
                    "amb":(material.nns_ambient[0],
                            material.nns_ambient[1],
                            material.nns_ambient[2],
                            1.0),
                    "spec":(material.nns_specular[0],
                            material.nns_specular[1],
                            material.nns_specular[2],
                            1.0),
                    "em":(material.nns_emission[0],
                            material.nns_emission[1],
                            material.nns_emission[2],
                            1.0)}

    Light0={"LightVector":(0,0,-1),"LightCol":(1,1,1,1),"LightSpecular":0.5,"isLightEnabled":mat.nns_light0,"LightIndex":0}
    Light1={"LightVector":(0,0.5,-0.5),"LightCol":(1,1,1,1),"LightSpecular":1,"isLightEnabled":mat.nns_light1,"LightIndex":1}
    Light2={"LightVector":(0,0,-1),"LightCol":(1,0,0,1),"LightSpecular":0.5,"isLightEnabled":mat.nns_light2,"LightIndex":2}
    Light3={"LightVector":(0,0,1),"LightCol":(1,1,0,1),"LightSpecular":0,"isLightEnabled":mat.nns_light3,"LightIndex":3}
    
    Lights=(Light0,Light1,Light2,Light3)
        
    #inputs
    NodeOffsetx=0
    NodeOffsety=-300
    Loca=(-7500,-300)
    
    for i in range(4):
        LightVec=create_node(mat,"Light"+str(i)+" Vector","ShaderNodeCombineXYZ",Loca,2)
        for j in range(3):
            LightVec.inputs[j].default_value=Lights[i]["LightVector"][j]
        
        LightCol=create_node(mat,"Light"+str(i)+" Color","ShaderNodeRGB",Loca,2)
        LightCol.outputs[0].default_value=Lights[i]["LightCol"]
        
        LightSpec=create_node(mat,"Light"+str(i)+" Specular","ShaderNodeValue",Loca,2)
        LightSpec.outputs[0].default_value=Lights[i]["LightSpecular"]
        
        LightEnabled=create_node(mat,"Light"+str(i)+" Enabled","ShaderNodeValue",Loca,2)
        LightEnabled.outputs[0].default_value=Lights[i]["isLightEnabled"]
        
        MaskNode=create_node(mat,"Light"+str(i)+" Color Filtered","ShaderNodeMixRGB",(-7300,Loca[1]),2)
        MaskNode.blend_type="MULTIPLY"
        MaskNode.inputs[0].default_value=1.0
        
        links.new(LightCol.outputs[0],MaskNode.inputs[1])
        links.new(LightEnabled.outputs[0],MaskNode.inputs[2])
    
    #material colors
    
    for name in Matcols.keys():
        Col=create_node(mat,name,"ShaderNodeRGB",Loca,2)
        Col.outputs[0].default_value=Matcols[name]
        
    #add all the results of the light0, 1, 2 and 3 calculations
    
    AddNodesX=-600
    NodeOffsety=-300
    
    LColAdd1=create_node(mat,"LColAdd1","ShaderNodeMixRGB",(AddNodesX,-300),3)
    LColAdd1.blend_type="ADD"
    LColAdd1.inputs[0].default_value=1.0
    
    LColAdd2=create_node(mat,"LColAdd2","ShaderNodeMixRGB",(AddNodesX,-450),3)
    LColAdd2.blend_type="ADD"
    LColAdd2.inputs[0].default_value=1.0
    
    LColAdd3=create_node(mat,"LColAdd3","ShaderNodeMixRGB",(AddNodesX,-600),3)
    LColAdd3.blend_type="ADD"
    LColAdd3.inputs[0].default_value=1.0
    
    LColAdd4=create_node(mat,"Total result","ShaderNodeMixRGB",(AddNodesX,-750),3)
    LColAdd4.blend_type="ADD"
    LColAdd4.inputs[0].default_value=1.0
    NodeEmission=nodes.get("em")
    
    UseDiffuseNode=create_node(mat,"UseOnlyDiffuse?","ShaderNodeMixRGB",(AddNodesX,-750),3)
    UseDiffuseNode.blend_type="MIX"
    
    links.new(LColAdd1.outputs[0],LColAdd2.inputs[1])
    links.new(LColAdd2.outputs[0],LColAdd3.inputs[1])
    links.new(LColAdd3.outputs[0],LColAdd4.inputs[1])
    links.new(NodeEmission.outputs[0],LColAdd4.inputs[2])
    
    NodeOffsetx=0
    NodeOffsety=-300
    
    for i in range(4):
        LightNode=create_light_nodes(mat,i,(-6500-i*150,-300))
        if i==0 or i==1:
            links.new(LightNode.outputs[0],LColAdd1.inputs[i+1])
        elif i==2:
            links.new(LightNode.outputs[0],LColAdd2.inputs[2])
        else:
            links.new(LightNode.outputs[0],LColAdd3.inputs [2])
        NodeOffsety-=350
        NodeOffsetx=0
    
    links.new(LColAdd3.outputs[0],LColAdd4.inputs[1])
    links.new(LColAdd4.outputs[0],UseDiffuseNode.inputs[1])
    LightTotalResult=UseDiffuseNode
    
    #if no light is enbaled
    UseOnlyDiffuse=True
    for light in Lights:
        if light["isLightEnabled"]:
            UseOnlyDiffuse=False
    
    LightTotalResult.inputs[0].default_value=UseOnlyDiffuse
    LightTotalResult.inputs[2].default_value=Matcols["df"]
    
    return LightTotalResult

def generate_decal_vc_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_1 = nodes.new(type='ShaderNodeMixRGB')
    node_mix_1.inputs[0].default_value = 0.0

    node_mix_2 = nodes.new(type='ShaderNodeMixRGB')

    links.new(node_mix_1.outputs[0], node_mix_2.inputs[2])

    if "tx" in material.nns_mat_type:
        node_image = generate_image_nodes(material)
        links.new(node_image.outputs[0], node_mix_1.inputs[1])
        links.new(node_image.outputs[1], node_mix_1.inputs[2])
        links.new(node_image.outputs[1], node_mix_2.inputs[0])

    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_trans_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')

    links.new(node_mix_2.outputs[0], node_mix_shader.inputs[2])
    links.new(node_trans_bsdf.outputs[0], node_mix_shader.inputs[1])

    if "vc" in material.nns_mat_type:
        node_attr = nodes.new(type='ShaderNodeAttribute')
        node_attr.attribute_name = 'Col'
        links.new(node_attr.outputs[0], node_mix_2.inputs[1])
        
    elif "nr" in material.nns_mat_type:
        node_vertex_lighting=generate_normal_lightning_color_nodes(material)
        links.new(node_vertex_lighting.outputs[0], node_mix_2.inputs[1])
        
    else:
        node_diffuse = nodes.new(type='ShaderNodeMixRGB')
        node_diffuse.name = 'nns_node_diffuse'
        node_diffuse.blend_type = 'MULTIPLY'
        node_diffuse.inputs[0].default_value = 1.0
        node_diffuse.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
        node_diffuse.inputs[2].default_value = (
            material.nns_diffuse[0],
            material.nns_diffuse[1],
            material.nns_diffuse[2],
            1.0)
        links.new(node_diffuse.outputs[0], node_mix_2.inputs[1])

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.location = (0, 200)
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    generate_output_node(material, node_mix_shader)


def generate_image_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_image = nodes.new(type='ShaderNodeTexImage')
    node_image.name = 'nns_node_image'
    node_image.interpolation = 'Closest'
    if material.nns_image != '':
        try:
            node_image.image = material.nns_image
        except Exception:
            raise NameError("Cannot load image")

    # Make this ahead of time. Must always be filled.
    node_srt = None

    if material.nns_tex_gen_mode == "nrm":
        node_geo = nodes.new(type='ShaderNodeNewGeometry')
        node_vec_trans = nodes.new(type='ShaderNodeVectorTransform')
        node_vec_trans.convert_from = 'WORLD'
        node_vec_trans.convert_to = 'CAMERA'
        node_vec_trans.vector_type = 'NORMAL'
        node_mapping = nodes.new(type='ShaderNodeMapping')
        node_mapping.inputs[3].default_value = (0.5, 0.5, 0.5)
        links.new(node_geo.outputs[1], node_vec_trans.inputs[0])
        links.new(node_vec_trans.outputs[0], node_mapping.inputs[0])
        node_srt = generate_srt_nodes(material, node_mapping)
    else:
        node_uvmap = nodes.new(type='ShaderNodeUVMap')
        node_uvmap.uv_map = "UVMap"
        node_srt = generate_srt_nodes(material, node_uvmap)

    node_sp_xyz = nodes.new(type='ShaderNodeSeparateXYZ')
    links.new(node_srt.outputs[0], node_sp_xyz.inputs[0])

    node_cb_xyz = nodes.new(type='ShaderNodeCombineXYZ')
    links.new(node_sp_xyz.outputs[2], node_cb_xyz.inputs[2])

    if material.nns_tex_tiling_u == "flip":
        node_math_u = nodes.new(type='ShaderNodeMath')
        node_math_u.operation = 'PINGPONG'
        node_math_u.inputs[1].default_value = 1.0
        links.new(node_sp_xyz.outputs[0], node_math_u.inputs[0])
        links.new(node_math_u.outputs[0], node_cb_xyz.inputs[0])
    elif material.nns_tex_tiling_u == "clamp":
        node_math_u = nodes.new(type='ShaderNodeMath')
        node_math_u.operation = 'MINIMUM'
        node_math_u.inputs[1].default_value = 0.99
        node_math_u.use_clamp = True
        links.new(node_sp_xyz.outputs[0], node_math_u.inputs[0])
        links.new(node_math_u.outputs[0], node_cb_xyz.inputs[0])
    else:
        links.new(node_sp_xyz.outputs[0], node_cb_xyz.inputs[0])

    if material.nns_tex_tiling_v == "flip":
        node_math_v = nodes.new(type='ShaderNodeMath')
        node_math_v.operation = 'PINGPONG'
        node_math_v.inputs[1].default_value = 1.0
        links.new(node_sp_xyz.outputs[1], node_math_v.inputs[0])
        links.new(node_math_v.outputs[0], node_cb_xyz.inputs[1])
    elif material.nns_tex_tiling_v == "clamp":
        node_math_v = nodes.new(type='ShaderNodeMath')
        node_math_v.operation = 'MINIMUM'
        node_math_v.inputs[1].default_value = 0.99
        node_math_v.use_clamp = True
        links.new(node_sp_xyz.outputs[1], node_math_v.inputs[0])
        links.new(node_math_v.outputs[0], node_cb_xyz.inputs[1])
    else:
        links.new(node_sp_xyz.outputs[1], node_cb_xyz.inputs[1])

    links.new(node_cb_xyz.outputs[0], node_image.inputs[0])

    return node_image


def generate_mod_vc_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix = nodes.new(type='ShaderNodeMixRGB')
    node_mix.inputs[0].default_value = 0.0

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )

    if "tx" in material.nns_mat_type:
        node_image = generate_image_nodes(material)
        links.new(node_image.outputs[0], node_mix.inputs[1])
        links.new(node_image.outputs[1], node_mix.inputs[2])
        links.new(node_image.outputs[1], node_mix_rgb.inputs[1])

    node_multiply = nodes.new(type='ShaderNodeMixRGB')
    node_multiply.name = 'nns_node_diffuse'
    node_multiply.blend_type = 'MULTIPLY'
    node_multiply.inputs[0].default_value = 1.0
    node_multiply.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_multiply.inputs[2].default_value = (
        material.nns_diffuse[0],
        material.nns_diffuse[1],
        material.nns_diffuse[2],
        1.0
    )

    if "vc" in material.nns_mat_type:
        node_attr = nodes.new(type='ShaderNodeAttribute')
        node_attr.attribute_name = 'Col'
        links.new(node_attr.outputs[0], node_multiply.inputs[2])
        
    elif "nr" in material.nns_mat_type:
        node_vertex_lighting=generate_normal_lightning_color_nodes(material)
        links.new(node_vertex_lighting.outputs[0], node_multiply.inputs[2])

    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    links.new(node_mix.outputs[0], node_multiply.inputs[1])
    links.new(node_multiply.outputs[0], node_mix_shader.inputs[2])

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    generate_output_node(material, node_mix_shader)


def generate_image_only_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_image = generate_image_nodes(material)

    links.new(node_image.outputs[0], node_mix_shader.inputs[2])
    links.new(node_image.outputs[1], node_mix_rgb.inputs[1])

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    generate_output_node(material, node_mix_shader)

def generate_solid_color_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.location = (0, 200)
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_mix_df = nodes.new(type='ShaderNodeMixRGB')
    node_mix_df.location = (0, -100)
    node_mix_df.name = 'nns_node_diffuse'
    node_mix_df.inputs[0].default_value = 1.0
    node_mix_df.inputs[2].default_value = (
        material.nns_diffuse[0],
        material.nns_diffuse[1],
        material.nns_diffuse[2],
        1.0
    )
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')
    node_mix_shader.location = (200, 0)

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_mix_df.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)


def generate_only_normal_lighting(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_vc_light = generate_normal_lightning_color_nodes(material)
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_vc_light.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)

def generate_only_vc_nodes(material):
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    node_mix_rgb = nodes.new(type='ShaderNodeMixRGB')
    node_mix_rgb.blend_type = 'MULTIPLY'
    node_mix_rgb.name = 'nns_node_alpha'
    node_mix_rgb.inputs[0].default_value = 1.0
    node_mix_rgb.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
    node_mix_rgb.inputs[2].default_value = (
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        material.nns_alpha / 31,
        1.0
    )
    node_bsdf = nodes.new(type='ShaderNodeBsdfTransparent')
    node_vc = nodes.new(type='ShaderNodeVertexColor')
    node_vc.layer_name = 'Col'
    node_mix_shader = nodes.new(type='ShaderNodeMixShader')

    if material.nns_display_face == "both":
        links.new(node_mix_rgb.outputs[0], node_mix_shader.inputs[0])
    else:
        node_face = generate_culling_nodes(material)
        links.new(node_mix_rgb.outputs[0], node_face.inputs[2])
        links.new(node_face.outputs[0], node_mix_shader.inputs[0])

    links.new(node_bsdf.outputs[0], node_mix_shader.inputs[1])
    links.new(node_vc.outputs[0], node_mix_shader.inputs[2])
    generate_output_node(material, node_mix_shader)

def generate_nodes(material):
    if material.is_nns:
        nodes = material.node_tree.nodes
        nodes.clear()
        links = material.node_tree.links
        links.clear()

        if material.nns_mat_type == "tx":
            print("oui")
            generate_image_only_nodes(material)
        elif material.nns_mat_type == "df":
            generate_solid_color_nodes(material)
        elif material.nns_mat_type == "vc":
            generate_only_vc_nodes(material)
        elif material.nns_mat_type == "df_nr":
            generate_only_normal_lighting(material) 
        elif material.nns_polygon_mode == "modulate" \
                or material.nns_polygon_mode == "toon_highlight" \
                or material.nns_polygon_mode == "shadow":
            generate_mod_vc_nodes(material)
        elif material.nns_polygon_mode == "decal":
            generate_decal_vc_nodes(material)


def update_nodes_mode(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_mat_type(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_image(self, context):
    material = context.material
    if material.is_nns:
        if material.nns_image != '':
            try:
                node_image = material.node_tree.nodes.get('nns_node_image')
                node_image.image = material.nns_image
            except Exception:
                raise NameError("Cannot load image")


def update_nodes_alpha(self, context):
    material = context.material
    if material.is_nns:
        if material.nns_polygon_mode == "modulate":
            try:
                node_alpha = material.node_tree.nodes.get('nns_node_alpha')
                node_alpha.inputs[2].default_value = (
                    material.nns_alpha / 31,
                    material.nns_alpha / 31,
                    material.nns_alpha / 31,
                    1.0
                )
            except Exception:
                raise NameError("Something alpha I think")
        elif material.nns_polygon_mode == "decal":
            try:
                node_alpha = material.node_tree.nodes.get('nns_node_alpha')
                node_alpha.inputs[0].default_value = material.nns_alpha / 31
            except Exception:
                raise NameError("Something alpha I think")

def update_nodes_diffuse(self, context):
    material=context.material
    if material.is_nns:
        if "df" in material.nns_mat_type and material.nns_mat_type!= "df_nr":
            node_diffuse = material.node_tree.nodes.get('nns_node_diffuse')
            node_diffuse.inputs[2].default_value = (
                material.nns_diffuse[0],
                material.nns_diffuse[1],
                material.nns_diffuse[2],
                1.0
            )
        if "nr" in material.nns_mat_type:
            node_diffuse1=material.node_tree.nodes.get("df")
            node_diffuse1.outputs[0].default_value=(
                material.nns_diffuse[0],
                material.nns_diffuse[1],
                material.nns_diffuse[2],
                1.0
            )
            node_diffuse2=material.node_tree.nodes.get("UseOnlyDiffuse?")
            node_diffuse2.inputs[2].default_value=(
                material.nns_diffuse[0],
                material.nns_diffuse[1],
                material.nns_diffuse[2],
                1.0
            )

def update_nodes_emission(self,context):
    material=context.material
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_emission=material.node_tree.nodes.get("em")
            node_emission.outputs[0].default_value=(
                material.nns_emission[0],
                material.nns_emission[1],
                material.nns_emission[2],
                1.0
            )

def update_nodes_ambient (self,context):
    material=context.material
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_emission=material.node_tree.nodes.get("amb")
            node_emission.outputs[0].default_value=(
                material.nns_ambient[0],
                material.nns_ambient[1],
                material.nns_ambient[2],
                1.0
            )
            
def update_nodes_specular (self,context):
    material=context.material
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_specular=material.node_tree.nodes.get("spec")
            node_specular.outputs[0].default_value=(
                material.nns_specular[0],
                material.nns_specular[1],
                material.nns_specular[2],
                1.0
            )

def update_nodes_UseOnlyDiffuse(material):
    Masknode=material.node_tree.nodes.get("UseOnlyDiffuse?")
    UseOnlyDiffuse=True
    Lights=(material.nns_light0,material.nns_light1,material.nns_light2,material.nns_light3)
    for light in Lights:
        if light:
            UseOnlyDiffuse=False
    Masknode.inputs[0].default_value=UseOnlyDiffuse

def update_nodes_Light0(self,context):
    material=context.material
    update_nodes_UseOnlyDiffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_Light0=material.node_tree.nodes.get("Light0 Enabled")
            node_Light0.outputs[0].default_value=material.nns_light0
        
def update_nodes_Light1(self,context):
    material=context.material
    update_nodes_UseOnlyDiffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_Light1=material.node_tree.nodes.get("Light1 Enabled")
            node_Light1.outputs[0].default_value=material.nns_light1
            
def update_nodes_Light2(self,context):
    material=context.material
    update_nodes_UseOnlyDiffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_Light2=material.node_tree.nodes.get("Light2 Enabled")
            node_Light2.outputs[0].default_value=material.nns_light2

def update_nodes_Light3(self,context):
    material=context.material
    update_nodes_UseOnlyDiffuse(material)
    if material.is_nns:
        if "nr" in material.nns_mat_type:
            node_Light3=material.node_tree.nodes.get("Light3 Enabled")
            node_Light3.outputs[0].default_value=material.nns_light3


def update_nodes_face(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_tex_gen(self, context):
    material = context.material
    generate_nodes(material)


def update_nodes_srt(material):
    if material.is_nns:
        if "tx" in material.nns_mat_type:
            try:
                node_rt = material.node_tree.nodes.get('nns_node_rt')
                node_rt.inputs[1].default_value = (
                    -material.nns_srt_translate[0],
                    -material.nns_srt_translate[1],
                    0
                )
                node_rt.inputs[2].default_value[2] = material.nns_srt_rotate
                node_s = material.node_tree.nodes.get('nns_node_s')
                node_s.inputs[3].default_value = (
                    material.nns_srt_scale[0],
                    material.nns_srt_scale[1],
                    0
                )
            except Exception:
                raise NameError("Couldn't find node?")


def update_nodes_srt_hook(self, context):
    material = context.material
    update_nodes_srt(material)


@persistent
def frame_change_handler(scene):
    if bpy.context.active_object.active_material:
        material = bpy.context.active_object.active_material
        update_nodes_srt(material)


def create_nns_material(obj):
    material = bpy.data.materials.new('Material')
    obj.data.materials.append(material)
    if bpy.context.object is not None:
        bpy.context.object.active_material_index = len(obj.material_slots) - 1

    material.is_nns = True
    material.use_nodes = True
    material.blend_method = 'CLIP'

    generate_nodes(material)


# This class is taken and modified from kurethedead's fast64 plugin.
class CreateNNSMaterial(bpy.types.Operator):
    bl_idname = 'object.create_nns_material'
    bl_label = "Create NNS Material"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    def execute(self, context):
        obj = bpy.context.view_layer.objects.active
        if obj is None:
            self.report({'ERROR'}, 'No active object selected.')
        else:
            create_nns_material(obj)
            self.report({'INFO'}, 'NNS: Created new material.')
        return {'FINISHED'}


class NTRTexReference(bpy.types.PropertyGroup):
    image: PointerProperty(
            name='Texture',
            type=Image)


class NewTexReference(bpy.types.Operator):
    bl_idname = "nns_texframe_reference.new_texref"
    bl_label = "Add a new texture reference"

    def execute(self, context):
        context.material.nns_texframe_reference.add()

        return{'FINISHED'}


class DeleteTexReference(bpy.types.Operator):
    bl_idname = "nns_texframe_reference.delete_texref"
    bl_label = "Deletes a texture reference"

    @classmethod
    def poll(cls, context):
        return context.material.nns_texframe_reference

    def execute(self, context):
        my_list = context.material.nns_texframe_reference
        index = context.material.nns_texframe_reference_index

        my_list.remove(index)
        context.material.nns_texframe_reference_index = min(
            max(0, index - 1), len(my_list) - 1)

        return{'FINISHED'}


class NTR_UL_texframe(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            if item.image:
                layout.label(text=item.image.name, translate=False,
                             icon_value=layout.icon(item.image))
            else:
                layout.label(text="", translate=False, icon='FILE_IMAGE')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon_value=icon)


class NTR_PT_material_texframe(bpy.types.Panel):
    bl_label = "NNS Material texframes"
    bl_idname = "MATERIAL_TEXFRAME_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    def draw(self, context):
        layout = self.layout
        mat = context.material

        if mat is None:
            pass
        elif not(mat.use_nodes and mat.is_nns):
            pass
        elif "tx" in mat.nns_mat_type:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material texture pattern")
            layout.template_list("NTR_UL_texframe", "",
                                 mat, "nns_texframe_reference",
                                 mat, "nns_texframe_reference_index")

            row = layout.row()
            row.operator('nns_texframe_reference.new_texref', text='New')
            row.operator('nns_texframe_reference.delete_texref', text='Delete')

            if (mat.nns_texframe_reference_index >= 0
               and mat.nns_texframe_reference):
                idx = mat.nns_texframe_reference_index
                item = mat.nns_texframe_reference[idx]

                row = layout.row()
                row.template_ID(item, "image", open="image.open")


class NTR_PT_material_keyframe(bpy.types.Panel):
    bl_label = "NNS Material Keyframes"
    bl_idname = "MATERIAL_KEYFRAME_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        if mat is None:
            pass
        elif not(mat.use_nodes and mat.is_nns):
            pass
        elif "tx" in mat.nns_mat_type:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material SRT")
            layout.row(align=True).prop(mat, "nns_srt_scale")
            layout.prop(mat, "nns_srt_rotate")
            layout.row(align=True).prop(mat, "nns_srt_translate")


class NTR_PT_material_visual(bpy.types.Panel):
    bl_label = "NNS Material visual options"
    bl_idname = "MATERIAL_VISUAL_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        layout = layout.box()
        title = layout.column()
        title.box().label(text="NNS Material Visual Options")
        layout.prop(mat, "nns_hdr_add_self")


class NTR_PT_material(bpy.types.Panel):
    bl_label = "NNS Material Options"
    bl_idname = "MATERIAL_PT_nns"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "material"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context):
        return context.material

    def draw(self, context):
        layout = self.layout
        mat = context.material

        layout.operator(CreateNNSMaterial.bl_idname)

        if mat is None:
            pass
        elif not(mat.use_nodes and mat.is_nns):
            pass
        else:
            layout = layout.box()
            title = layout.column()
            title.box().label(text="NNS Material Options")

            layout.prop(mat, "nns_mat_type")

            if "vc" in mat.nns_mat_type:
                layout.label(
                    text='Note: There must be a vertex color layer named '
                         '"Col"')

            if "tx" in mat.nns_mat_type:
                layout.template_ID(mat, "nns_image", open="image.open")

            if "df" in mat.nns_mat_type:
                layout.row().prop(mat, "nns_diffuse")

            if "nr" in mat.nns_mat_type:
                layout.row().prop(mat, "nns_ambient")
                layout.row().prop(mat, "nns_specular")
                layout.row().prop(mat, "nns_emission")

            layout.row().prop(mat, "nns_alpha", slider=True)

            if "nr" in mat.nns_mat_type:
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

            if "tx" in mat.nns_mat_type:
                layout.prop(mat, "nns_tex_tiling_u")
                layout.prop(mat, "nns_tex_tiling_v")
                layout.row(align=True).prop(mat, "nns_tex_scale")
                layout.prop(mat, "nns_tex_rotate")
                layout.row(align=True).prop(mat, "nns_tex_translate")
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


def material_register():

    bpy.utils.register_class(NTRTexReference)
    bpy.utils.register_class(NewTexReference)
    bpy.utils.register_class(DeleteTexReference)
    bpy.types.Material.nns_texframe_reference = CollectionProperty(
        type=NTRTexReference)
    bpy.types.Material.nns_texframe_reference_index = IntProperty(
        name="Active texture reference index", default=0)

    bpy.types.Material.nns_hdr_add_self = BoolProperty(
        default=False, name="HDR shaders", update=update_nodes_mode)
    bpy.types.Material.is_nns = BoolProperty(default=False)
    mat_type_items = [
        ("df", "Solid color", '', 1),
        ("df_nr", "Solid color + normals", '', 2),
        ("vc", "Vertex colored", '', 3),
        ("tx_df", "Textured + solid color", '', 4),
        ("tx_vc", "Textured + vertex colors", '', 5),
        ("tx_nr_df", "Textured + normals", '', 6)
    ]
    bpy.types.Material.nns_mat_type = EnumProperty(
        name="Material type", items=mat_type_items,
        update=update_nodes_mat_type)
    bpy.types.Material.nns_image = PointerProperty(
        name='Texture', type=Image, update=update_nodes_image)
    bpy.types.Material.nns_diffuse = FloatVectorProperty(
        default=(1, 1, 1), subtype='COLOR', min=0.0, max=1.0, name='Diffuse',
        update=update_nodes_diffuse)
    bpy.types.Material.nns_ambient = FloatVectorProperty(
        default=(1, 1, 1), subtype='COLOR', min=0.0, max=1.0, name='Ambient',
        update=update_nodes_ambient)
    bpy.types.Material.nns_specular = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Specular',
        update=update_nodes_specular)
    bpy.types.Material.nns_emission = FloatVectorProperty(
        default=(0, 0, 0), subtype='COLOR', min=0.0, max=1.0, name='Emission',
        update=update_nodes_emission)
    bpy.types.Material.nns_light0 = BoolProperty(name="Light0", default=False,
        update=update_nodes_Light0)
    bpy.types.Material.nns_light1 = BoolProperty(name="Light1", default=False,
        update=update_nodes_Light1)
    bpy.types.Material.nns_light2 = BoolProperty(name="Light2", default=False,
        update=update_nodes_Light2)
    bpy.types.Material.nns_light3 = BoolProperty(name="Light3", default=False,
        update=update_nodes_Light3)
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
        name="Display face", items=display_face_items,
        update=update_nodes_face)
    polygon_mode_items = [
        ("modulate", "Modulate", '', 1),
        ("decal", "Decal", '', 2),
        ("toon_highlight", "Toon/highlight", '', 3),
        ("shadow", "Shadow", '', 4)
    ]
    bpy.types.Material.nns_polygon_mode = EnumProperty(
        name="Polygon mode", items=polygon_mode_items,
        update=update_nodes_mode)
    tex_gen_mode_items = [
        ("none", "None", '', 1),
        ("tex", "Texcoord", '', 2),
        ("nrm", "Normal", '', 3),
        ("pos", "Vertex", '', 4)
    ]
    bpy.types.Material.nns_tex_gen_mode = EnumProperty(
        name="Tex gen mode", items=tex_gen_mode_items,
        update=update_nodes_tex_gen)
    tex_gen_st_src_items = [
        ("polygon", "Polygon", '', 1),
        ("material", "Material", '', 2),
    ]
    bpy.types.Material.nns_tex_gen_st_src = EnumProperty(
        name="Tex gen ST source", items=tex_gen_st_src_items)
    bpy.types.Material.nns_tex_effect_mtx_0 = FloatVectorProperty(
        size=2, name='', default=(1, 0))
    bpy.types.Material.nns_tex_effect_mtx_1 = FloatVectorProperty(
        size=2, name='', default=(0, 1))
    bpy.types.Material.nns_tex_effect_mtx_2 = FloatVectorProperty(
        size=2, name='')
    bpy.types.Material.nns_tex_effect_mtx_3 = FloatVectorProperty(
        size=2, name='')
    tex_tiling_items = [
        ("repeat", "Repeat", '', 1),
        ("flip", "Flip", '', 2),
        ("clamp", "Clamp", '', 3)
    ]
    bpy.types.Material.nns_tex_tiling_u = EnumProperty(
        name="Tex tiling u", items=tex_tiling_items, update=update_nodes_mode)
    bpy.types.Material.nns_tex_tiling_v = EnumProperty(
        name="Tex tiling v", items=tex_tiling_items, update=update_nodes_mode)
    bpy.types.Material.nns_alpha = IntProperty(
        name="Alpha", min=0, max=31, default=31, update=update_nodes_alpha)
    bpy.types.Material.nns_tex_scale = FloatVectorProperty(
        size=2, name="Texture scale", default=(1, 1))
    bpy.types.Material.nns_tex_rotate = FloatProperty(name="Texture rotation")
    bpy.types.Material.nns_tex_translate = FloatVectorProperty(
        size=2, name="Texture translation")

    bpy.types.Material.nns_srt_translate = FloatVectorProperty(
        size=2, name="Translate", update=update_nodes_srt_hook)
    bpy.types.Material.nns_srt_scale = FloatVectorProperty(
        size=2, name="Scale", update=update_nodes_srt_hook, default=(1, 1))
    bpy.types.Material.nns_srt_rotate = FloatProperty(
        name="Rotate", update=update_nodes_srt_hook, subtype='ANGLE')

    print("Register frame handler")
    bpy.app.handlers.frame_change_pre.append(frame_change_handler)

    bpy.utils.register_class(CreateNNSMaterial)
    bpy.utils.register_class(NTR_PT_material_visual)
    bpy.utils.register_class(NTR_PT_material)
    bpy.utils.register_class(NTR_PT_material_keyframe)
    bpy.utils.register_class(NTR_UL_texframe)
    bpy.utils.register_class(NTR_PT_material_texframe)


def material_unregister():
    bpy.utils.unregister_class(NTRTexReference)
    bpy.utils.unregister_class(NewTexReference)
    bpy.utils.unregister_class(DeleteTexReference)

    bpy.utils.unregister_class(CreateNNSMaterial)
    bpy.utils.unregister_class(NTR_PT_material_visual)
    bpy.utils.unregister_class(NTR_PT_material)
    bpy.utils.unregister_class(NTR_PT_material_keyframe)
    bpy.utils.unregister_class(NTR_UL_texframe)
    bpy.utils.unregister_class(NTR_PT_material_texframe)
