def read_tga_header(f):
    return {
        'id_field_length': int.from_bytes(f.read(1), byteorder='little'),
        'color_map_type': int.from_bytes(f.read(1), byteorder='little'),
        'image_type': int.from_bytes(f.read(1), byteorder='little'),
        'color_map_origin': int.from_bytes(f.read(2), byteorder='little'),
        'color_map_length': int.from_bytes(f.read(2), byteorder='little'),
        'color_map_entry_size': int.from_bytes(f.read(1), byteorder='little'),
        'image_x_origin': int.from_bytes(f.read(2), byteorder='little'),
        'image_y_origin': int.from_bytes(f.read(2), byteorder='little'),
        'image_width': int.from_bytes(f.read(2), byteorder='little'),
        'image_heigth': int.from_bytes(f.read(2), byteorder='little'),
        'image_pixel_size': int.from_bytes(f.read(1), byteorder='little'),
        'image_descriptor': int.from_bytes(f.read(1), byteorder='little'),
    }


def read_nitro_tga_id(f):
    return {
        'version': f.read(16).decode('utf-8').replace('\x00', ''),
        'nitro_data_offset': int.from_bytes(f.read(4), byteorder='little')
    }


def read_nitro_tga_data(f, offset):
    color_0_transp = False
    pltt_idx_data = None
    optpix_data = None

    # Get the end of the file
    f.seek(0, 2)
    end_of_file = f.tell()

    # Seek to Nitro TGA Data Offset
    f.seek(offset)

    while f.tell() + 12 <= end_of_file:
        sig = f.read(8).decode('ascii')
        length = int.from_bytes(f.read(4), byteorder='little')

        if sig == 'nns_frmt':
            tex_format = f.read(length - 12).decode('ascii')
        elif sig == 'nns_txel':
            texel_data = f.read(length - 12)
        elif sig == 'nns_pidx':
            pltt_idx_data = f.read(length - 12)
        elif sig == 'nns_pnam':
            palette_name = f.read(length - 12).decode('ascii')
        elif sig == 'nns_pcol':
            palette = f.read(length - 12)
        elif sig == 'nns_c0xp':
            color_0_transp = True
        elif sig == 'nns_gnam':
            generator_name = f.read(length - 12).decode('ascii')
        elif sig == 'nns_gver':
            generator_ver = f.read(length - 12).decode('ascii')
        elif sig == 'nns_imst':
            optpix_data = f.read(length - 12)
        elif sig == 'nns_endb':
            return {
                'tex_format': tex_format,
                'texel_data': texel_data,
                'pltt_idx_data': pltt_idx_data,
                'palette_name': palette_name,
                'palette': palette,
                'color_0_transp': color_0_transp,
                'generator_name': generator_name,
                'generator_ver': generator_ver,
                'optpix_data': optpix_data
            }


def read_nitro_tga(path):
    with open(path, "rb") as f:
        header = read_tga_header(f)
        nitro_tga_id = read_nitro_tga_id(f)
        nitro_data = read_nitro_tga_data(f, nitro_tga_id['nitro_data_offset'])

        f.close()

    return {
        'header': header,
        'nitro_tga_id': nitro_tga_id,
        'nitro_data': nitro_data,
    }


# These functions below purpose is inside the imd directly
# and they might need to be moved somewhere else
def format_hex_data(array, element_size):
    str_format = '0' + str(element_size * 2) + 'x'

    out_str = ''

    i = 0
    while i < len(array):
        temp = [array[j] for j in range(i, i + element_size)]
        element = int.from_bytes(temp, byteorder='little')

        out_str += format(element, str_format) + ' '
        i += element_size

    return out_str


def get_bitmap_data(tga):
    if tga['nitro_data']['tex_format'] == 'tex4x4':
        element_size = 4
    else:
        element_size = 2

    return format_hex_data(tga['nitro_data']['texel_data'], element_size)


def get_bitmap_size(tga):
    if tga['nitro_data']['tex_format'] == 'tex4x4':
        return int(len(tga['nitro_data']['texel_data']) / 4)
    else:
        return int(len(tga['nitro_data']['texel_data']) / 2)


def get_palette_data(tga):
    return format_hex_data(tga['nitro_data']['palette'], 2)


def get_palette_size(tga):
    return int(len(tga['nitro_data']['palette']) / 2)


# Used for tex4x4 only
def get_pltt_idx_data(tga):
    return format_hex_data(tga['nitro_data']['pltt_idx_data'], 2)


def get_pltt_idx_size(tga):
    return int(len(tga['nitro_data']['pltt_idx_data']) / 2)
