import io
import struct
from pathlib import Path
from typing import TYPE_CHECKING

from pakal.archive import SimpleArchive, make_opener

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex, SimpleEntry


def read_string(file, length):
    text = file.read(length)
    # print(text)
    return text

def read_long(file):
    return struct.unpack('<I', file.read(4))[0]

def extract(file, base_offset, path):
    entries = read_long(file)
    for _ in range(entries):
        name_size = read_long(file)
        name = read_string(file, name_size).decode('ascii')
        assert name.rstrip('\0') == name, name
        entry_type = read_long(file)
        if entry_type == 1:
            yield from extract(file, base_offset, path / name)
        else:
            assert entry_type == 2, entry_type
            size = read_long(file)
            zero = read_long(file)  # ZSIZE?
            assert zero == 0
            offset = read_long(file) + base_offset
            full_name = path / name
            yield full_name, (offset, size)


def build_path_dict(paths):
    def insert_path(d, parts, full_path):
        if len(parts) == 1:
            d[parts[0]] = full_path
        else:
            if parts[0] not in d:
                d[parts[0]] = {}
            insert_path(d[parts[0]], parts[1:], full_path)

    path_dict = {}
    for path in paths:
        parts = Path(path).parts
        insert_path(path_dict, parts, path)
    
    return path_dict


def encode_path_dict(path_index, new_index, ofile):
    ofile.write(struct.pack('<I', len(path_index)))
    for key, val in path_index.items():
        ofile.write(struct.pack('<I', len(key)))
        ofile.write(key.encode('ascii'))
        if isinstance(val, dict):
            ofile.write(struct.pack('<I', 1))
            encode_path_dict(val, new_index, ofile)
        else:
            off, size = new_index[val]
            ofile.write(struct.pack('<I', 2))
            ofile.write(struct.pack('<I', size))
            ofile.write(b"\0\0\0\0")
            ofile.write(struct.pack('<I', off - 32))


class CryoBF(SimpleArchive):
    def _create_index(self) -> 'ArchiveIndex[SimpleEntry]':
        if read_string(self._stream, 9) != b"CryoBF - ":
            raise ValueError("Invalid file format")

        self.ver = read_string(self._stream, 7)
        zero1 = read_long(self._stream)
        zero2 = read_long(self._stream)
        assert zero1 == zero2 == 0
        info_offset = read_long(self._stream)
        base_offset = read_long(self._stream)
        
        assert self._stream.tell() == base_offset == 32, (self._stream.tell(), base_offset)

        self._stream.seek(info_offset)
        index = dict(extract(self._stream, base_offset, path=Path()))
        
        assert not self._stream.read(), "Not all data was read"
        return index


def main(filename):
    filename = Path(filename)

    output_dir = Path("extracted")
    patch_dir = Path("patch")

    with CryoBF(filename) as archive:
        archive.extractall(output_dir)

        # rebuild

        with io.open(f'{filename.stem}_new.bf', 'wb') as ofile:
            ofile.write(b"CryoBF - ")
            ofile.write(archive.ver)
            ofile.write(b"\0\0\0\0\0\0\0\0")
            ofile.write(struct.pack('<I', 0))
            ofile.write(struct.pack('<I', 32))
            assert ofile.tell() == 32, (ofile.tell(), 32)

            new_index = {}
            base_offset = 32
            for entry in archive:
                # print(fname)
                if not (patch_dir / str(entry)).exists():
                    content = entry.read_bytes()
                else:
                    print('patching', str(entry))
                    content = (patch_dir / str(entry)).read_bytes()
                ofile.write(content)
                new_index[str(entry)] = (base_offset, len(content))
                base_offset += len(content)

            it = build_path_dict(new_index.keys())

            encode_path_dict(it, new_index, ofile)

            ofile.seek(24)
            ofile.write(struct.pack('<I', base_offset))


open = make_opener(CryoBF)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()
    main(args.filename)
