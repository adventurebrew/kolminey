from collections.abc import Iterator

import numpy as np
import archive

import io
import pathlib
import struct
import itertools
from PIL import Image

from iff import decompress_chunk, read_chunk, read_chunks
from vqt import load_vqt

UINT16LE = struct.Struct('<H')
UINT32LE = struct.Struct('<I')

VERIFY = True


def read_uint16le(stream):
    return UINT16LE.unpack(stream.read(UINT16LE.size))[0]


def read_inf(data):
    with io.BytesIO(data) as stream:
        num = read_uint16le(stream)
        widths = [read_uint16le(stream) for _ in range(num)]
        heights = [read_uint16le(stream) for _ in range(num)]
        rest = stream.read()
        assert not rest, rest
        return zip(widths, heights)



def load_scn(data, width, height):
    tw = width
    th = height
    total_size = tw * th
    dst = bytearray(total_size)

    dstpos = 0

    with io.BytesIO(data) as stream:
        addval = stream.read(1)[0]
        lastcmd = 0xFF
        while dstpos < total_size:
            val = stream.read(1)
            if not val:
                break
            val = val[0]
            cmd = (val & 0xC0) >> 6
            assert (val >> 6) == (val & 0xC0) >> 6
            val &= 0x3F
            if cmd == 0:
                # print('CMD 00 - move cursor down and back', val)
                if lastcmd == 0 and val:
                    dstpos -= (val << 6)
                else:
                    dstpos += tw - val
            elif cmd == 1:
                # print('CMD 01 - skip', val)
                if not val:
                    dstpos = tw * th
                else:
                    dstpos += val
            elif cmd == 2:
                # print('CMD 10 - repeat val', val)
                color = stream.read(1)[0]
                dst[dstpos:dstpos + val] = [(color + addval) & 0xFF] * val
                dstpos += val
            elif cmd == 3:
                # print('CMD 11 - direct read of `val` * 4-bit values', val)
                colors = [((color >> 4) + addval, (color & 0xf) + addval) for color in stream.read((val + 1) // 2)]
                dst[dstpos:dstpos + val] = list(itertools.chain.from_iterable(colors))[:val]
                dstpos += val
            else:
                raise ValueError(f"Invalid command {cmd}")
            lastcmd = cmd
    if set(dst) != {0}:
        assert min(x for x in dst if x > 0) >= addval, (addval, set(dst))
    else:
        assert addval == 255, addval
    return bytes(dst)


def save_scn(image_data, width, height):
    tw = width
    th = height
    total_size = tw * th
    stream = io.BytesIO()

    # Determine addval as the minimum value in the image data that is not zero
    if set(image_data) != {0}:
        addval = min(x for x in image_data if x > 0)
    else:
        addval = 255
    stream.write(bytes([addval]))

    dstpos = 0

    while dstpos < total_size:
        val = image_data[dstpos]
        if dstpos + 1 < total_size:
            next_val = image_data[dstpos + 1]
        else:
            next_val = None
        
        if val == next_val:
            # CMD 10 - repeat val
            count = 1
            while dstpos + count < total_size and image_data[dstpos + count] == val and count < 0x3F:
                count += 1
            stream.write(bytes([(2 << 6) | count]))
            stream.write(bytes([(val - addval) & 0xFF]))
            dstpos += count
        elif val == 0:
            # CMD 01 - skip
            count = 1
            while dstpos + count < total_size and image_data[dstpos + count] == 0 and count < 0x3F:
                count += 1
            stream.write(bytes([(1 << 6) | count]))
            dstpos += count
        else:
            # CMD 11 - direct read of `val` * 4-bit values
            count = 1
            while dstpos + count < total_size and image_data[dstpos + count] != 0 and count < 0x3F:
                count += 1
            stream.write(bytes([(3 << 6) | count]))
            colors = [(image_data[dstpos + i] - addval) & 0xFF for i in range(count)]
            packed_colors = [(colors[i] << 4) | (colors[i + 1] if i + 1 < count else 0) for i in range(0, count, 2)]
            stream.write(bytes(packed_colors))
            dstpos += count
    
    return stream.getvalue()


def handle_vga_bin(data, sizes, split_nibbles):
    data = decompress_chunk(data)
    data = bytes(nibble for byte in data for nibble in split_nibbles(byte))
    with io.BytesIO(data) as imstream:
        for (w, h) in sizes:
            assert w * h % 2 == 0, (w, h)
            yield Image.frombuffer('P', (w, h), imstream.read(w * h))
        _rest = imstream.read()
        # assert not _rest, _rest


def split_low_nibble(byte):
    return (byte & 0xF0) >> 4, byte & 0x0F


def split_high_nibble(byte):
    return byte & 0xF0, (byte & 0x0F) << 4


def handle_bin(data, sizes):
    return handle_vga_bin(data, sizes, split_low_nibble)


def handle_vga(data, sizes):
    return handle_vga_bin(data, sizes, split_high_nibble)


def handle_vqt(data, sizes, offs=()):
    offset = 0
    if not offs:
        print('VQT without OFFs', sizes)
        for size in sizes:
            offset, im = load_vqt(data, offset, *size)
            yield Image.frombuffer('P', size, im[:size[0] * size[1]])
            # Align to 8 bytes
            offset += (8 - offset) % 8
        return
    print('VQT with OFFs', sizes)
    for (start, end), size in zip(itertools.pairwise([*offs, len(data)]), sizes, strict=True):
        # assert offset == start, (offset, start)
        _, im = load_vqt(data[start:end], 0, *size)
        yield Image.frombuffer('P', size, im[:size[0] * size[1]])


def handle_scn(data, sizes, offs):
    assert offs
    for (start, end), size in zip(itertools.pairwise([*offs, len(data)]), sizes, strict=True):
        im = load_scn(data[start:end], *size)
        yield Image.frombuffer('P', size, im[:size[0] * size[1]])
        if VERIFY:
            encoded = save_scn(im, *size)
            decoded = load_scn(encoded, *size)
            assert load_scn(encoded, *size) == im, (im, decoded)


def handle_mtx(data):
    with io.BytesIO(data) as stream:
        matrix_x = read_uint16le(stream)
        matrix_y = read_uint16le(stream)
        print(matrix_x, matrix_y)
        tile_matrix = [read_uint16le(stream) for _ in range(matrix_x * matrix_y)]
        rest = stream.read()
        assert not rest, rest
        return matrix_x, matrix_y, tile_matrix


def read_bmp(data: bytes) -> Iterator[Image.Image]:
    chunk, rest = read_chunk(data)
    assert not rest, rest
    assert chunk.tag == b'BMP:' and chunk.container, (chunk.tag, chunk.container)

    inf, *rest = read_chunks(chunk.content)
    assert inf.tag == b'INF:', inf.tag
    sizes = list(read_inf(inf.content))
    print(sizes)

    print(rest)

    for chunk in rest:
        if chunk.tag == b'OFF:':
            num = len(chunk.content) // UINT32LE.size
            with io.BytesIO(chunk.content) as stream:
                offs = [UINT32LE.unpack(stream.read(UINT32LE.size))[0] for _ in range(num)]
            print(offs)
            if not offs:
                assert chunk.content == b'\xFF\xFF', chunk.content

    frames = {}
    matrix_x = matrix_y = 0
    tile_matrix = []

    types = tuple(chunk.tag for chunk in rest)
    assert types in {
        (b'SCN:', b'OFF:'),  # TIM, WILLY
        (b'BIN:',),  # TIM
        (b'BIN:', b'RLE:'),  # TIM
        (b'VQT:', b'OFF:'),  # ROTD, WILLY
        (b'BIN:', b'VGA:'),  # ROTD, WILLY
        (b'BIN:', b'VGA:', b'MTX:'),  # ROTD, WILLY
        (b'BIN:', b'VGA:', b'SCL:'),  # WILLY
        (b'VQT:', b'OFF:', b'SCL:'),  # WILLY
    }, types

    for chunk in rest:
        if chunk.tag == b'OFF:':
            pass # we have parsed this already
        elif chunk.tag == b'BIN:':
            for idx, im in enumerate(handle_bin(chunk.content, sizes)):
                frames[idx] = im
        elif chunk.tag == b'VGA:':
            for idx, im in enumerate(handle_vga(chunk.content, sizes)):
                if idx in frames:
                    im = np.array(frames[idx]) | np.array(im)
                    frames[idx] = Image.frombuffer('P', sizes[idx], im)
                else:
                    raise ValueError(f"VGA before BIN {idx}")
        elif chunk.tag == b'VQT:':
            for idx, im in enumerate(handle_vqt(chunk.content, sizes, offs)):
                frames[idx] = im
        elif chunk.tag == b'SCN:':
            for idx, im in enumerate(handle_scn(chunk.content, sizes, offs)):
                frames[idx] = im
        elif chunk.tag == b'MTX:':
            matrix_x, matrix_y, tile_matrix = handle_mtx(chunk.content)
        else:
            print('UNHANDLED', chunk.tag)
            # raise ValueError(f'Unhandled {chunk.tag}')

    if tile_matrix:
        # stack all frames, matrix_x accross and matrix_y down
        im = np.hstack(
            [
                np.vstack(
                    [
                        np.asarray(frames[tile_matrix[x * matrix_y + y]])
                        for y in range(matrix_y)
                    ]
                )
                for x in range(matrix_x)
            ]
        )
        yield Image.frombuffer('P', (im.shape[1], im.shape[0]), im)
        return
    # assert len(frames) == len(sizes), (len(frames), len(sizes))
    for frame in frames.values():
        yield frame


def read_scr(data: bytes) -> Image.Image:
    chunk, rest = read_chunk(data)
    assert not rest, rest
    assert chunk.tag == b'SCR:' and chunk.container, (chunk.tag, chunk.container)
    subchunks = list(read_chunks(chunk.content))
    print(subchunks)
    size = (320, 200)
    im: Image.Image | None = None
    for schunk in subchunks:
        output_path.mkdir(exist_ok=True, parents=True)
        if schunk.tag == b'VQT:':
            im, *rest = handle_vqt(schunk.content, [size])
            assert not rest, rest
        elif schunk.tag == b'BIN:':
            im, *rest = handle_bin(schunk.content, [size])
            assert not rest, rest
        elif schunk.tag == b'VGA:':
            assert im is not None
            bim, *rest = handle_vga(schunk.content, [size])
            assert not rest, rest
            im = np.array(im) | np.array(bim)
            im = Image.frombuffer('P', size, im)
        else:
            print('UNHANDLED', schunk.tag)
            # raise ValueError(f"Unhandled {schunk.tag}")
    assert im is not None
    return im


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('fname', help='Path to the game resource map')
    args = parser.parse_args()

    fname = pathlib.Path(args.fname)

    palettes = {}
    output_path = pathlib.Path('out')
    with archive.open(fname) as f:
        for palfile in f.glob('*.PAL'):
            chunk, rest = read_chunk(palfile.read_bytes())
            assert not rest, rest
            assert chunk.tag == b'PAL:' and chunk.container, (chunk.tag, chunk.container)

            vga, *egas = read_chunks(chunk.content)
            palette = [x << 2 for x in vga.content]
            assert palette[0:3] == [0, 0, 0], palette[0:3]
            palette[0:3] = [150, 0, 150]
            palettes[palfile.stem] = palette
        print(len(palettes))

        for entry in f.glob('*.BMP'):
            print(entry)
            for idx, im in enumerate(read_bmp(entry.read_bytes())):
                output_path.mkdir(exist_ok=True, parents=True)
                for palname, palette in palettes.items():
                    im.putpalette(palette)
                    im.save(output_path / f'{entry.stem}_{idx}_{palname}.png')
                    # break

        for entry in f.glob('*.SCR'):
            print(entry)
            im = read_scr(entry.read_bytes())
            assert im is not None
            output_path.mkdir(exist_ok=True, parents=True)
            for palname, palette in palettes.items():
                im.putpalette(palette)
                im.save(output_path / f'{entry.stem}_{palname}.png')
                # break
