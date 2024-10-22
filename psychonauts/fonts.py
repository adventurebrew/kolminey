
from pathlib import Path
from PIL import Image


if __name__ == '__main__':
    path = Path(r"C:\GOG Games\Psychonauts\WorkResource\Fonts")
    for fntfile in path.glob('*.dff'):
        print(fntfile.name)
        with open(fntfile, 'rb') as f:
            magic = f.read(4)
            assert magic == b'FFFD'
            tblsiz = int.from_bytes(f.read(4), 'little')
            assert tblsiz == 256, tblsiz
            nchars = int.from_bytes(f.read(4), 'little')
            chartbl = f.read(tblsiz)
            info = []
            print(f"tblsiz: {tblsiz}, nchars: {nchars}")

            for i in range(nchars):
                x1 = int.from_bytes(f.read(2), 'little')
                y1 = int.from_bytes(f.read(2), 'little')
                x2 = int.from_bytes(f.read(2), 'little')
                y2 = int.from_bytes(f.read(2), 'little')
                base = int.from_bytes(f.read(2), 'little')
                dmy = int.from_bytes(f.read(2), 'little')
                info.append((x1, y1, x2, y2, base, dmy))

            magic2 = int.from_bytes(f.read(4), 'little')
            assert magic2 == 3, magic2
            tex_w = int.from_bytes(f.read(4), 'little')
            tex_h = int.from_bytes(f.read(4), 'little')
            tex = f.read(tex_w*tex_h)
            rest = f.read()
            assert not rest, rest

            im = Image.new('L', (tex_w, tex_h))
            im.putdata(tex)
            im.save(fntfile.with_suffix('.png').name)

            ext = Path('ext') / fntfile.stem
            ext.mkdir(exist_ok=True, parents=True)
            for c in range(tblsiz):
                char = info[chartbl[c]]
                x1, y1, x2, y2 = char[:4]
                cim = im.crop((x1, y1, x2, y2))
                cim.save(ext / fntfile.with_name(fntfile.stem + f'_{c}.png').name)
