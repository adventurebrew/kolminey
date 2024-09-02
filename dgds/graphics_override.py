import pathlib
import archive
from graphics import read_bmp
from PIL import Image

from iff import read_chunk, read_chunks


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('fname', help='Path to the game resource map')
    args = parser.parse_args()

    fname = pathlib.Path(args.fname)
    override_path = pathlib.Path('tim_override')
    with archive.open(fname) as f:

        palettes = {}
        for palfile in f.glob('*.PAL'):
            chunk, rest = read_chunk(palfile.read_bytes())
            assert not rest, rest
            assert chunk.tag == b'PAL:' and chunk.container, (chunk.tag, chunk.container)

            vga, *egas = read_chunks(chunk.content)
            palette = [x << 2 for x in vga.content]
            assert palette[0:3] == [0, 0, 0], palette[0:3]
            palette[0:3] = [150, 0, 150]
            palettes[palfile.stem] = palette

        for entry in f.glob('*.BMP'):
            print(entry)
            frames: list[Image.Image] = []
            sizes = []
            override = False
            assert entry.read_bytes().startswith(b'BMP:')
            for idx, im in enumerate(read_bmp(entry.read_bytes())):
                override_file = override_path / f'{entry.stem}_{idx}.png'
                if override_file.is_file():
                    override = True
                    frames.append(Image.open(override_file))
                else:
                    frames.append(im)
                if override:
                    offs: list[int] = []
                    out = bytearray()
                    for frame in frames:
                        sizes.append(im.size)

            #         frames.append(save_scn(np.asarray(Image.open(override_file)).tobytes(), *im.size))
            #         sizes.append(im.size)
            #         override = True
            #     elif override:
            #         frames.append(save_scn(np.asarray(im), *im.size))
            #         sizes.append(im.size)
            # if override:
            #     offs = []
            #     off = 0
            #     for frame in frames:
            #         offs.append(off)
            #         off += len(frame)
            #     scn = b''.join(frames)
            #     offs_chunk = write_chunk(b'OFF:', b''.join(UINT32LE.pack(o) for o in offs), False)
            #     scn_chunk = write_chunk(b'SCN:', scn, False)
            #     ws, hs = zip(*sizes)
            #     widths = b''.join(UINT16LE.pack(w) for w in ws)
            #     heights = b''.join(UINT16LE.pack(h) for h in hs)
            #     info_chunk = write_chunk(b'INF:', UINT16LE.pack(len(sizes)) + widths + heights, False)
            #     assert entry.read_bytes()[8:8+len(info_chunk)] == info_chunk, (entry.read_bytes()[8:8+len(info_chunk)], info_chunk)

            #     with open(entry.stem + '.BMP', 'wb') as f:
            #         f.write(write_chunk(b'BMP:', info_chunk + scn_chunk + offs_chunk, True))


            #     for idx, im in enumerate(read_bmp(pathlib.Path(entry.stem + '.BMP').read_bytes())):
            #         im.putpalette(palettes['TIM'])
            #         im.save(f'{entry.stem}_{idx}.png')
