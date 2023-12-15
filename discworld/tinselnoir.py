import io
import sys
from enum import IntFlag
import pathlib


class MemHandleFlag(IntFlag):
    Preload = 0x01
    Discard = 0x02
    Sound = 0x04
    Graphic = 0x08
    Compressed = 0x10
    Loaded = 0x20

from read_scn import UINT32LE
from lzss import decompress

loaded = {}

def load_mem(name, size):
    data = name.read_bytes()
    print(len(data))
    return decompress(data, size)


if __name__ == '__main__':
    fname = pathlib.Path(sys.argv[1])
    with open(fname, 'rb') as stream:
        stream.seek(0, io.SEEK_END)
        stream_size = stream.tell()
        stream.seek(0, io.SEEK_SET)

        print(stream_size)
        for i in range(stream_size // 24):
            name = stream.read(12).rstrip(b'\0').decode()
            size = UINT32LE.unpack(stream.read(UINT32LE.size))[0]
            unk1 = int.from_bytes(stream.read(4), byteorder='little', signed=False)
            flags = MemHandleFlag(ord(stream.read(1)))
            unk2 = int.from_bytes(stream.read(3), byteorder='little', signed=False)

            print(i, name, size, unk1, flags, unk2, flags & MemHandleFlag.Preload)
            if flags & MemHandleFlag.Preload:
                loaded[name] = load_mem(fname.parent / name, size)
                # print(loaded[name])
