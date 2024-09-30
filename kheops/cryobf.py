import struct
from pathlib import Path

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


def main(filename):
    filename = Path(filename)

    output_dir = Path("extracted")
    patch_dir = Path("patch")

    with filename.open('rb') as file:
        if read_string(file, 9) != b"CryoBF - ":
            raise ValueError("Invalid file format")

        ver = read_string(file, 7)
        zero1 = read_long(file)
        zero2 = read_long(file)
        assert zero1 == zero2 == 0
        info_offset = read_long(file)
        base_offset = read_long(file)
        
        assert file.tell() == base_offset, (file.tell(), base_offset)

        file.seek(info_offset)
        index = list(extract(file, base_offset, Path()))

        assert not file.read(), "Not all data was read"

        for fname, (off, size) in index:
            file.seek(off)
            (output_dir / fname).parent.mkdir(parents=True, exist_ok=True)
            (output_dir / fname).write_bytes(file.read(size))

        # rebuild

        with open(f'{filename.stem}_new.bf', 'wb') as ofile:
            ofile.write(b"CryoBF - ")
            ofile.write(ver)
            ofile.write(b"\0\0\0\0\0\0\0\0")
            ofile.write(struct.pack('<I', base_offset))
            ofile.write(struct.pack('<I', 32))
            assert ofile.tell() == 32, (ofile.tell(), 32)

            new_index = []
            base_offset = 32
            for fname, (off, size) in index:
                # print(fname)
                if not (patch_dir / fname).exists():
                    file.seek(off)
                    ofile.write(file.read(size))
                    new_index.append((fname, (base_offset, size)))
                    base_offset += size
                else:
                    print('patching', fname)
                    content = (patch_dir / fname).read_bytes()
                    ofile.write(content)
                    new_index.append((fname, (base_offset, len(content))))
                    base_offset += len(content)


            it = build_path_dict([fname for fname, _ in new_index])

            encode_path_dict(it, dict(new_index), ofile)

            ofile.seek(24)
            ofile.write(struct.pack('<I', base_offset))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()
    main(args.filename)

