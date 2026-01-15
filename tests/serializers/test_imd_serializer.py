import pytest
from pytest import FixtureRequest
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
        indirect=["fp_value"]
    )


@pytest.fixture
def fp_value(request: FixtureRequest) -> float:
    return getattr(request, "param", 0.0)


@pytest.fixture
def default_nitro_vertices(fp_value: float) -> list[NitroVertex]:
    return [NitroVertex(0, (fp_value, fp_value),
                        (fp_value, fp_value, fp_value), (0, 0, 0),
                        (fp_value, fp_value, fp_value))] * 4


@pytest.fixture
def default_nitro_model(default_nitro_vertices: list[NitroVertex],
                        fp_value: float) -> NitroModel:
    fp_vector = (fp_value, fp_value, fp_value)
    model_info = NitroModelInfo(1, ScalingRule.MAYA, VertexStyle.DIRECT,
                                fp_value, 1, TexMatrixMode.SOFTIMAGE_XSI,
                                CompressNode.UNITE, 20, 15, NitroBool.ON, 2, 1,
                                OutputTexture.USED, NitroBool.OFF,
                                NitroBool.ON)
    box_test = NitroModelBoxTest(123, fp_vector, fp_vector)
    tex_image = NitroTexImage("img0", 100, 60, TexFormat.DIRECT,
                              Color0Mode.COLOR, "pal0", Path("test/img.png"),
                              bytes(8), None)
    tex_palette = NitroTexPalette("pal0", bytes(8))
    material = NitroMaterial("mat0", NitroBool.ON, NitroBool.OFF, NitroBool.ON,
                             NitroBool.OFF, FaceMode.FRONT, 22, NitroBool.OFF,
                             PolygonMode.MODULATE, 0, NitroBool.ON,
                             NitroBool.OFF, NitroBool.ON, NitroBool.OFF,
                             NitroBool.ON, (23, 31, 17), (23, 31, 17),
                             (23, 31, 17), (23, 31, 17), NitroBool.OFF, "img0",
                             "pal0", TexTiling.REPEAT, (fp_value, fp_value),
                             fp_value, (fp_value, fp_value), TexGenMode.NRM,
                             TexGenStSrc.MATERIAL, [[fp_value] * 4] * 4)
    weight = NitroWeight(100, "joint0")
    envelope = NitroEnvelope([weight])
    matrix = NitroMatrix([envelope])
    primitive = NitroPrimitive(PrimitiveType.TRIANGLES, default_nitro_vertices)
    mtx_prim = NitroMtxPrim([0], [primitive])
    polygon = NitroPolygon("pol0", fp_vector, fp_vector, 2, NitroBool.ON,
                           NitroBool.ON, NitroBool.ON, [mtx_prim])
    display = NitroDisplay("mat0", "pol0", 0)
    root_node = NitroNode("root", NodeKind.MESH, None, "joint0", None, None,
                          NitroBool.OFF, BillboardSetting.OFF, fp_vector,
                          fp_vector, fp_vector, fp_vector, fp_vector, fp_value,
                          [display])
    joint_node = NitroNode("joint0", NodeKind.CHAIN, "root", None, None, None,
                           NitroBool.ON, BillboardSetting.OFF, fp_vector,
                           fp_vector, fp_vector)
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


def test_serialize_imd_vtx_pos_data(default_nitro_model: NitroModel):
    default_nitro_model.model_info.vertex_style = VertexStyle.INDEX
    vertices = [(1.0, 2.0, 1.0),
                (1.0, 2.0, 1.0),
                (2.0, 1.0, 2.0),
                (3.0, 4.0, 5.0)]
    primitive = NitroPrimitive(
        PrimitiveType.TRIANGLES,
        [NitroVertex(0, (0, 0), (0, 0, 0), (0, 0, 0), vertex)
         for vertex in vertices])
    mtx_prim = NitroMtxPrim([0], [primitive])
    polygon = NitroPolygon("pol0", (0, 0, 0), (0, 0, 0), 2, NitroBool.OFF,
                           NitroBool.OFF, NitroBool.OFF, [mtx_prim])
    default_nitro_model.polygons = [polygon]

    imd = serialize_imd(default_nitro_model)

    model_info = imd.find("./body/model_info")
    assert model_info is not None
    assert model_info.get("vertex_style") == VertexStyle.INDEX

    vtx_pos_data = imd.find("./body/vtx_pos_data")
    assert vtx_pos_data is not None
    assert vtx_pos_data.get("pos_size") == "7"
    assert vtx_pos_data.text == "1.000000, 2.000000, 1.000000, 2.000000, " \
                                "3.000000, 4.000000, 5.000000"


def test_serialize_imd_vtx_pos_data_none(default_nitro_model: NitroModel):
    imd = serialize_imd(default_nitro_model)

    model_info = imd.find("./body/model_info")
    assert model_info is not None
    assert model_info.get("vertex_style") == VertexStyle.DIRECT

    vtx_pos_data = imd.find("./body/vtx_pos_data")
    assert vtx_pos_data is None


@pytest.mark.parametrize("value", [12, -12])
def test_serialize_imd_vtx_pos_data_invalid(default_nitro_model: NitroModel,
                                            value: float):
    """
    Tests error raised if vtx_pos_data contains values lower than -8 and
    greater than 8.
    """
    default_nitro_model.model_info.vertex_style = VertexStyle.INDEX
    vertices = [NitroVertex(0, (0, 0), (0, 0, 0), (0, 0, 0),
                            (value, value, value))]
    primitive = NitroPrimitive(PrimitiveType.TRIANGLES, vertices)
    mtx_prim = NitroMtxPrim([0], [primitive])
    polygon = NitroPolygon("pol0", (0, 0, 0), (0, 0, 0), 2, NitroBool.OFF,
                           NitroBool.OFF, NitroBool.OFF, [mtx_prim])
    default_nitro_model.polygons = [polygon]

    with pytest.raises(VtxPosDataError):
        serialize_imd(default_nitro_model)


@fixed_point_format()
def test_serialize_imd_vtx_pos_data_formatting(default_nitro_model: NitroModel,
                                               fp_expected: str):
    default_nitro_model.model_info.vertex_style = VertexStyle.INDEX

    imd = serialize_imd(default_nitro_model)

    vtx_pos_data = imd.find("./body/vtx_pos_data")
    assert vtx_pos_data is not None
    assert vtx_pos_data.get("pos_size") == "3"
    assert vtx_pos_data.text == " ".join([fp_expected] * 3)


def test_serialize_imd_vtx_color_data(default_nitro_model: NitroModel):
    default_nitro_model.model_info.vertex_style = VertexStyle.INDEX
    colors = [(1, 2, 1),
              (1, 2, 1),
              (2, 1, 2),
              (3, 4, 5)]
    primitive = NitroPrimitive(
        PrimitiveType.TRIANGLES,
        [NitroVertex(0, (0, 0), (0, 0, 0), color, (0, 0, 0))
         for color in colors])
    mtx_prim = NitroMtxPrim([0], [primitive])
    polygon = NitroPolygon("pol0", (0, 0, 0), (0, 0, 0), 2, NitroBool.OFF,
                           NitroBool.ON, NitroBool.OFF, [mtx_prim])
    default_nitro_model.polygons = [polygon]

    imd = serialize_imd(default_nitro_model)

    model_info = imd.find("./body/model_info")
    assert model_info is not None
    assert model_info.get("vertex_style") == VertexStyle.INDEX

    vtx_color_data = imd.find("./body/vtx_color_data")
    assert vtx_color_data is not None
    assert vtx_color_data.get("color_size") == "7"
    assert vtx_color_data.text == "1 2 1 2 3 4 5"


def test_serialize_imd_vtx_color_data_none(default_nitro_model: NitroModel):
    imd = serialize_imd(default_nitro_model)

    model_info = imd.find("./body/model_info")
    assert model_info is not None
    assert model_info.get("vertex_style") == VertexStyle.DIRECT

    vtx_pos_data = imd.find("./body/vtx_pos_data")
    assert vtx_pos_data is None


@pytest.mark.parametrize("value", [32, -1])
def test_serialize_imd_vtx_color_data_invalid(default_nitro_model: NitroModel,
                                              value: int):
    """
    Tests error raised if vtx_color_data contains values lower than 0 and
    greater than 31.
    """
    default_nitro_model.model_info.vertex_style = VertexStyle.INDEX
    primitive = NitroPrimitive(
        PrimitiveType.TRIANGLES,
        [NitroVertex(0, (0, 0), (0, 0, 0), (value, value, value), (0, 0, 0))])
    mtx_prim = NitroMtxPrim([0], [primitive])
    polygon = NitroPolygon("pol0", (0, 0, 0), (0, 0, 0), 2, NitroBool.OFF,
                           NitroBool.ON, NitroBool.OFF, [mtx_prim])
    default_nitro_model.polygons = [polygon]

    with pytest.raises(VtxColorDataError):
        serialize_imd(default_nitro_model)


def test_serialize_imd_tex_img(default_nitro_model: NitroModel):
    imd = serialize_imd(default_nitro_model)

    tex_image_array = imd.find("./body/tex_image_array")
    assert tex_image_array is not None
    assert tex_image_array.get("size") == "1"

    tex_image = tex_image_array.find("tex_image")
    assert tex_image is not None
    assert tex_image.get("index") == "0"
    assert tex_image.get("name") == "img0"
    assert tex_image.get("width") == "128"
    assert tex_image.get("height") == "64"
    assert tex_image.get("original_width") == "100"
    assert tex_image.get("original_height") == "60"
    assert tex_image.get("format") == TexFormat.DIRECT
    assert tex_image.get("color0_mode") == Color0Mode.COLOR
    assert tex_image.get("palette_name") == "pal0"
    assert tex_image.get("path") == "test/img.png"

    bitmap = tex_image.find("bitmap")
    assert bitmap is not None
    assert bitmap.get("size") == "8"
    assert bitmap.text == "0000 0000 0000 0000"


def test_serialize_imd_tex_img_tex4x4(default_nitro_model: NitroModel):
    tex_image_4x4 = NitroTexImage("img0", 100, 60, TexFormat.TEX4X4,
                                  Color0Mode.COLOR, "pal0",
                                  Path("test/img.png"), bytes(8), bytes(8))
    default_nitro_model.tex_images = [tex_image_4x4]

    imd = serialize_imd(default_nitro_model)

    tex_image_array = imd.find("./body/tex_image_array")
    assert tex_image_array is not None
    assert tex_image_array.get("size") == "1"

    tex_image = tex_image_array.find("tex_image")
    assert tex_image is not None
    assert tex_image.get("index") == "0"
    assert tex_image.get("name") == "img0"
    assert tex_image.get("width") == "128"
    assert tex_image.get("height") == "64"
    assert tex_image.get("original_width") == "100"
    assert tex_image.get("original_height") == "60"
    assert tex_image.get("format") == TexFormat.TEX4X4
    assert tex_image.get("color0_mode") == Color0Mode.COLOR
    assert tex_image.get("palette_name") == "pal0"
    assert tex_image.get("path") == "test/img.png"

    bitmap = tex_image.find("bitmap")
    assert bitmap is not None
    assert bitmap.get("size") == "8"
    assert bitmap.text == "00000000 00000000"

    tex4x4 = tex_image.find("tex4x4")
    assert tex4x4 is not None
    assert tex4x4.get("size") == "8"
    assert tex4x4.text == "0000 0000 0000 0000"


def test_serialize_imd_tex_img_sorting(default_nitro_model: NitroModel):
    names = ["bbc2", "bbc4", "abc1", "bbc", "abc"]
    images = [NitroTexImage(name, 100, 60, TexFormat.DIRECT, Color0Mode.COLOR,
                            "pal0", Path("test/img.png"), bytes(8), None)
              for name in names]
    default_nitro_model.tex_images = images
    imd = serialize_imd(default_nitro_model)

    tex_image_array = imd.find("./body/tex_image_array")
    assert tex_image_array is not None
    assert tex_image_array.get("size") == "5"

    tex_images = tex_image_array.findall("tex_image")
    assert tex_images[0].get("name") == "abc"
    assert tex_images[1].get("name") == "abc1"
    assert tex_images[2].get("name") == "bbc"
    assert tex_images[3].get("name") == "bbc2"
    assert tex_images[4].get("name") == "bbc4"


def test_serialize_imd_tex_palette(default_nitro_model: NitroModel):
    imd = serialize_imd(default_nitro_model)

    tex_palette_array = imd.find("./body/tex_palette_array")
    assert tex_palette_array is not None
    assert tex_palette_array.get("size") == "2"

    tex_palette = tex_palette_array.find("tex_palette")
    assert tex_palette is not None
    assert tex_palette.get("index") == "0"
    assert tex_palette.get("name") == "pal0"
    assert tex_palette.get("color_size") == "8"
    assert tex_palette.text == "0000 0000 0000 0000"


def test_serialize_imd_tex_palette_sorting(default_nitro_model: NitroModel):
    names = ["bbc2", "bbc4", "abc1", "bbc", "abc"]
    palettes = [NitroTexPalette(name, bytes(8)) for name in names]
    default_nitro_model.tex_palettes = palettes

    imd = serialize_imd(default_nitro_model)

    tex_palette_array = imd.find("./body/tex_palette_array")
    assert tex_palette_array is not None
    assert tex_palette_array.get("size") == "2"

    tex_palette = tex_palette_array.findall("tex_palette")
    assert tex_palette[0].get("name") == "abc"
    assert tex_palette[1].get("name") == "abc1"
    assert tex_palette[2].get("name") == "bbc"
    assert tex_palette[3].get("name") == "bbc2"
    assert tex_palette[4].get("name") == "bbc4"


@fixed_point_format()
def test_serialize_imd_material(default_nitro_model: NitroModel,
                                fp_expected: str):
    imd = serialize_imd(default_nitro_model)

    material_array = imd.find("./body/material_array")
    assert material_array is not None

    material = material_array.find("material")
    assert material is not None
    assert material.get("index") == "0"
    assert material.get("name") == "mat0"
    assert material.get("light0") == "on"
    assert material.get("light1") == "off"
    assert material.get("light2") == "on"
    assert material.get("light3") == "off"
    assert material.get("face") == "front"
    assert material.get("alpha") == "22"
    assert material.get("wire_mode") == "off"
    assert material.get("polygon_mode") == "modulate"
    assert material.get("polygon_id") == "0"
    assert material.get("fog_flag") == "on"
    assert material.get("depth_test_decal") == "off"
    assert material.get("translucent_update_depth") == "on"
    assert material.get("render_1_pixel") == "off"
    assert material.get("far_clipping") == "on"
    assert material.get("diffuse") == "23 31 17"
    assert material.get("ambient") == "23 31 17"
    assert material.get("specular") == "23 31 17"
    assert material.get("emission") == "23 31 17"
    assert material.get("shininess_table_flag") == "off"
    assert material.get("tex_image_idx") == "0"
    assert material.get("tex_palette_idx") == "0"
    assert material.get("tex_tiling") == "repeat"
    assert material.get("tex_scale") == f"{fp_expected} {fp_expected}"
    assert material.get("tex_rotate") == fp_expected
    assert material.get("tex_translate") == f"{fp_expected} {fp_expected}"
    assert material.get("tex_gen_mode") == "none"
    assert material.get("tex_gen_st_src") == "material"
    assert material.get("tex_effect_mtx") == " ".join([fp_expected] * 16)


def test_serialize_imd_material_no_tex(default_nitro_model: NitroModel):
    material = NitroMaterial("mat0", NitroBool.ON, NitroBool.OFF, NitroBool.ON,
                             NitroBool.OFF, FaceMode.FRONT, 22, NitroBool.OFF,
                             PolygonMode.MODULATE, 0, NitroBool.ON,
                             NitroBool.OFF, NitroBool.ON, NitroBool.OFF,
                             NitroBool.ON, (23, 31, 17), (23, 31, 17),
                             (23, 31, 17), (23, 31, 17), NitroBool.OFF, None,
                             None)
    default_nitro_model.materials = [material]

    imd = serialize_imd(default_nitro_model)

    material_array = imd.find("./body/material_array")
    assert material_array is not None

    material = material_array.find("material")
    assert material is not None
    assert material.get("tex_image_idx") == "-1"
    assert material.get("tex_palette_idx") == "-1"
    assert material.get("tex_tiling") is None
    assert material.get("tex_scale") is None
    assert material.get("tex_rotate") is None
    assert material.get("tex_translate") is None
    assert material.get("tex_gen_mode") is None
    assert material.get("tex_gen_st_src") is None
    assert material.get("tex_effect_mtx") is None


@pytest.mark.parametrize(
        "value, expected",
        [
            (TexGenMode.NONE, False),
            (TexGenMode.TEX, False),
            (TexGenMode.POS, True),
            (TexGenMode.NRM, True)
        ])
def test_serialize_imd_material_tex_gen_mode(
        default_nitro_model: NitroModel,
        value: TexGenMode,
        expected: bool):
    """
    Tests that tex_gen_st_src and tex_effect_mtx should not be output when
    tex_gen_mode is 'none' or 'tex' but it should be output when tex_gen_mode
    is 'pos' or 'nrm'.
    """
    material = NitroMaterial("mat0", NitroBool.ON, NitroBool.OFF, NitroBool.ON,
                             NitroBool.OFF, FaceMode.FRONT, 22, NitroBool.OFF,
                             PolygonMode.MODULATE, 0, NitroBool.ON,
                             NitroBool.OFF, NitroBool.ON, NitroBool.OFF,
                             NitroBool.ON, (23, 31, 17), (23, 31, 17),
                             (23, 31, 17), (23, 31, 17), NitroBool.OFF, "img0",
                             "pal0", TexTiling.REPEAT, (1.0, 1.0), 1.0,
                             (1.0, 1.0), value, TexGenStSrc.MATERIAL,
                             [[1.0] * 4] * 4)
    default_nitro_model.materials = [material]

    imd = serialize_imd(default_nitro_model)

    material_array = imd.find("./body/material_array")
    assert material_array is not None

    material = material_array.find("material")
    assert material is not None
    if expected:
        assert material.get("tex_gen_st_src") is not None
        assert material.get("tex_effect_mtx") is not None
    else:
        assert material.get("tex_gen_st_src") is None
        assert material.get("tex_effect_mtx") is None
