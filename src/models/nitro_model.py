from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class NitroBool(StrEnum):
    ON = "on"
    OFF = "off"


class ScalingRule(StrEnum):
    STANDARD = "standard"
    MAYA = "maya"
    SOFTIMAGE = "si3d"


class VertexStyle(StrEnum):
    DIRECT = "direct"
    INDEX = "index"


class TexMatrixMode(StrEnum):
    MAYA = "maya"
    SOFTIMAGE_3D = "si3d"
    SOFTIMAGE_XSI = "xsi"
    _3DSMAX = "3dsmax"


class CompressNode(StrEnum):
    NONE = "none"
    CULL = "cull"
    MERGE = "merge"
    UNITE = "unite"
    UNITE_COMBINE = "unite_combine"


class OutputTexture(StrEnum):
    USED = "used"
    ALL = "all"


class TexFormat(StrEnum):
    PALETTE4 = "palette4"
    PALETTE16 = "palette16"
    PALETTE256 = "palette256"
    TEX4X4 = "tex4x4"
    A3I5 = "a3i5"
    A5I3 = "a5i3"
    DIRECT = "direct"


class Color0Mode(StrEnum):
    COLOR = "color"
    TRANSPARENCY = "transparency"


class FaceMode(StrEnum):
    FRONT = "front"
    BACK = "back"
    BOTH = "both"


class PolygonMode(StrEnum):
    MODULATE = "modulate"
    DECAL = "decal"
    TOON_HIGHLIGHT = "toon_highlight"
    SHADOW = "shadow"


class TexTiling(StrEnum):
    CLAMP = "clamp"
    REPEAT = "repeat"
    FLIP = "flip"


class TexGenMode(StrEnum):
    NONE = "none"
    TEX = "tex"
    NRM = "nrm"
    POS = "pos"


class TexGenStSrc(StrEnum):
    POLYGON = "polygon"
    MATERIAL = "material"


class PrimitiveType(StrEnum):
    TRIANGLES = "triangles"
    QUADS = "quads"
    TRIANGLE_STRIP = "triangle_strip"
    QUAD_STRIP = "quad_strip"


class NodeKind(StrEnum):
    NULL = "null"
    MESH = "mesh"
    JOINT = "joint"
    CHAIN = "chain"
    EFFECTOR = "effector"


class BillboardSetting(StrEnum):
    ON = "on"
    OFF = "off"
    Y_ON = "y_on"


@dataclass
class NitroModelInfo:
    pos_scale: int
    scaling_rule: ScalingRule
    vertex_style: VertexStyle
    magnify: float
    tool_start_frame: int
    tex_matrix_mode: TexMatrixMode
    compress_node: CompressNode
    node_size_uncompressed: int
    node_size_compressed: int
    compress_material: NitroBool
    material_size_uncompressed: int
    material_size_compressed: int
    output_texture: OutputTexture
    force_full_weight: NitroBool
    use_primitive_strip: NitroBool


@dataclass(frozen=True)
class NitroModelBoxTest:
    pos_scale: int
    xyz: tuple[float, float, float]
    whd: tuple[float, float, float]


@dataclass
class NitroTexImage:
    name: str
    width: int
    height: int
    format: TexFormat
    color0_mode: Color0Mode
    palette_name: str
    path: Path
    bitmap: bytes
    tex4x4_palette_idx: bytes | None


@dataclass
class NitroTexPalette:
    name: str
    colors: bytes


@dataclass
class NitroMaterial:
    name: str
    light0: NitroBool
    light1: NitroBool
    light2: NitroBool
    light3: NitroBool
    face: FaceMode
    alpha: int
    wire_mode: NitroBool
    polygon_mode: PolygonMode
    polygon_id: int
    fog_flag: NitroBool
    depth_test_decal: NitroBool
    translucent_update_depth: NitroBool
    render_1_pixel: NitroBool
    far_clipping: NitroBool
    diffuse: tuple[int, int, int]
    ambient: tuple[int, int, int]
    specular: tuple[int, int, int]
    emission: tuple[int, int, int]
    shininess_table_flag: NitroBool
    tex_image: str | None = None
    tex_palette: str | None = None
    tex_tiling: TexTiling | None = None
    tex_scale: tuple[float, float] | None = None
    tex_rotate: float | None = None
    tex_translate: tuple[float, float] | None = None
    tex_gen_mode: TexGenMode | None = None
    tex_gen_st_src: TexGenStSrc | None = None
    tex_effect_mtx: list[list[float]] | None = None


@dataclass(frozen=True)
class NitroWeight:
    weight: int
    node: str


@dataclass(frozen=True)
class NitroEnvelope:
    weights: list[NitroWeight]


@dataclass
class NitroMatrix:
    envelopes: list[NitroEnvelope]


@dataclass
class NitroVertex:
    mtx_idx: int
    tex_coord: tuple[float, float]
    normal: tuple[float, float, float]
    color: tuple[int, int, int]
    position: tuple[float, float, float]


@dataclass
class NitroPrimitive:
    type: PrimitiveType
    vertices: list[NitroVertex]


@dataclass
class NitroMtxPrim:
    mtx_list: list[int]
    primitives: list[NitroPrimitive]


@dataclass
class NitroPolygon:
    name: str
    volume_min: tuple[float, float, float]
    volume_max: tuple[float, float, float]
    volume_r: float
    nrm_flag: NitroBool
    clr_flag: NitroBool
    tex_flag: NitroBool
    mtx_prim_list: list[NitroMtxPrim]


@dataclass
class NitroDisplay:
    material: str
    polygon: str
    priority: int


@dataclass
class NitroNode:
    name: str
    kind: NodeKind
    parent: str | None
    child: str | None
    brother_next: str | None
    brother_prev: str | None
    draw_mtx: NitroBool
    billboard: BillboardSetting
    scale: tuple[float, float, float]
    rotate: tuple[float, float, float]
    translate: tuple[float, float, float]
    volume_min: tuple[float, float, float] | None = None
    volume_max: tuple[float, float, float] | None = None
    volume_r: float | None = None
    displays: list[NitroDisplay] | None = None


@dataclass
class NitroModel:
    model_info: NitroModelInfo
    box_test: NitroModelBoxTest
    tex_images: list[NitroTexImage]
    tex_palettes: list[NitroTexPalette]
    materials: list[NitroMaterial]
    matrices: list[NitroMatrix]
    polygons: list[NitroPolygon]
    nodes: list[NitroNode]
