import bpy
from mathutils import Vector
import xml.etree.ElementTree as ET
import math


settings = None


class NitroSRTInfo():
    def __init__(self):
        self.frame_size = 0
    
    def set_frame_size(self, size):
        if size > self.frame_size:
            self.frame_size = size


class NitroSRTData():
    def __init__(self, name):
        self.name = name
        if name == 'tex_scale_data':
            self.data = [1.0]
        else:
            self.data = [0.0]
    
    def add_data(self, data):
        """
        Adds and compresses data. Returns a tuple with head and size.
        """
        head = len(self.data)
        if all(elem == data[0] for elem in data):
            try:
                head = self.data.index(data[0])
            except ValueError:
                self.data.append(data[0])
            return (head, 1)
        else:
            length = len(data)
            if self.data[-1] == data[0]:
                data.pop(0)
                head = head - 1
            self.data.extend(data)
            return (head, length)


class NitroSRTReference():
    def __init__(self):
        self.data_head = 0
        self.data_size = 1
        self.frame_step = 1


class NitroSRTAnimation():
    def __init__(self, index, material_name):
        self.index = index
        self.material_name = material_name
        self.references = {
            'tex_scale_s': NitroSRTReference(),
            'tex_scale_t': NitroSRTReference(),
            'tex_rotate': NitroSRTReference(),
            'tex_translate_s': NitroSRTReference(),
            'tex_translate_t': NitroSRTReference()
        }
    
    def set_reference(self, name, head, size, step):
        reference = self.references[name]
        reference.data_head = head
        reference.data_size = size
        reference.frame_step = step


class NitroSRT():
    def __init__(self):
        self.info = NitroSRTInfo()
        self.scale_data = NitroSRTData('tex_scale_data')
        self.rotate_data = NitroSRTData('tex_rotate_data')
        self.translate_data = NitroSRTData('tex_translate_data')
        self.animations = []
    
    def collect(self):
        for mat in bpy.data.materials:
            if mat.nns_srt_translate.data.animation_data is not None:
                action = mat.nns_srt_translate.data.animation_data.action
                self.process_action(mat.name, action)
    
    def process_action(self, material_name, action):
        for curve in action.fcurves:
            data = []
            for i in range(int(action.frame_range[1]+1)):
                data.append(round(curve.evaluate(i), 6))
            self.info.set_frame_size(len(data))
            animation = self.find_animation(material_name)
            if curve.data_path == 'nns_srt_scale':
                result = self.scale_data.add_data(data)
                name = 'tex_scale_t' if curve.array_index else 'tex_scale_s'
                animation.set_reference(name, result[0], result[1], 1)
            elif curve.data_path == 'nns_srt_rotate':
                data = [math.degrees(x) for x in data]
                result = self.rotate_data.add_data(data)
                animation.set_reference('tex_rotate', result[0], result[1], 1)
            elif curve.data_path == 'nns_srt_translate':
                result = self.translate_data.add_data(data)
                name = 'tex_translate_t' if curve.array_index else 'tex_translate_s'
                animation.set_reference(name, result[0], result[1], 1)
    
    def find_animation(self, material_name):
        for animation in self.animations:
            if animation.material_name == material_name:
                return animation
        index = len(self.animations)
        self.animations.append(NitroSRTAnimation(index, material_name))
        return self.animations[-1]


def generate_srt_info(ita, info):
    tex_srt_info = ET.SubElement(ita, 'tex_srt_info')
    tex_srt_info.set('frame_size', str(info.frame_size))
    tex_srt_info.set('tool_start_frame', '0')
    tex_srt_info.set('tool_end_frame', str(info.frame_size))
    tex_srt_info.set('interpolation', 'frame')
    tex_srt_info.set('tex_matrix_mode', 'maya')
    tex_srt_info.set('compress_material', 'off')
    tex_srt_info.set('material_size', '1 1')
    tex_srt_info.set('frame_step_mode', '1')
    scale_tolerance = '{:.6f}'.format(settings['ita_scale_tolerance'])
    tex_srt_info.set('tolerance_tex_scale', scale_tolerance)
    rotate_tolerance = '{:.6f}'.format(settings['ita_rotate_tolerance'])
    tex_srt_info.set('tolerance_tex_rotate', rotate_tolerance)
    translate_tolerance = '{:.6f}'.format(settings['ita_translate_tolerance'])
    tex_srt_info.set('tolerance_tex_translate', translate_tolerance)


def generate_data(ita, str_data: NitroSRTData):
    tex_data = ET.SubElement(ita, str_data.name)
    tex_data.set('size', str(len(str_data.data)))
    data_string = ' '.join(['{:.6f}'.format(x) for x in str_data.data])
    tex_data.text = data_string


def generate_animations(ita, animations):
    tex_srt_anm_array = ET.SubElement(ita, 'tex_srt_anm_array')
    tex_srt_anm_array.set('size', str(len(animations)))
    for animation in animations:
        tex_srt_anm = ET.SubElement(tex_srt_anm_array, 'tex_srt_anm')
        tex_srt_anm.set('index', str(animation.index))
        tex_srt_anm.set('material_name', str(animation.material_name))

        for key, reference in animation.references.items():
            generate_reference(tex_srt_anm, key, reference)

def generate_reference(ita, name, reference):
    ref = ET.SubElement(ita, name)
    ref.set('frame_step', str(reference.frame_step))
    ref.set('data_size', str(reference.data_size))
    ref.set('data_head', str(reference.data_head))


def generate_body(ita, export_settings):
    global settings
    settings = export_settings

    srt = NitroSRT()
    srt.collect()

    generate_srt_info(ita, srt.info)
    generate_data(ita, srt.scale_data)
    generate_data(ita, srt.rotate_data)
    generate_data(ita, srt.translate_data)
    generate_animations(ita, srt.animations)
