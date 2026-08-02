import bpy
from mathutils import Quaternion
import xml.etree.ElementTree as ET
from math import degrees
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
            scene = bpy.context.scene
            mtxs = []
            frame_old = scene.frame_current
            for frame in range(scene.frame_start, scene.frame_end + 1):
                scene.frame_set(frame)

                transforms = {}
                for pose in obj.pose.bones:
                    transform = pose.matrix.copy()
                    if pose.parent:
                        inv = pose.parent.matrix.inverted()
                        transform = inv @ transform
                    transforms[pose.bone.name] = transform
                mtxs.append(transforms)

                # Althought this was used in the sm64ds plugin, it doesn't
                # work. You need to inverse multiply it with the parent
                # logically.
                # mtxs.append([b.matrix.copy() for b in obj.pose.bones])
            scene.frame_set(frame_old)

            self.info.set_frame_size(len(mtxs))
            for i, bone in enumerate(obj.data.bones):
                self.process_bone(bone, [m[bone.name] for m in mtxs])

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

    def process_bone(self, bone, transforms):
        node = self.model.find_node(bone.name)
        animation = self.find_animation(node.index)

        mag = self.model.settings['imd_magnification']

        scales = {'scale_x': [], 'scale_y': [], 'scale_z': []}
        rotations = {'rotate_x': [], 'rotate_y': [], 'rotate_z': []}
        trans = {'translate_x': [], 'translate_y': [], 'translate_z': []}

        # Get frames.
        for transform in transforms:
            scale = transform.to_scale()
            scales['scale_x'].append(round(scale[0], 6))
            scales['scale_y'].append(round(scale[1], 6))
            scales['scale_z'].append(round(scale[2], 6))

            rotate = transform.to_euler('XYZ')
            rotations['rotate_x'].append(round(degrees(rotate[0]), 6))
            rotations['rotate_y'].append(round(degrees(rotate[1]), 6))
            rotations['rotate_z'].append(round(degrees(rotate[2]), 6))

            translate = transform.to_translation()
            trans['translate_x'].append(round(translate[0] * mag, 6))
            trans['translate_y'].append(round(translate[1] * mag, 6))
            trans['translate_z'].append(round(translate[2] * mag, 6))

        # Set scale frames.
        for key in scales:
            data, frame_step = self.process_curve(
                scales[key],
                settings['ica_scale_tolerance'])
            result = self.scale_data.add_data(data)
            animation.set_reference(key, result[0], result[1], frame_step)

        # Set rotation frames.
        for key in rotations:
            data, frame_step = self.process_curve(
                rotations[key],
                settings['ica_rotate_tolerance'])
            result = self.rotate_data.add_data(data)
            animation.set_reference(key, result[0], result[1], frame_step)

        # Set translation frames.
        for key in trans:
            data, frame_step = self.process_curve(
                trans[key],
                settings['ica_translate_tolerance'])
            result = self.translate_data.add_data(data)
            animation.set_reference(key, result[0], result[1], frame_step)

    def process_curve(self, data, tolerance):
        result = []
        frame_step = 1

        if settings['ica_frame_step'] == "1":
            result = data
        elif settings['ica_frame_step'] == "2":
            frame_step = 2
            for i, v in enumerate(data):
                if i % frame_step == 0 or len(data) - i < frame_step:
                    result.append(v)
        elif settings['ica_frame_step'] == "4":
            frame_step = 4
            for i, v in enumerate(data):
                if i % frame_step == 0 or len(data) - i < frame_step:
                    result.append(v)

        # Calculate tolerance.
        min_value = result[0]
        max_value = result[0]
        for v in result:
            min_value = min(min_value, v)
            max_value = max(max_value, v)
        value_range = max_value - min_value
        if value_range < tolerance:
            frame_step = 1
            result = [result[0]]

        return (result, frame_step)

    def find_animation(self, index) -> NitroBCAAnimation:
        for animation in self.animations:
            if animation.index == index:
                return animation
        self.animations.append(NitroBCAAnimation(index))
        return self.animations[-1]


def generate_anm_info(ica, info, model):
    node_anm_info = ET.SubElement(ica, 'node_anm_info')
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
    scale_tolerance = '{:.6f}'.format(settings['ica_scale_tolerance'])
    node_anm_info.set('tolerance_scale', scale_tolerance)
    rotate_tolerance = '{:.6f}'.format(settings['ica_rotate_tolerance'])
    node_anm_info.set('tolerance_rotate', rotate_tolerance)
    translate_tolerance = '{:.6f}'.format(settings['ica_translate_tolerance'])
    node_anm_info.set('tolerance_translate', translate_tolerance)


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

    generate_anm_info(ica, bca.info, model)
    generate_data(ica, bca.scale_data)
    generate_data(ica, bca.rotate_data)
    generate_data(ica, bca.translate_data)
    generate_animations(ica, bca.animations)
