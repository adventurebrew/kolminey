import io
import operator
import struct

import numpy as np


HEADER = struct.Struct('<7I')
header_fields = (
    'version',
    'transparent_color',
    'width',
    'height',
    'scan_len',
    'unknown2',
    'unknown3',
)


def read_uint32_le(stream):
    return int.from_bytes(stream.read(4), 'little')


def decode_xmg(data):
    header = dict(zip(header_fields, HEADER.unpack(data[:HEADER.size]), strict=True))
    width, height, transparent_color = operator.itemgetter('width', 'height', 'transparent_color')(header)
    return decode_xmg_image(data[HEADER.size:], width, height, transparent_color)


def decode_xmg_image(data, width, height, transparent_color):
    x = 0
    y = 0
    output = np.zeros((height + 1, width + 1), dtype=np.uint32)
    with io.BytesIO(data) as stream:
        while stream.tell() < len(data):
            if x >= width:
                x = 0
                y += 2
                if y >= height:
                    break

            op = stream.read(1)[0]
            if (op & 0xC0) != 0xC0:
                count = op & 0x3F
            else:
                count = ((op & 0xF) << 8) + stream.read(1)[0]
                op <<= 2
            op &= 0xC0

            for _ in range(count):
                output[y : y + 2, x : x + 2] = decode_xmg_block(
                    stream,
                    op,
                    transparent_color,
                )
                x += 2
    return output[:height, :width]


def decode_xmg_block(stream, op, transparent_color):
    if op == 0x00:
        return process_ycrcb(stream)
    elif op == 0x40:
        return np.zeros((2, 2))
    elif op == 0x80:
        return process_rgb(stream, transparent_color)
    else:
        raise ValueError(f'Unsupported color mode {op}')


def process_ycrcb(stream):
    y = np.array(list(stream.read(4))).reshape((2, 2))
    cr, cb = stream.read(2)

    return yuv_to_rgb(y, cb, cr)


YUV_TO_RGB_MATRIX = np.array([
    [1024, 0, 1357],
    [1024, -333, -691],
    [1024, 1715, 0],
])


def yuv_to_rgb(y, u, v):
    # # TODO: this gives slightly different results due to rounding after shifting on each component
    # r, g, b = np.array([
    #     y + (1357 * (v - 128) >> 10),
    #     y - (691 * (v - 128) >> 10) - (333 * (u - 128) >> 10),
    #     y + (1715 * (u - 128) >> 10)
    # ]).clip(0, 255)
    # return 255 << 24 | b << 16 | g << 8 | r

    r, g, b = (
        np.array(
            [
                1024 * y + 1357 * (v - 128),
                1024 * y - 691 * (v - 128) - 333 * (u - 128),
                1024 * y + 1715 * (u - 128),
            ]
        )
        >> 10
    ).clip(0, 255)
    return 255 << 24 | b << 16 | g << 8 | r

    # uf = np.full_like(y, u - 128)
    # vf = np.full_like(y, v - 128)

    # yuv = np.stack([y, uf, vf], axis=-1)

    # x = yuv @ YUV_TO_RGB_MATRIX.T
    # x = np.clip(x >> 10, 0, 255)

    # r1, g1, b1 = x[:, :, 0], x[:, :, 1], x[:, :, 2]
    # b = 255 << 24 | b1 << 16 | g1 << 8 | r1

    # return b


def process_rgb(stream, transparent_color):
    colors = np.array(
        [int.from_bytes(stream.read(3), 'little') for _ in range(4)]
    ).reshape((2, 2))
    return np.where(colors != transparent_color, colors + (255 << 24), 0)
