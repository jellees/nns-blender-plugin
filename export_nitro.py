import bpy
import xml.etree.ElementTree as ET
from xml.dom import minidom
from . import local_logger as logger


def generate_header(imd):
    imd.set('version', '1.6.0')
    head = ET.SubElement(imd, 'head')

    title = ET.SubElement(head, 'title')
    title.text = 'Model Data for NINTENDO NITRO-System'

    generator = ET.SubElement(head, 'generator')
    generator.set('name', 'Nitro plugin for Blender 2.8')
    generator.set('version', '0.0.1')


def generate_imd(settings):
    from . import export_imd

    imd = ET.Element('imd')
    generate_header(imd)
    body = ET.SubElement(imd, 'body')
    export_imd.generate_body(body, settings)

    output = ""
    if settings['pretty_print']:
        output = minidom.parseString(ET.tostring(imd))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(imd, encoding='unicode')

    with open(settings['filepath'] + '.imd', 'w') as f:
        f.write(output)


def generate_ita(settings):
    from . import export_ita

    ita = ET.Element('ita')
    generate_header(ita)
    body = ET.SubElement(ita, 'body')
    export_ita.generate_body(body, settings)

    output = ""
    if settings['pretty_print']:
        output = minidom.parseString(ET.tostring(ita))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(ita, encoding='unicode')

    with open(settings['filepath'] + '.ita', 'w') as f:
        f.write(output)


def save(context, settings):
    logger.create_log(settings['filepath'], settings['generate_log'])
    generate_imd(settings)
    generate_ita(settings)
