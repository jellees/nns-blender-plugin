import bpy
import xml.etree.ElementTree as ET
from .nns_model import NitroModel
from .util import lin2s

# This is only imported to fix access to fcurves in the same way export_ita.py / export_itp.py already do.
if bpy.app.version >= (5, 0, 0):
    from bpy_extras import anim_utils

settings = None

# The channels a material color animation can drive, in the exact order g3dcvtr expects them written in <mat_color_anm>. Each entry is: (xml tag, material property name, array index or None for a scalar property, whether the raw value needs the same lin2s/sRGB conversion already used for the static diffuse/ambient/specular/emission colors in nns_model.py. Alpha is already stored as a plain 0-31 int, so it doesn't go through that conversion).
_CHANNELS = [
    ('diffuse_r', 'nns_diffuse', 0, True),
    ('diffuse_g', 'nns_diffuse', 1, True),
    ('diffuse_b', 'nns_diffuse', 2, True),
    ('ambient_r', 'nns_ambient', 0, True),
    ('ambient_g', 'nns_ambient', 1, True),
    ('ambient_b', 'nns_ambient', 2, True),
    ('specular_r', 'nns_specular', 0, True),
    ('specular_g', 'nns_specular', 1, True),
    ('specular_b', 'nns_specular', 2, True),
    ('emission_r', 'nns_emission', 0, True),
    ('emission_g', 'nns_emission', 1, True),
    ('emission_b', 'nns_emission', 2, True),
    ('polygon_alpha', 'nns_alpha', None, False),
]


class NitroIMAInfo:
    def __init__(self):
        self.frame_size = 0

    def set_frame_size(self, size):
        if size > self.frame_size:
            self.frame_size = size


class NitroIMAData:
    """Shared pool of quantized 0-31 color values.

    Deduplicated the exact same way NitroTXPData pools texture pattern
    frame data in export_itp.py: linear search for an existing matching
    run before appending new data. Most channels on a given animated material usually
    aren't animated at all (see the reference test_sphere1.ima: only
    diffuse_r/diffuse_b actually vary, every other channel is a single
    constant value that ends up reusing a value already sitting in the
    pool instead of being duplicated).
    """
    def __init__(self):
        self.values = []

    def find_or_add(self, values):
        n = len(values)
        for i in range(len(self.values) - n + 1):
            if self.values[i:i + n] == values:
                return i
        head = len(self.values)
        self.values.extend(values)
        return head


def _get_all_fcurves(action):
    if bpy.app.version >= (5, 0, 0):
        curves = []
        for slot in action.slots:
            channelbag = anim_utils.action_get_channelbag_for_slot(
                action, slot)
            if channelbag is not None:
                curves.extend(channelbag.fcurves)
        return curves
    return list(action.fcurves)


def _find_fcurve(all_fcurves, data_path, index):
    for fc in all_fcurves:
        if fc.data_path == data_path and (
                index is None or fc.array_index == index):
            return fc
    return None


def _sample_channel(all_fcurves, data_path, index, frame_size,
                     apply_gamma, static_value):
    """Returns frame_size quantized (0-31) values for one channel.

    If the channel isn't keyframed, this is just the material's
    current value repeated. Callers still get a full-length list back,
    it's up to the tolerance check afterward to collapse it down to a
    single constant entry in the data pool.
    """
    fcurve = _find_fcurve(all_fcurves, data_path, index)

    if fcurve is None:
        raw_values = [static_value] * frame_size
    else:
        raw_values = [fcurve.evaluate(frame) for frame in range(frame_size)]

    if apply_gamma:
        # Same conversion already used for the static diffuse/ambient/specular/emission colors in NitroModelMaterial, so an animated color and a static one encode consistently. lin2s() clamps its input itself, so an fcurve that overshoots slightly at a keyframe tangent doesn't need extra clamping here.
        return [int(round(lin2s(v) * 31)) for v in raw_values]
    return [max(0, min(31, int(round(v)))) for v in raw_values]


class NitroIMA:
    def __init__(self):
        self.info = NitroIMAInfo()
        self.data = NitroIMAData()
        # material_name -> [(tag, data_size, data_head), ...]
        self.mat_anm = {}

    def collect(self, model: NitroModel):
        tolerance = settings.get('ima_tolerance_color', 2)

        for material in model.materials:
            bld_material = bpy.data.materials[material.blender_index]

            action = None
            if (bld_material.animation_data is not None
                    and bld_material.animation_data.action is not None):
                action = bld_material.animation_data.action

            if action is None:
                continue

            all_fcurves = _get_all_fcurves(action)

            # Only worth an entry if something we actually care about on this material is keyframed at all.
            if not any(_find_fcurve(all_fcurves, path, idx) is not None
                       for _, path, idx, _ in _CHANNELS):
                continue

            frame_size = int(action.frame_range[1]) + 1
            self.info.set_frame_size(frame_size)

            channels = []
            for tag, path, idx, apply_gamma in _CHANNELS:
                prop_value = getattr(bld_material, path)
                static_value = prop_value[idx] if idx is not None else prop_value

                quantized = _sample_channel(
                    all_fcurves, path, idx, frame_size, apply_gamma,
                    static_value)

                lo, hi = min(quantized), max(quantized)
                if hi - lo <= tolerance:
                    # Close enough to flat (or unanimated), store as a single constant value instead of the full per-frame run.
                    final_values = [quantized[0]]
                else:
                    final_values = quantized

                head = self.data.find_or_add(final_values)
                channels.append((tag, len(final_values), head))

            self.mat_anm[material.name] = channels


def generate_mat_color_info(body, info, tolerance):
    mat_color_info = ET.SubElement(body, 'mat_color_info')
    mat_color_info.set('frame_size', str(info.frame_size))
    mat_color_info.set('tool_start_frame', '0')
    mat_color_info.set('tool_end_frame', str(max(info.frame_size - 1, 0)))
    mat_color_info.set('interpolation', 'frame')
    mat_color_info.set('compress_material', 'off')
    mat_color_info.set('material_size', '1 1')
    mat_color_info.set('frame_step_mode', '1')
    mat_color_info.set('tolerance_color', str(tolerance))


def generate_mat_color_data(body, data):
    mat_color_data = ET.SubElement(body, 'mat_color_data')
    mat_color_data.set('size', str(len(data.values)))
    mat_color_data.text = ' '.join(str(v) for v in data.values)


def generate_mat_color_anm_array(body, mat_anm):
    array = ET.SubElement(body, 'mat_color_anm_array')
    array.set('size', str(len(mat_anm)))
    for index, (material_name, channels) in enumerate(mat_anm.items()):
        anm = ET.SubElement(array, 'mat_color_anm')
        anm.set('index', str(index))
        anm.set('material_name', material_name)
        for tag, data_size, data_head in channels:
            channel = ET.SubElement(anm, tag)
            channel.set('frame_step', '1')
            channel.set('data_size', str(data_size))
            channel.set('data_head', str(data_head))


def generate_body(body, model: NitroModel, export_settings):
    global settings
    settings = export_settings

    ima_data = NitroIMA()
    ima_data.collect(model)

    generate_mat_color_info(
        body, ima_data.info, settings.get('ima_tolerance_color', 2))
    generate_mat_color_data(body, ima_data.data)
    generate_mat_color_anm_array(body, ima_data.mat_anm)
