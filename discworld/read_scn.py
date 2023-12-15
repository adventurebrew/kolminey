import os
import io
import sys
import struct

import numpy as np
from PIL import Image

UINT32LE = struct.Struct('<I')
UINT16LE_x2 = struct.Struct('<2H')


def parse_unk(chunk_type, data):
    print(hex(chunk_type))

def parse_header(chunk_type, data):
    assert not data
    return

def parse_graphics(chunk_type, data):
    blocks = len(data) // 16
    with io.BytesIO(data) as f:
        for b in range(blocks):
            width, height = UINT16LE_x2.unpack(f.read(UINT16LE_x2.size))
            width, height = width & 0x7FFF, height & 0x7FFF
            nbits, = UINT32LE.unpack(f.read(UINT32LE.size))
            offset, = UINT32LE.unpack(f.read(UINT32LE.size))
            offset_pal, = UINT32LE.unpack(f.read(UINT32LE.size))
            # print(width, height)
    
            # print(offset)

            with open(fname, 'rb') as stream:
                stream.seek(offset + 4 & 0x7FFFFF)

                arr = np.frombuffer(stream.read(width * height), dtype=np.uint8).reshape(height, width)
                print(arr)
                Image.fromarray(arr).save(f'pic_{b:06d}.png')


PARSERS = {
    0x0002: parse_header,
    0x0006: parse_graphics
}

if __name__ == '__main__':
    fname = sys.argv[1]
    with open(fname, 'rb') as stream:
        while True:
            
            chunk_type, magic = UINT16LE_x2.unpack(stream.read(UINT16LE_x2.size))
            assert magic == 0x3334, hex(magic)
            next_offset, = UINT32LE.unpack(stream.read(UINT32LE.size))
            size = next_offset - stream.tell() if next_offset else -1
            data = stream.read(size)

            PARSERS.get(chunk_type, parse_unk)(chunk_type, data)

            # print(stream.tell())

            if next_offset == 0:
                break
