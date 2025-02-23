import xml.etree.ElementTree as ET
from xml.dom import minidom
from . import local_logger as logger
from .nns_model import NitroModel
import os
from .version import get_version_str


def generate_header(imd, data_name):
    imd.set('version', '1.6.0')
    head = ET.SubElement(imd, 'head')

    title = ET.SubElement(head, 'title')
    title.text = data_name + ' for NINTENDO NITRO-System'

    generator = ET.SubElement(head, 'generator')
    generator.set('name', 'Nitro plugin for Blender 2.8')
    generator.set('version', get_version_str())


def generate_imd(settings, model):
    from . import export_imd

    imd = ET.Element('imd')
    generate_header(imd, 'Model Data')
    body = ET.SubElement(imd, 'body')
    export_imd.generate_body(body, model, settings)

    output = ""
    if settings['pretty_print']:
        output = minidom.parseString(ET.tostring(imd, encoding='unicode'))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(imd, encoding='unicode')

    with open(settings['filepath'] + '.imd', 'w') as f:
        f.write(output)


def generate_ita(settings):
    from . import export_ita

    ita = ET.Element('ita')
    generate_header(ita, 'Texture SRT Animation Data')
    body = ET.SubElement(ita, 'body')
    export_ita.generate_body(body, settings)

    output = ""
    if settings['pretty_print']:
        output = minidom.parseString(ET.tostring(ita, encoding='unicode'))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(ita, encoding='unicode')

    with open(settings['filepath'] + '.ita', 'w') as f:
        f.write(output)


def generate_ica(settings, model):
    from . import export_ica

    ica = ET.Element('ica')
    generate_header(ica, 'Character Animation Data')
    body = ET.SubElement(ica, 'body')
    export_ica.generate_body(body, model, settings)

    output = ""
    if settings['pretty_print']:
        output = minidom.parseString(ET.tostring(ica, encoding='unicode'))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(ica, encoding='unicode')

    with open(settings['filepath'] + '.ica', 'w') as f:
        f.write(output)


def generate_itp(settings, model):
    from . import export_itp

    itp = ET.Element('itp')
    generate_header(itp, 'Texture Pattern Animation Data')
    body = ET.SubElement(itp, 'body')
    export_itp.generate_body(body, model, settings)

    output = ""
    if settings['pretty_print']:
        output = minidom.parseString(ET.tostring(itp, encoding='unicode'))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(itp, encoding='unicode')

    with open(settings['filepath'] + '.itp', 'w') as f:
        f.write(output)


def save(context, settings):

    settings['filepath'] = os.path.splitext(settings['filepath'])[0]

    logger.create_log(settings['filepath'], settings['generate_log'])

    model = None

    if (settings['imd_export']
       or settings['ica_export']
       or settings['itp_export']):
        model = NitroModel(settings)
        model.collect()

    if settings['ita_export']:
        generate_ita(settings)
    if settings['ica_export']:
        generate_ica(settings, model)
    if settings['itp_export']:
        generate_itp(settings, model)
    # Generate the imd as last because the other files may have changed things.
    if settings['imd_export']:
        generate_imd(settings, model)
