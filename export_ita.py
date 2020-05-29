import bpy
from mathutils import Vector
import xml.etree.ElementTree as ET
import math


settings = None


class NitroSRTData:
    def __init__(self, data):
        if all(elem == data[0] for elem in data):
            self.data = [data[0]]
        else:
            self.data = data
        self.head = 0


class NitroSRTAnmation:
    def __init__(self, index, material_name):
        self.index = index
        self.material_name = material_name
        self.tex_scale_s = NitroSRTData([1.0])
        self.tex_scale_t = NitroSRTData([1.0])
        self.tex_rotate = NitroSRTData([0.0])
        self.tex_translate_s = NitroSRTData([0.0])
        self.tex_translate_t = NitroSRTData([0.0])
    
    def add_data(self, type, index, data):
        if type == 'nns_srt_scale':
            if index == 0:
                self.tex_scale_s = NitroSRTData(data)
            elif index == 1:
                self.tex_scale_t = NitroSRTData(data)
        elif type == 'nns_srt_rotate':
            data = [math.degrees(x) for x in data]
            self.tex_rotate = NitroSRTData(data)
        elif type == 'nns_srt_translate':
            if index == 0:
                self.tex_translate_s = NitroSRTData(data)
            elif index == 1:
                self.tex_translate_t = NitroSRTData(data)


class NitroSRTAnimations:
    def __init__(self):
        self.animations = []
    
    def collect(self):
        for mat in bpy.data.materials:
            if mat.nns_srt_translate.data.animation_data is not None:
                action = mat.nns_srt_translate.data.animation_data.action
                self.process_action(mat.name, action)

    def process_action(self, name, action):
        for curve in action.fcurves:
            data = []
            for i in range(int(action.frame_range[1]+1)):
                data.append(round(curve.evaluate(i), 6))
            animation = self.find_animation(name)
            animation.add_data(curve.data_path, curve.array_index, data)

    def find_animation(self, material_name):
        for animation in self.animations:
            if animation.material_name == material_name:
                return animation
        index = len(self.animations)
        self.animations.append(NitroSRTAnmation(index, material_name))
        return self.animations[-1]


def generate_srt_info(ita):
    tex_srt_info = ET.SubElement(ita, 'tex_srt_info')
    tex_srt_info.set('frame_size', '60')
    tex_srt_info.set('tool_start_frame', '1')
    tex_srt_info.set('tool_end_frame', '60')
    tex_srt_info.set('interpolation', 'frame')
    tex_srt_info.set('tex_matrix_mode', 'maya')
    tex_srt_info.set('compress_material', 'off')
    tex_srt_info.set('material_size', '1 1')
    tex_srt_info.set('frame_step_mode', '1')
    tex_srt_info.set('tolerance_tex_scale', '0.100000')
    tex_srt_info.set('tolerance_tex_rotate', '0.100000')
    tex_srt_info.set('tolerance_tex_translate', '0.010000')


def generate_scale_data(ita, animations):
    tex_scale_data = ET.SubElement(ita, 'tex_scale_data')
    tex_scale_data.text = ''
    size = 0
    for animation in animations.animations:
        animation.tex_scale_s.head = size
        size = size + len(animation.tex_scale_s.data)
        for point in animation.tex_scale_s.data:
            point = '{:.6f}'.format(point)
            tex_scale_data.text = tex_scale_data.text + ' ' + point
        animation.tex_scale_t.head = size
        size = size + len(animation.tex_scale_t.data)
        for point in animation.tex_scale_t.data:
            point = '{:.6f}'.format(point)
            tex_scale_data.text = tex_scale_data.text + ' ' + point
    tex_scale_data.set('size', str(size))


def generate_rotate_data(ita, animations):
    tex_rotate_data = ET.SubElement(ita, 'tex_rotate_data')
    tex_rotate_data.text = ''
    size = 0
    for animation in animations.animations:
        animation.tex_rotate.head = size
        size = size + len(animation.tex_rotate.data)
        for point in animation.tex_rotate.data:
            point = '{:.6f}'.format(point)
            tex_rotate_data.text = tex_rotate_data.text + ' ' + point
    tex_rotate_data.set('size', str(size))


def generate_translate_data(ita, animations):
    tex_translate_data = ET.SubElement(ita, 'tex_translate_data')
    tex_translate_data.text = ''
    size = 0
    for animation in animations.animations:
        animation.tex_translate_s.head = size
        size = size + len(animation.tex_translate_s.data)
        for point in animation.tex_translate_s.data:
            point = '{:.6f}'.format(point)
            tex_translate_data.text = tex_translate_data.text + ' ' + point
        animation.tex_translate_t.head = size
        size = size + len(animation.tex_translate_t.data)
        for point in animation.tex_translate_t.data:
            point = '{:.6f}'.format(point)
            tex_translate_data.text = tex_translate_data.text + ' ' + point
    tex_translate_data.set('size', str(size))


def generate_reference_data(ita, animations):
    tex_srt_anm_array = ET.SubElement(ita, 'tex_srt_anm_array')
    tex_srt_anm_array.set('size', str(len(animations.animations)))
    for animation in animations.animations:
        tex_srt_anm = ET.SubElement(tex_srt_anm_array, 'tex_srt_anm')
        tex_srt_anm.set('index', str(animation.index))
        tex_srt_anm.set('material_name', str(animation.material_name))

        generate_reference(tex_srt_anm, 'tex_scale_s', animation.tex_scale_s)
        generate_reference(tex_srt_anm, 'tex_scale_t', animation.tex_scale_t)
        generate_reference(tex_srt_anm, 'tex_rotate', animation.tex_rotate)
        generate_reference(tex_srt_anm, 'tex_translate_s', animation.tex_translate_s)
        generate_reference(tex_srt_anm, 'tex_translate_t', animation.tex_translate_t)



def generate_reference(ita, name, data):
    ref = ET.SubElement(ita, name)
    ref.set('frame_step', '1')
    ref.set('data_size', str(len(data.data)))
    ref.set('data_head', str(data.head))
    



def generate_body(ita, export_settings):
    global settings
    settings = export_settings

    animations = NitroSRTAnimations()
    animations.collect()

    generate_srt_info(ita)
    generate_scale_data(ita, animations)
    generate_rotate_data(ita, animations)
    generate_translate_data(ita, animations)
    generate_reference_data(ita, animations)