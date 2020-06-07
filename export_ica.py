import bpy
from mathutils import Quaternion
import xml.etree.ElementTree as ET
import math
from .nns_model import NitroModel


settings = None


class NitroBCAInfo():
    def __init__(self):
        self.frame_size = 0

    def set_frame_size(self, size):
        if size > self.frame_size:
            self.frame_size = size


class NitroBCAData():
    def __init__(self, name):
        self.name = name
        if name == 'node_scale_data':
            self.data = [1.0]
        else:
            self.data = [0.0]

    def find_in_data(self, x):
        l1, l2 = len(self.data), len(x)
        for i in range(l1):
            if self.data[i:i+l2] == x:
                return i
        return -1

    def add_data(self, data):
        """
        Adds and compresses data. Returns a tuple with head and size.
        """
        head = len(self.data)
        if all(elem == data[0] for elem in data):
            # This animation consists of one element.
            # Try to find if the value already exist
            # otherwise add it.
            try:
                head = self.data.index(data[0])
            except ValueError:
                self.data.append(data[0])
            return (head, 1)
        else:
            # Try to find the pattern in the existing
            # data first.
            length = len(data)
            index = self.find_in_data(data)
            if index != -1:
                # Found the pattern, index is now the head.
                head = index
            else:
                # Didn't find anything, try checking if the
                # last inserted value is equal to the first
                # value in the data.
                if self.data[-1] == data[0]:
                    data.pop(0)
                    head = head - 1
                self.data.extend(data)
            return (head, length)


class NitroBCAReference():
    def __init__(self):
        self.data_head = -1
        self.data_size = -1
        self.frame_step = 1


class NitroBCAAnimation():
    def __init__(self, index):
        self.index = index
        self.references = {
            'scale_x': NitroBCAReference(),
            'scale_y': NitroBCAReference(),
            'scale_z': NitroBCAReference(),
            'rotate_x': NitroBCAReference(),
            'rotate_y': NitroBCAReference(),
            'rotate_z': NitroBCAReference(),
            'translate_x': NitroBCAReference(),
            'translate_y': NitroBCAReference(),
            'translate_z': NitroBCAReference(),
        }

    def set_reference(self, name, head, size, step):
        reference = self.references[name]
        reference.data_head = head
        reference.data_size = size
        reference.frame_step = step


class NitroBCA():
    def __init__(self, model: NitroModel):
        self.info = NitroBCAInfo()
        self.scale_data = NitroBCAData('node_scale_data')
        self.rotate_data = NitroBCAData('node_rotate_data')
        self.translate_data = NitroBCAData('node_translate_data')
        self.animations = []
        self.model = model

    def collect(self):
        # Make a reference for each node first.
        for node in self.model.nodes:
            self.find_animation(node.index)

        for obj in bpy.context.view_layer.objects:
            if obj.type != 'ARMATURE':
                continue
            if obj.animation_data and obj.animation_data.action:
                action = obj.animation_data.action
                for bone in obj.data.bones:
                    self.process_bone(action, bone)

        # Set the proper data for each non-animated node.
        for animation in self.animations:
            node = self.model.nodes[animation.index]
            scale = {
                'scale_x': round(node.scale[0], 6),
                'scale_y': round(node.scale[1], 6),
                'scale_z': round(node.scale[2], 6)
            }
            for key in scale:
                if animation.references[key].data_head == -1:
                    result = self.scale_data.add_data([scale[key]])
                    animation.set_reference(key, result[0], result[1], 1)

            rotate = {
                'rotate_x': round(node.rotate[0], 6),
                'rotate_y': round(node.rotate[1], 6),
                'rotate_z': round(node.rotate[2], 6)
            }
            for key in rotate:
                if animation.references[key].data_head == -1:
                    result = self.rotate_data.add_data([rotate[key]])
                    animation.set_reference(key, result[0], result[1], 1)

            translate = {
                'translate_x': round(node.translate[0], 6),
                'translate_y': round(node.translate[1], 6),
                'translate_z': round(node.translate[2], 6)
            }
            for key in translate:
                if animation.references[key].data_head == -1:
                    result = self.translate_data.add_data([translate[key]])
                    animation.set_reference(key, result[0], result[1], 1)

    def process_bone(self, action, bone):
        node = self.model.find_node(bone.name)

        # Get scale frames.
        if self.do_keyframes_exist(action, bone, 'scale'):
            references = ['scale_x', 'scale_z', 'scale_y']
            for idx, reference in enumerate(references):
                frames = self.get_frames(action, bone, 'scale', idx)
                if frames:
                    start_value = 0
                    if reference == 'scale_x':
                        start_value = node.scale[0]
                    if reference == 'scale_y':
                        start_value = node.scale[1]
                    if reference == 'scale_z':
                        start_value = node.scale[2]
                    frames = [x + start_value for x in frames]
                    result = self.scale_data.add_data(frames)
                    animation = self.find_animation(node.index)
                    animation.set_reference(reference, result[0], result[1], 1)

        # Get rotation frames.
        if self.do_keyframes_exist(action, bone, 'rotation_quaternion'):
            frames = self.get_rotation_frames(action, bone)
            frames['rotate_x'] = [
                x + float(node.rotate[0]) for x in frames['rotate_x']]
            frames['rotate_y'] = [
                x + float(node.rotate[1]) for x in frames['rotate_y']]
            frames['rotate_z'] = [
                x + float(node.rotate[2]) for x in frames['rotate_z']]
            animation = self.find_animation(node.index)
            for key in frames:
                result = self.rotate_data.add_data(frames[key])
                animation.set_reference(key, result[0], result[1], 1)

        # Get location frames.
        if self.do_keyframes_exist(action, bone, 'location'):
            references = ['translate_x', 'translate_z', 'translate_y']
            for idx, reference in enumerate(references):
                frames = self.get_frames(action, bone, 'location', idx)
                if frames:
                    start_value = 0
                    if reference == 'translate_x':
                        start_value = node.translate[0]
                    if reference == 'translate_y':
                        start_value = node.translate[1]
                    if reference == 'translate_z':
                        start_value = node.translate[2]
                    frames = [x + start_value for x in frames]
                    result = self.translate_data.add_data(frames)
                    animation = self.find_animation(node.index)
                    animation.set_reference(reference, result[0], result[1], 1)

    def do_keyframes_exist(self, action, bone, name):
        name = 'pose.bones["' + bone.name + '"].' + name
        for curve in action.fcurves:
            if curve.data_path == name:
                return True
        return False

    def get_frames(self, action, bone, name, index):
        name = 'pose.bones["' + bone.name + '"].' + name
        frames = []
        for curve in action.fcurves:
            if curve.data_path == name and curve.array_index == index:
                frame_range = action.frame_range
                self.info.set_frame_size(int(frame_range[1] - frame_range[0]))
                for i in range(int(frame_range[0]), int(frame_range[1])):
                    value = curve.evaluate(i)
                    if name == 'location':
                        value *= self.model.settings['imd_magnification']
                        if index == 2:
                            value = -value
                    frames.append(round(value, 6))
        return frames

    def get_rotation_frames(self, action, bone):
        frames = {
            'rotate_x': [],
            'rotate_y': [],
            'rotate_z': [],
        }
        frame_range = action.frame_range
        self.info.set_frame_size(int(frame_range[1] - frame_range[0]))
        for i in range(int(frame_range[0]), int(frame_range[1])):
            rotation = self.get_quaternion(action, bone, i).to_euler()
            frames['rotate_x'].append(round(math.degrees(rotation[0]), 6))
            frames['rotate_y'].append(round(math.degrees(rotation[2]), 6))
            frames['rotate_z'].append(round(math.degrees(-rotation[1]), 6))
        return frames

    def get_quaternion(self, action, bone, frame):
        name = 'pose.bones["' + bone.name + '"].rotation_quaternion'
        values = [0, 0, 0, 0]
        for curve in action.fcurves:
            if curve.data_path == name:
                values[curve.array_index] = curve.evaluate(frame)
        return Quaternion(values)

    def find_animation(self, index) -> NitroBCAAnimation:
        for animation in self.animations:
            if animation.index == index:
                return animation
        self.animations.append(NitroBCAAnimation(index))
        return self.animations[-1]


def generate_srt_info(ita, info, model):
    node_anm_info = ET.SubElement(ita, 'node_anm_info')
    node_anm_info.set('frame_size', str(info.frame_size))
    node_anm_info.set('scaling_rule', 'standard')
    node_anm_info.set('magnify', str(settings['imd_magnification']))
    node_anm_info.set('tool_start_frame', '0')
    node_anm_info.set('tool_end_frame', str(info.frame_size))
    node_anm_info.set('interpolation', 'frame')
    node_anm_info.set('interp_end_to_start', 'off')
    node_anm_info.set('compress_node', settings['imd_compress_nodes'])
    node_anm_info.set('node_size',
                      str(len(model.nodes)) + ' ' + str(len(model.nodes)))
    node_anm_info.set('frame_step_mode', '1')
    # scale_tolerance = '{:.6f}'.format(settings['ita_scale_tolerance'])
    # node_anm_info.set('tolerance_tex_scale', scale_tolerance)
    # rotate_tolerance = '{:.6f}'.format(settings['ita_rotate_tolerance'])
    # node_anm_info.set('tolerance_tex_rotate', rotate_tolerance)
    # translate_tolerance = '{:.6f}'.format(settings['ita_translate_tolerance'])
    # node_anm_info.set('tolerance_tex_translate', translate_tolerance)
    node_anm_info.set('tolerance_scale', '0.000100')
    node_anm_info.set('tolerance_rotate', '0.000100')
    node_anm_info.set('tolerance_translate', '0.000100')


def generate_data(ica, bca_data: NitroBCAData):
    node_data = ET.SubElement(ica, bca_data.name)
    node_data.set('size', str(len(bca_data.data)))
    data_string = ' '.join(['{:.6f}'.format(x) for x in bca_data.data])
    node_data.text = data_string


def generate_animations(ica, animations):
    node_anm_array = ET.SubElement(ica, 'node_anm_array')
    node_anm_array.set('size', str(len(animations)))
    for animation in animations:
        node_anm = ET.SubElement(node_anm_array, 'node_anm')
        node_anm.set('index', str(animation.index))

        for key, reference in animation.references.items():
            generate_reference(node_anm, key, reference)


def generate_reference(ica, name, reference):
    ref = ET.SubElement(ica, name)
    ref.set('frame_step', str(reference.frame_step))
    ref.set('data_size', str(reference.data_size))
    ref.set('data_head', str(reference.data_head))


def generate_body(ica, model, export_settings):
    global settings
    settings = export_settings

    bca = NitroBCA(model)
    bca.collect()

    generate_srt_info(ica, bca.info, model)
    generate_data(ica, bca.scale_data)
    generate_data(ica, bca.rotate_data)
    generate_data(ica, bca.translate_data)
    generate_animations(ica, bca.animations)
