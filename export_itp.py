import bpy
from mathutils import Vector
import xml.etree.ElementTree as ET
import math
from .nns_model import NitroModel


settings = None


class NitroTXPInfo:
    def __init__(self):
        self.frame_size = 0

    def set_frame_size(self, size):
        if size > self.frame_size:
            self.frame_size = size


class NitroTXP:
    def __init__(self):
        self.info = NitroTXPInfo()

    def collect(self, model: NitroModel):
        pass


def generate_txp_info(ita, info):
    tex_pattern_info = ET.SubElement(ita, 'tex_pattern_info')
    tex_pattern_info.set('frame_size', str(info.frame_size))
    tex_pattern_info.set('tool_start_frame', '0')
    tex_pattern_info.set('tool_end_frame', str(info.frame_size))
    tex_pattern_info.set('compress_material', 'off')
    tex_pattern_info.set('material_size', '1 1')


def generate_body(itp, model, export_settings):
    global settings
    settings = export_settings

    txp = NitroTXP()
    txp.collect(model)

    generate_txp_info(itp, txp.info)
