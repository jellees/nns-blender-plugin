import bpy
import xml.etree.ElementTree as ET
from xml.dom import minidom


class ExportSettings():
    def __init__(self,
                 pretty_print):
        self.pretty_print = pretty_print


def generate_header(imd):
    head = ET.SubElement(imd, 'head')

    title = ET.SubElement(head, 'title')
    title.text = 'Model Data for NINTENDO NITRO-System'

    generator = ET.SubElement(head, 'generator')
    generator.set('name', 'Nitro plugin for Blender 2.8')
    generator.set('version', '0.0.1')


def generate_imd(filepath, settings):
    from . import export_imd

    imd = ET.Element('imd')
    generate_header(imd)
    body = ET.SubElement(imd, 'body')
    export_imd.generate_body(body, settings)

    output = ""
    if settings.pretty_print:
        output = minidom.parseString(ET.tostring(imd))
        output = output.toprettyxml(indent='   ')
    else:
        output = ET.tostring(imd, encoding='unicode')

    with open(filepath, 'w') as f:
        f.write(output)


def save(context, filepath, pretty_print):
    settings = ExportSettings(pretty_print)
    generate_imd(filepath, settings)
