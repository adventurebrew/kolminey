import argparse
import io
import pathlib
import struct

import numpy as np

from grid import create_char_grid


UINT16LE_X5 = struct.Struct('<5H')


def untag(stream):
    tag = stream.read(4)
    size = int.from_bytes(stream.read(4), 'big')
    data = stream.read(size)
    return tag, data


def read_chunks(stream):
    while True:
        htag, data = untag(stream)
        if htag == b'END ':
            break
        yield htag, data
    rest = stream.read()
    if rest:
        raise ValueError(f'Unexpected data after END: {rest}')


def read_chars(data: bytes):
    last_idx = 0
    with io.BytesIO(data) as bmp:
        while True:
            bheader = bmp.read(UINT16LE_X5.size)
            if not bheader:
                break
            idx, xoff, yoff, w, h = UINT16LE_X5.unpack(bheader)
            yield (
                xoff,
                yoff,
                np.frombuffer(bmp.read(w * h), dtype=np.uint8).reshape((h, w)),
            )
            assert idx in {0, 1} or idx == last_idx + 1, idx
            assert idx > 0 or (w, h, xoff, yoff) == (1, 1, 0, 0), (
                idx,
                w,
                h,
                xoff,
                yoff,
            )
            last_idx = idx


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process font files.')
    parser.add_argument(
        'pattern',
        metavar='<PATH>',
        help='Path to a file, directory, or glob pattern of font files to process.',
    )
    args = parser.parse_args()

    path = pathlib.Path(args.pattern)
    if path.is_dir():
        filenames = path.glob('*.FNT')
    else:
        filenames = path.parent.glob(path.name)

    for file in filenames:
        print(file)

        with file.open('rb') as f:
            chunks = list(read_chunks(f))
            htag, header = chunks[0]
            assert htag == b'FNHD'
            assert len(header) == 56, len(header)
            # TODO: Figure out the header format
            print(header[:32], header[32:])
            print('Chunks:', [tag for tag, _ in chunks])
            palette = None

            for htag, data in chunks[1:]:
                if htag == b'FPAL':  # Used in ARIALVS.FNT
                    assert palette is None, palette
                    assert len(data) == 768, len(data)
                    palette = [x << 2 for x in data]
                if htag == b'BPAL':
                    assert palette is None, palette
                    assert len(data) == 768, len(data)
                    palette = [x << 2 for x in data]
                if htag == b'FBMP':
                    glyphs = list(read_chars(data))

                    chars = range(32, 32 + len(glyphs))

                    im = create_char_grid(chars.stop, zip(chars, glyphs))
                    im.putpalette(palette)
                    im.save(str(f'{file.name}.png'))
