import bpy
from mathutils import Vector
import xml.etree.ElementTree as ET
import math
from .nns_model import NitroModel
import os

settings = None


class NitroTXPInfo:
    def __init__(self):
        self.frame_size = 0

    def set_frame_size(self, size):
        if size > self.frame_size:
            self.frame_size = size

class NitroTXPImagePalette:
    def __init__(self):
        self.images = []
        self.palettes = []

    def find_image(self,img):
        for i in range(len(self.images)):
            if self.images[i] == img:
                return i
        self.images.append(img)
        return len(self.images)-1

    def find_palette(self,plt):
        for i in range(len(self.palettes)):
            if self.palettes[i] == plt:
                return i
        self.palettes.append(plt)
        return len(self.palettes)-1

class NitroTXPData:
    def __init__(self):
        self.frame_ids = []
        self.image_ids = []
        self.palette_ids = []

    def find_plt_img_frm(self,palettes,images,frames): 
        """entry other than the object :list of frames, list of images and list of palettes, all of the same length
        role : finds an id in self.frame_ids, self.palette_ids and self.image_ids where the corresponding input list is equal to a portion of the former list starting at the id, if its not found it adds the input lists to their corresponding list and returns the next id after the last id before the addition"""

        for i in range(len(self.frame_ids)): #same len for all elem tbh
            if self.frame_ids[i:i+len(frames)] == frames and self.palette_ids[i:i+len(palettes)] == palettes and self.image_ids[i:i+len(images)] == images:
                return i
        retval = len(self.palette_ids)
        self.frame_ids += frames
        self.image_ids += images
        self.palette_ids += palettes
        return retval


class NitroTXP:
    def __init__(self):
        self.info = NitroTXPInfo()
        self.imgPlt = NitroTXPImagePalette()
        self.data = NitroTXPData()
        self.pattern_anm = {}

    def collect(self, model: NitroModel):
        materials = model.materials

        for material in materials:
            bldMaterial = bpy.data.materials[material.blender_index]
            if bldMaterial.nns_texframe_reference:

                action = bldMaterial.animation_data.action
                self.info.set_frame_size( int(action.frame_range[1]) )

                self.set_images(bldMaterial,model)

                self.set_data(action,bldMaterial,model)

    def set_data(self,action,material,model):
        material_imgPattern = []
        material_pltPattern = []
        material_frmPattern = []

        for curve in action.fcurves:
            if curve.data_path.count("nns_texframe_reference_index"):
                prev = float("inf")
                for frame in range(int(action.frame_range[1]+1)):

                    evaluation = curve.evaluate(frame) 
                    if evaluation != prev:

                        prev = evaluation
                        idTex = int(evaluation)
                        tex = material.nns_texframe_reference[idTex]
                        path = os.path.realpath(bpy.path.abspath(tex.image.filepath))
                        texName = model.find_texture(path)

                        idTex = self.imgPlt.find_image(texName.name)
                        material_imgPattern.append(idTex)

                        idPlt = self.imgPlt.find_palette(texName.palette_name)
                        material_pltPattern.append(idPlt)

                        material_frmPattern.append(int(frame))

        head = self.data.find_plt_img_frm(material_pltPattern,material_imgPattern,material_frmPattern)
        self.pattern_anm[material.name] = [len(material_frmPattern), head]


    def set_images(self,material,model):

        for ref in material.nns_texframe_reference:
            path = os.path.realpath( bpy.path.abspath( ref.image.filepath ) )
            texName = model.find_texture(path)
            self.imgPlt.find_image(texName.name)
            self.imgPlt.find_palette(texName.palette_name)
            



def generate_txp_info(itp, info):
    tex_pattern_info = ET.SubElement(itp, 'tex_pattern_info')
    tex_pattern_info.set('frame_size', str(info.frame_size))
    tex_pattern_info.set('tool_start_frame', '0')
    tex_pattern_info.set('tool_end_frame', str(info.frame_size-1))
    tex_pattern_info.set('compress_material', 'off')
    tex_pattern_info.set('material_size', '1 1') 
    
def generate_txp_pattern_list_data(itp,img_plt):

    tex_pattern_LD = ET.SubElement(itp,"tex_pattern_list_data")
    tex_pattern_LD.set('image_size', str(len(img_plt.images)))
    tex_pattern_LD.set('palette_size', str(len(img_plt.palettes)))

    for imgID in range(len(img_plt.images)):
        pattern_image = ET.SubElement(tex_pattern_LD, "image_name")
        pattern_image.set("index", str(imgID))
        pattern_image.set("name", str(img_plt.images[imgID]))

    for pltID in range(len(img_plt.palettes)):
        pattern_image = ET.SubElement(tex_pattern_LD, "palette_name")
        pattern_image.set("index", str(pltID))
        pattern_image.set("name", str(img_plt.palettes[pltID]))
        

def generate_txp_pattern_data(itp, data):
    tex_pattern_data = ET.SubElement(itp,"tex_pattern_data")

    frame_idx = ET.SubElement(tex_pattern_data, "frame_idx")
    frame_idx.set("size",str(len(data.frame_ids)))
    frame_idx.text = data_to_string(data.frame_ids)

    image_idx = ET.SubElement(tex_pattern_data, "image_idx")
    image_idx.set("size",str(len(data.image_ids)))
    image_idx.text = data_to_string(data.image_ids)

    palette_idx = ET.SubElement(tex_pattern_data, "palette_idx")
    palette_idx.set("size",str(len(data.palette_ids)))
    palette_idx.text = data_to_string(data.palette_ids)

def generate_txp_anm_array(itp,anm):
    tex_pattern_anm_array = ET.SubElement(itp,"tex_pattern_anm_array")
    tex_pattern_anm_array.set("size", str(len(anm)))

    for keyID in range(len(anm.keys())):
        name = list(anm.keys())[keyID]
        tex_pattern_anm= ET.SubElement(tex_pattern_anm_array,"tex_pattern_anm")
        tex_pattern_anm.set("index",str(keyID))
        tex_pattern_anm.set("material_name",name)
        tex_pattern_anm.set("data_size",str(anm[name][0]))
        tex_pattern_anm.set("data_head",str(anm[name][1]))



def generate_body(itp, model:NitroModel, export_settings):
    global settings
    settings = export_settings

    txp = NitroTXP()
    txp.collect(model)

    generate_txp_info(itp, txp.info)
    generate_txp_pattern_list_data(itp, txp.imgPlt)
    generate_txp_pattern_data(itp,txp.data)
    generate_txp_anm_array(itp,txp.pattern_anm)





def data_to_string(data):
    strR = ""
    for i in data:
        strR+= str(i)+" "
    return strR