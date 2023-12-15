import os
import io
import sys
import struct
import pathlib

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
            unk = f.read(4)
            offset, = UINT32LE.unpack(f.read(UINT32LE.size))
            offset_pal, = UINT32LE.unpack(f.read(UINT32LE.size))
            # print(width, height)
    
            # print(offset)

            with open(fname, 'rb') as stream:
                stream.seek(offset & 0x7FFFFF)

                arr = np.frombuffer(stream.read(width * height), dtype=np.uint8).reshape(height, width)
                print(arr)
                Image.fromarray(arr).save(f'pic_{b:06d}.png')


PARSERS = {
    0x0002: parse_header,
    0x0006: parse_graphics
}

def read_chunks(stream):
    while True:
        chunk_type, magic = UINT16LE_x2.unpack(stream.read(UINT16LE_x2.size))
        assert magic == 0x3334, hex(magic)
        next_offset, = UINT32LE.unpack(stream.read(UINT32LE.size))
        size = next_offset - stream.tell() if next_offset else -1
        data = stream.read(size)
        yield chunk_type, data
        if next_offset == 0:
            break

PARSERS = {
    0x0002: parse_header,
    0x0006: parse_graphics
}

NOT_USED = {3, 4, 5, 6, 7, 8, 9, 11, 12, 13}

if __name__ == '__main__':
    index_fname = sys.argv[1]
    with open(index_fname, 'rb') as stream:
        stream.seek(0, 2)
        length = stream.tell()
        stream.seek(0, 0)

        handles = []
        while True:
            # f.read(_handleTable[i].szName, 12);
            # _handleTable[i].filesize = f.readUint32();
            # // The pointer should always be NULL. We don't
            # // need to read that from the file.
            # _handleTable[i]._node= nullptr;
            # f.seek(4, SEEK_CUR);
            # // For Discworld 2, read in the flags2 field
            # _handleTable[i].flags2 = t2Flag ? f.readUint32() : 0;
            fname = stream.read(12).split(b'\0')[0].decode()
            if not fname:
                break
            filesize, = UINT32LE.unpack(stream.read(UINT32LE.size))
            offset, = UINT32LE.unpack(stream.read(UINT32LE.size))
            assert offset == 0
            if False:  # DW2
                flags, = UINT32LE.unpack(stream.read(UINT32LE.size))
            handles.append((fname, filesize, offset))

        opens = {}
        for fname, filesize, offset in handles:
            print(fname)
            actual_size = filesize & 0x00FFFFFF
            opens[fname] = (pathlib.Path(index_fname).parent / fname).read_bytes()
            assert len(opens[fname]) == actual_size, (len(opens[fname]), actual_size)
            chunks = list(read_chunks(io.BytesIO(opens[fname])))
            for chunk_type, chunk_data in chunks:
                if chunk_type == 2:  # CHUNK_BITMAP
                    assert not chunk_data, chunk_data
                elif chunk_type in NOT_USED:
                    pass
                elif chunk_type == 10:  # CHUNK_PCODE
                    pass
                elif chunk_type == 14: # CHUNK_SCENE
                    print(chunk_data)
                elif chunk_type == 15: # CHUNK_TOTAL_ACTORS
                    numta, = UINT32LE.unpack(chunk_data)
                elif chunk_type == 16: # CHUNK_TOTAL_GLOBALS
                    numtg, = UINT32LE.unpack(chunk_data)
                elif chunk_type == 17: # CHUNK_TOTAL_OBJECTS
                    numto, = UINT32LE.unpack(chunk_data)
                elif chunk_type == 18: # CHUNK_OBJECTS
                    pass
                elif chunk_type == 21: # CHUNK_TOTAL_POLY
                    numtp, = UINT32LE.unpack(chunk_data)
                else:
                    raise ValueError(chunk_type)
            # break
