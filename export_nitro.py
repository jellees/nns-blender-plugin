import bpy
import xml.etree.ElementTree as ET
from xml.dom import minidom


def generate_header(imd):

    head = ET.SubElement(imd, 'head')

    title = ET.SubElement(head, 'title')
    title.text = "Model Data for NINTENDO NITRO-System"

    generator = ET.SubElement(head, 'generator')
    generator.set('name','Nitro plugin for Blender 2.8')
    generator.set('version','0.0.1')


def generate_imd(filepath):
    
    from . import export_imd
    
    imd = ET.Element('imd')
    generate_header(imd)
    body = ET.SubElement(imd, 'body')
    export_imd.generate_body(body)

    pretty_imd = minidom.parseString(ET.tostring(imd)).toprettyxml(indent="   ")

    with open(filepath, "w") as f:
        f.write(pretty_imd)


def save(context, filepath):
    
    generate_imd(filepath)
