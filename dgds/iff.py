
from dataclasses import dataclass, field
import functools
import io
import itertools
import struct

from lzw import LZWDecoder

UINT32LE = struct.Struct('<I')

@dataclass
class Chunk:
    tag: bytes
    content: bytes = field(repr=False)
    container: bool


def readcstr(f):
    toeof = iter(functools.partial(f.read, 1), b'')
    return b''.join(itertools.takewhile(b'\0'.__ne__, toeof))

def read_chunk(data):
    with io.BytesIO(data) as stream:
        tag = stream.read(4)
        sizeo = UINT32LE.unpack(stream.read(UINT32LE.size))[0]
        size = sizeo & 0x7FFFFFFF
        container = sizeo & 0x80000000
        content = stream.read(size)
        rest = stream.read()
        return Chunk(tag, content, container), rest


def read_chunks(data):
    while data:
        chunk, data = read_chunk(data)
        yield chunk


def decompress_chunk(data):
    with io.BytesIO(data) as stream:
        comp = ord(stream.read(1))
        uncompressed_size = UINT32LE.unpack(stream.read(UINT32LE.size))[0]
        # print(comp, uncompressed_size)
        if comp == 2:
            lzwd = LZWDecoder()
            return lzwd.decompress(stream.read(), uncompressed_size)
        raise ValueError(comp)


def write_chunk(tag, content, container=False):
    with io.BytesIO() as stream:
        stream.write(tag)
        size = len(content) | (0x80000000 if container else 0)
        stream.write(UINT32LE.pack(size))
        stream.write(content)
        return stream.getvalue()
