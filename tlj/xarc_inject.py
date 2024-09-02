import pathlib
from typing import IO, Iterator
from xarc import read_uint32_le, readcstr


def read_index_entries2(stream: IO[bytes]) -> Iterator[tuple[str, tuple[int, int], int]]:
    _unknown = read_uint32_le(stream)
    assert _unknown == 1, _unknown
    file_count = read_uint32_le(stream)
    base_offset = read_uint32_le(stream)
    offset = base_offset
    for _i in range(file_count):
        file_name = readcstr(stream).decode('ascii')
        file_size = read_uint32_le(stream)
        _unknown2 = read_uint32_le(stream)
        assert _unknown2 in {1, 2, 3, 4}, _unknown2
        yield file_name, (offset, file_size), _unknown2
        offset += file_size


def patch_archive(basedir: pathlib.Path, fname: pathlib.Path, patches: dict[str, bytes]):
    with open(basedir / fname, 'rb') as f:
        content = bytearray()
        idx_data = bytearray(b'\1\0\0\0')
        index = list(read_index_entries2(f))
        base_offset = index[0][1][0]
        assert base_offset == f.tell(), (base_offset, f.tell())

        idx_data += len(index).to_bytes(4, 'little')
        idx_data += base_offset.to_bytes(4, 'little')

        offset = base_offset
        for name, (off, size), unk in index:
            print(name)
            idx_data += name.encode('ascii') + b'\0'
            if name in patches:
                currfile = patches[name]
            else:
                f.seek(off)
                currfile = f.read(size)
            content += currfile
            offset += len(currfile)
            idx_data += len(currfile).to_bytes(4, 'little')
            idx_data += unk.to_bytes(4, 'little')

    return bytes(idx_data + content)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('basedir', type=str, help='File to extract from')
    args = parser.parse_args()

    patch_archive(pathlib.Path(args.basedir), pathlib.Path('x.xarc'), {'x.xrc': b'x.xrc content'})
