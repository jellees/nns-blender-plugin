import pytest
from src.errors import VtxPosDataError, VtxColorDataError
from src.models.nitro_model import (NitroModel, NitroModelInfo,
                                    NitroModelBoxTest, NitroTexImage,
                                    NitroTexPalette, NitroMaterial,
                                    NitroWeight, NitroEnvelope, NitroMatrix,
                                    NitroVertex, NitroPrimitive, NitroMtxPrim,
                                    NitroPolygon, NitroDisplay, NitroNode)
from src.models.nitro_model import (ScalingRule, VertexStyle, TexMatrixMode,
                                    CompressNode, NitroBool, OutputTexture,
                                    TexFormat, Color0Mode, FaceMode,
                                    PolygonMode, TexTiling, TexGenMode,
                                    TexGenStSrc, PrimitiveType, NodeKind,
                                    BillboardSetting)
from src.serializers.imd_serializer import serialize_imd
from pathlib import Path


FIXED_POINT_CASES = {
    "simple": (1.0, "1.000000"),
    "round_down": (1.1234564, "1.123456"),
    "round_up": (1.1234565, "1.123457"),
    "small": (0.0000012, "0.000001"),
    "negative": (-2.5, "-2.500000"),
    "large": (12345.6789, "12345.678900"),
}


def fixed_point_format():
    return pytest.mark.parametrize(
        "fp_value, fp_expected",
        FIXED_POINT_CASES.values(),
        ids=FIXED_POINT_CASES.keys(),
    )


@pytest.fixture
def default_nitro_vertices(fp_value: float) -> list[NitroVertex]:
    return [NitroVertex(0, (fp_value, fp_value),
                        (fp_value, fp_value, fp_value), (31, 0, 31),
                        (fp_value, fp_value, fp_value))] * 4


@pytest.fixture
def default_nitro_model(default_nitro_vertices: list[NitroVertex],
                        fp_value: float):
    vector = (fp_value, fp_value, fp_value)
    model_info = NitroModelInfo(1, ScalingRule.MAYA, VertexStyle.DIRECT,
                                fp_value, 1, TexMatrixMode.SOFTIMAGE_XSI,
                                CompressNode.UNITE, 20, 15, NitroBool.ON, 2, 1,
                                OutputTexture.USED, NitroBool.OFF,
                                NitroBool.ON)
    box_test = NitroModelBoxTest(123, vector, vector)
    tex_image = NitroTexImage("img0", 100, 60, TexFormat.DIRECT,
                              Color0Mode.COLOR, "pal0", Path("test/img.png"),
                              bytes(8), None)
    tex_palette = NitroTexPalette("pal0", bytes(8))
    tex_effect_mtx = (1, 0, 0, 0,
                      0, 1, 0, 0,
                      0, 0, 1, 0,
                      0, 0, 0, 1)
    material = NitroMaterial("mat0", NitroBool.ON, NitroBool.OFF, NitroBool.ON,
                             NitroBool.OFF, FaceMode.FRONT, 22, NitroBool.OFF,
                             PolygonMode.MODULATE, 0, NitroBool.ON,
                             NitroBool.OFF, NitroBool.ON, NitroBool.OFF,
                             NitroBool.ON, (23, 31, 17), (23, 31, 17),
                             (23, 31, 17), (23, 31, 17), NitroBool.OFF, "img0",
                             "pal0", TexTiling.REPEAT, (fp_value, fp_value),
                             2.0, (fp_value, fp_value), TexGenMode.NONE,
                             TexGenStSrc.MATERIAL, tex_effect_mtx)
    weight = NitroWeight(100, "joint0")
    envelope = NitroEnvelope([weight])
    matrix = NitroMatrix([envelope])
    primitive = NitroPrimitive(PrimitiveType.TRIANGLES, default_nitro_vertices)
    mtx_prim = NitroMtxPrim([0], [primitive])
    polygon = NitroPolygon("pol0", vector, vector, 2, NitroBool.ON,
                           NitroBool.ON, NitroBool.ON, [mtx_prim])
    display = NitroDisplay("mat0", "pol0", 0)
    root_node = NitroNode("root", NodeKind.MESH, None, "joint0", None, None,
                          NitroBool.OFF, BillboardSetting.OFF, vector,
                          vector, vector, vector, vector, 1.0,
                          [display])
    joint_node = NitroNode("joint0", NodeKind.CHAIN, "root", None, None, None,
                           NitroBool.ON, BillboardSetting.OFF, (1, 1, 1),
                           vector, vector)
    model = NitroModel(model_info, box_test, [tex_image], [tex_palette],
                       [material], [matrix], [polygon],
                       [root_node, joint_node])
    return model


@fixed_point_format()
def test_serialize_imd_model_info(default_nitro_model: NitroModel,
                                  fp_expected: str):
    imd = serialize_imd(default_nitro_model)

    element = imd.find("./body/model_info")
    assert element is not None
    pos_scale = element.get("pos_scale")
    assert pos_scale == "1"
    assert element.get("scaling_rule") == ScalingRule.MAYA
    assert element.get("vertex_style") == VertexStyle.DIRECT
    assert element.get("magnify") == fp_expected
    assert element.get("tool_start_frame") == "1"
    assert element.get("tex_matrix_mode") == TexMatrixMode.SOFTIMAGE_XSI
    assert element.get("compress_node") == CompressNode.UNITE
    assert element.get("node_size") == "20 15"
    assert element.get("compress_material") == NitroBool.ON
    assert element.get("material_size") == "2 1"
    assert element.get("output_texture") == OutputTexture.USED
    assert element.get("force_full_weight") == NitroBool.OFF
    assert element.get("use_primitive_strip") == NitroBool.ON


@fixed_point_format()
def test_serialize_imd_box_test(default_nitro_model: NitroModel,
                                fp_expected: str):
    imd = serialize_imd(default_nitro_model)

    element = imd.find("./body/box_test")
    assert element is not None
    assert element.get("pos_scale") == "123"
    assert element.get("xyz") == " ".join([fp_expected] * 3)
    assert element.get("whd") == " ".join([fp_expected] * 3)


@fixed_point_format()
def test_serialize_imd_vtx_pos_data(default_nitro_model: NitroModel,
                                    fp_expected: str):
    default_nitro_model.model_info.vertex_style = VertexStyle.INDEX

    imd = serialize_imd(default_nitro_model)

    model_info = imd.find("./body/model_info")
    assert model_info is not None
    assert model_info.get("vertex_style") == VertexStyle.INDEX

    vtx_pos_data = imd.find("./body/vtx_pos_data")
    assert vtx_pos_data is not None
    assert vtx_pos_data.get("pos_size") == "1"
    assert vtx_pos_data.text == fp_expected


# def test_serialize_imd_vtx_pos_data_none(nitro_model):
#     imd = serialize_imd(nitro_model)

#     model_info = imd.find("./body/model_info")
#     assert model_info.get("vertex_style") == VERTEX_STYLE_DIRECT

#     vtx_pos_data = imd.find("./body/vtx_pos_data")
#     assert vtx_pos_data is None


# def test_serialize_imd_invalid_vtx_pos_data(nitro_model_vertex_style_index):
#     """
#     Tests error raised if vtx_pos_data contains values lower than -8 and
#     greater than 8.
#     """
#     nitro_model_vertex_style_index.vtx_pos_data = [-12, 8, 12]
#     with pytest.raises(VtxPosDataError):
#         serialize_imd(nitro_model_vertex_style_index)


# def test_serialize_imd_vtx_color_data(nitro_model_vertex_style_index):
#     imd = serialize_imd(nitro_model_vertex_style_index)

#     model_info = imd.find("./body/model_info")
#     assert model_info.get("vertex_style") == VERTEX_STYLE_INDEX

#     vtx_color_data = imd.find("./body/vtx_color_data")
#     assert vtx_color_data.get("color_size") == "6"
#     assert vtx_color_data.text == "1 2 -3 4 5 -6"


# def test_serialize_imd_vtx_color_data_none(nitro_model):
#     imd = serialize_imd(nitro_model)

#     model_info = imd.find("./body/model_info")
#     assert model_info.get("vertex_style") == VERTEX_STYLE_DIRECT

#     vtx_pos_data = imd.find("./body/vtx_pos_data")
#     assert vtx_pos_data is None


# def test_serialize_imd_invalid_vtx_color_data(nitro_model_vertex_style_index):
#     """
#     Tests error raised if vtx_color_data contains values lower than 0 and
#     greater than 31.
#     """
#     nitro_model_vertex_style_index.vtx_color_data = [-12, 8, 32]
#     with pytest.raises(VtxColorDataError):
#         serialize_imd(nitro_model_vertex_style_index)
