import xml.etree.ElementTree as ET
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
    generator.set('name', 'Nitro plugin for Blender')
    generator.set('version', get_version_str())


def _serialize(root, pretty_print):
    """Turn an ElementTree root into a final XML string.

    Previously this always went through xml.dom.minidom (parseString +
    toprettyxml), which re-parses the whole document into a second, much
    heavier DOM tree purely to indent it. minidom's pretty-printer is a
    pure-Python implementation that scales very poorly with document size,
    and for a model with a few thousand vertices/commands it could easily
    become the single slowest step of the whole export.

    xml.etree.ElementTree.indent() (standard library since Python 3.9,
    which is well below what Blender 5.2 ships) indents the tree in place,
    without a second parse pass, and is dramatically faster for large
    documents. It's kept as a soft dependency with a minidom fallback in
    case this ever runs under an unexpectedly old Python.
    """
    if pretty_print:
        if hasattr(ET, 'indent'):
            ET.indent(root, space='   ')
            output = ET.tostring(root, encoding='unicode')
            # ET always writes self-closing tags with a space before the slash ("<tag />"), unlike minidom's "<tag/>". IMD files are made almost entirely of leaf elements like <pos_xyz/> and <nrm/>, one or more per vertex, so this one byte per tag adds up to a measurable size difference on models with vertex counts even though it's pure whitespace, the parsed XML content is identical either way. Stripping it back out keeps the speed win from ET.indent() while keeping file size close to what the original plugin produced.
            return output.replace(' />', '/>')
        else:
            # Fallback for very old Python versions only.
            from xml.dom import minidom
            return minidom.parseString(
                ET.tostring(root, encoding='unicode')
            ).toprettyxml(indent='   ')
    return ET.tostring(root, encoding='unicode')


def generate_imd(settings, model):
    from . import export_imd

    imd = ET.Element('imd')
    generate_header(imd, 'Model Data')
    body = ET.SubElement(imd, 'body')
    export_imd.generate_body(body, model, settings)

    output = _serialize(imd, settings['pretty_print'])

    with open(settings['filepath'] + '.imd', 'w') as f:
        f.write(output)


def generate_ita(settings):
    from . import export_ita

    ita = ET.Element('ita')
    generate_header(ita, 'Texture SRT Animation Data')
    body = ET.SubElement(ita, 'body')
    export_ita.generate_body(body, settings)

    output = _serialize(ita, settings['pretty_print'])

    with open(settings['filepath'] + '.ita', 'w') as f:
        f.write(output)


def generate_ica(settings, model):
    from . import export_ica

    ica = ET.Element('ica')
    generate_header(ica, 'Character Animation Data')
    body = ET.SubElement(ica, 'body')
    export_ica.generate_body(body, model, settings)

    output = _serialize(ica, settings['pretty_print'])

    with open(settings['filepath'] + '.ica', 'w') as f:
        f.write(output)


def generate_itp(settings, model):
    from . import export_itp

    itp = ET.Element('itp')
    generate_header(itp, 'Texture Pattern Animation Data')
    body = ET.SubElement(itp, 'body')
    export_itp.generate_body(body, model, settings)

    output = _serialize(itp, settings['pretty_print'])

    with open(settings['filepath'] + '.itp', 'w') as f:
        f.write(output)


def generate_ima(settings, model):
    from . import export_ima

    ima = ET.Element('ima')
    generate_header(ima, 'Material Color Animation Data')
    body = ET.SubElement(ima, 'body')
    export_ima.generate_body(body, model, settings)

    output = _serialize(ima, settings['pretty_print'])

    with open(settings['filepath'] + '.ima', 'w') as f:
        f.write(output)


def save(context, settings):

    settings['filepath'] = os.path.splitext(settings['filepath'])[0]

    logger.create_log(settings['filepath'], settings['generate_log'])

    try:
        model = None

        if (settings['imd_export']
           or settings['ica_export']
           or settings['itp_export']
           or settings.get('ima_export', False)):
            model = NitroModel(settings)
            model.collect()

        if settings['ita_export']:
            generate_ita(settings)
        if settings['ica_export']:
            generate_ica(settings, model)
        if settings['itp_export']:
            generate_itp(settings, model)
        if settings.get('ima_export', False):
            generate_ima(settings, model)
        # Generate the imd as last because the other files may have changed
        # things.
        if settings['imd_export']:
            generate_imd(settings, model)

        return model.warnings if model is not None else []
    finally:
        # Always release the log file handle, even if the export raises.
        logger.close_log()

