import io
import pathlib
import archive
from iff import read_chunk

def read_uint16le(f):
    return int.from_bytes(f.read(2), 'little')

def read_uint32le(f):
    return int.from_bytes(f.read(4), 'little')

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('fname', help='Path to the game resource map')
    args = parser.parse_args()

    fname = pathlib.Path(args.fname)

    output_path = pathlib.Path('out')
    with archive.open(fname) as f:
        for entry in f.glob('*.FNT'):
            chunk, rest = read_chunk(entry.read_bytes())
            assert not rest, rest
            assert chunk.tag == b'FNT:' and not chunk.container, (chunk.tag, chunk.container)

            with io.BytesIO(chunk.content) as f:
                version = f.read(1)[0]
                bpp = 1 if version == 0xFF else 8
                max_width = f.read(1)[0]
                max_height = f.read(1)[0]
                base_line = f.read(1)[0]
                start_symbol = f.read(1)[0]
                nr_of_symbols = f.read(1)[0]
                symbol_data_size = read_uint16le(f)
                compression_method = f.read(1)[0]
                uncompressed_size = read_uint32le(f)
                print(entry, version, max_width, max_height, base_line, start_symbol, nr_of_symbols, symbol_data_size, compression_method, uncompressed_size)
