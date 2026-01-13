from xml.etree.ElementTree import ElementTree, Element, SubElement
from src.models.nitro_model import (NitroModel,
                                    NitroModelInfo,
                                    NitroModelBoxTest)
# from src.errors import VtxPosDataError


def _serialize_model_info(model_info: NitroModelInfo) -> Element:
    xml = Element("model_info")
    xml.set("pos_scale", str(model_info.pos_scale))
    xml.set("scaling_rule", str(model_info.scaling_rule))
    xml.set("vertex_style", str(model_info.vertex_style))
    xml.set("magnify", f"{model_info.magnify:.6f}")
    xml.set("tool_start_frame", str(model_info.tool_start_frame))
    xml.set("tex_matrix_mode", str(model_info.tex_matrix_mode))
    xml.set("compress_node", str(model_info.compress_node))
    node_size = "{} {}".format(
        model_info.node_size_uncompressed,
        model_info.node_size_compressed)
    xml.set("node_size", node_size)
    xml.set("compress_material", str(model_info.compress_material))
    material_size = "{} {}".format(
        model_info.material_size_uncompressed,
        model_info.material_size_compressed)
    xml.set("material_size", material_size)
    xml.set("output_texture", str(model_info.output_texture))
    xml.set("force_full_weight", str(model_info.force_full_weight))
    xml.set("use_primitive_strip", str(model_info.use_primitive_strip))
    return xml


def _serialize_box_test(box_test: NitroModelBoxTest) -> Element:
    xml = Element("box_test")
    xml.set("pos_scale", str(box_test.pos_scale))
    xml.set("xyz", " ".join(f"{x:.6f}" for x in box_test.xyz))
    xml.set("whd", " ".join(f"{x:.6f}" for x in box_test.whd))
    return xml


# def __serialize_vtx_pos_data(vtx_pos_data: list[float]) -> Element:
#     xml = Element("vtx_pos_data")
#     xml.set("pos_size", str(len(vtx_pos_data)))
#     for vtx_pos in vtx_pos_data:
#         if not -8 <= vtx_pos <= 8:
#             raise VtxPosDataError(f"Vertex position ({vtx_pos}) cannot be "
#                                   "smaller than -8 or greater than 8.")
#     xml.text = " ".join(f"{x:.6f}" for x in vtx_pos_data)
#     return xml


def serialize_imd(model: NitroModel) -> ElementTree:
    imd = Element("imd")
    body = SubElement(imd, "body")

    body.append(_serialize_model_info(model.model_info))
    body.append(_serialize_box_test(model.box_test))

    return ElementTree(imd)
