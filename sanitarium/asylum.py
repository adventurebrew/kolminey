import itertools
import operator
import os
from mrcrowbar import models as mrc
# from mrcrowbar import utils
from mrcrowbar.lib.images import base as img

# class FileEntry(mrc.Block):
#     offset: mrc.UInt32_BE(0x00)

class ResourcePack(mrc.Block):
    entryCount = mrc.UInt32_LE( 0x00 )
    entries = mrc.UInt32_LE( 0x04, count=mrc.Ref( "entryCount" ) )
    raw_bytes = mrc.Bytes( mrc.EndOffset( "entries" ) )

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self.resources = mrc.LinearStore(
            parent=self,
            source=mrc.Ref( "raw_bytes" ),
            block_klass=mrc.Unknown,
            offsets=mrc.Ref( "entries" ),
            base_offset=mrc.EndOffset( "entries", neg=True ),
        )

class GraphicsResource( mrc.Block ):
    magic = mrc.Const( mrc.Bytes( 0x00, length=4 ), b'D3GR' )
    flags = mrc.UInt32_LE( 0x04 )
    contentOffset = mrc.Int32_LE( 0x08 )
    field_C = mrc.Int32_LE( 0x0C )
    field_10 = mrc.Int32_LE( 0x10 )
    field_14 = mrc.Int32_LE( 0x14 )
    frameCount = mrc.Int16_LE( 0x18 )
    maxWidth = mrc.Int16_LE( 0x1A )

    offsets = mrc.UInt32_LE( 0x1C, count=mrc.Ref( "frameCount" ) )
    raw_bytes = mrc.Bytes( mrc.EndOffset( "offsets" ) )

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self.frames = mrc.LinearStore(
            parent=self,
            source=mrc.Ref( "raw_bytes" ),
            block_klass=Frame,
            offsets=mrc.Ref( "offsets" ),
            base_offset=0x00,
        )


class Frame(mrc.Block):
    unk1 = mrc.UInt16_LE(0x00)
    unk2 = mrc.UInt16_LE(0x02)
    unk3 = mrc.UInt16_LE(0x04)
    unk4 = mrc.UInt16_LE(0x06)
    x = mrc.Int16_LE(0x08)
    y = mrc.Int16_LE(0x0A)
    height = mrc.UInt16_LE(0x0C)
    width = mrc.UInt16_LE(0x0E)

    raw_data = mrc.Bytes(0x10)

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self.image = img.IndexedImage(
            self,
            width=mrc.Ref( "width" ),
            height=mrc.Ref( "height" ),
            source=mrc.Ref( "raw_data" ),
            # palette=[((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)],
        )

import numpy as np

def crop_bounds(image):
    mask = image == 4 | image == 6

    # Coordinates of non-black pixels.
    coords = np.argwhere(mask)

    # Bounding box of non-black pixels.
    x0, y0 = coords.min(axis=0)
    x1, y1 = coords.max(axis=0) + 1   # slices are exclusive at the top

    # Get the contents of the bounding box.
    return x0, y0, x1, y1

def crop_bounds_pil(image, bg_colors):
    bgs = set(bg_colors)
    bgpos = [(x,y) for x in range(image.size[0]) for y in range(image.size[1]) if image.getdata()[x+y*image.size[0]] not in bgs]
    if not bgpos:
        return None
    rect = (min([x for x, _ in bgpos]), min([y for _, y in bgpos]), max([x for x, _ in bgpos]) + 1, max([y for _, y in bgpos]) + 1)
    return rect

if __name__ == "__main__":
    from PIL import Image
    import pathlib
    import csv

    data_path = pathlib.Path(r"C:\GOG Games\Sanitarium\Data")

    with open('texts.csv', 'w', encoding='utf-8') as output_file:
    #     reses = pathlib.Path(r"C:\GOG Games\Sanitarium\Data").glob('RES.*')
    #     for path in sorted(reses, key=str):
        path = pathlib.Path(data_path / 'RES.000')
        rp = ResourcePack(path.read_bytes())
        for idx, x in enumerate(rp.resources.items):
            if x.data[:4] not in {
                b'RIFF',
                b'D3GR',
                b'\x01\x00\x00\x00'
            } and x.data.endswith(b'\0'):
                assert b'[END]' not in x.data
                try:
                    text = x.data.rstrip(b'\0').decode('latin-1').replace('"', '""').replace('\x01', '[END]')
                except UnicodeDecodeError:
                    print(x.data)
                    raise
                print(path.name, idx, f'"{text}"', sep='\t', file=output_file)

    with open('texts_heb.csv', 'r', encoding='utf-8') as f:
        tsv_file = csv.reader(f, delimiter='\t')
        for idx, x in enumerate(rp.resources.items):
            if x.data[:4] not in {
                b'RIFF',
                b'D3GR',
                b'\x01\x00\x00\x00'
            } and x.data.endswith(b'\0'):
                line = next(tsv_file)[-1]
                try:
                    rep = line.encode('windows-1255', errors='ignore') + b'\0'
                except UnicodeEncodeError:
                    print(line)
                    raise
                x.data = rep
        rp.resources.save()
        pathlib.Path('RES.000').write_bytes(rp.export_data())


    import numpy as np
    from PIL import Image


    im = Image.open('image1.png')
    palette = bytes(np.asarray(im).ravel())

    # fonts2 = []

    # for res in sorted(glob.iglob(r"C:\GOG Games\Sanitarium\Data\RES.0*")):
    #     data = pathlib.Path(res).read_bytes()
    #     rp = ResourcePack(data)

    #     for fidx, font_resource in enumerate(rp.resources.items):
    #         if font_resource.data[:4] != b'D3GR':
    #             continue
    #         try:
    #             gr = GraphicsResource(font_resource.data)
    #         except Exception:
    #             continue

    #         if gr.frameCount < 100:
    #             continue

    #         if max(frame.height for frame in gr.frames.items) > 200:
    #             continue

    #         print(res, fidx)
    #         fonts2.append((int(res[-3:]), fidx))


    # print(fonts2)

    fonts = [
        (1, 16),
        (1, 22),
        (1, 25),
        (1, 32),
        (1, 57),
        (5, 13),
        (5, 14),
        (5, 15),
        (6, 13),
        (6, 14),
        (6, 15),
        (7, 13),
        (7, 14),
        (7, 15),
        (8, 13),
        (8, 14),
        (8, 15),
        (9, 13),
        (9, 14),
        (9, 15),
        (9, 174),
        (10, 13),
        (10, 14),
        (10, 15),
        (11, 13),
        (11, 14),
        (11, 15),
        (11, 310),  # fails assert on BG color, clone of 18, 18
        (12, 13),
        (12, 14),
        (12, 15),
        (12, 415),
        (12, 416),
        (12, 417),
        (13, 13),
        (13, 14),
        (13, 15),
        (14, 13),
        (14, 14),
        (14, 15),
        (15, 13),
        (15, 14),
        (15, 15),
        (16, 13),
        (16, 14),
        (16, 15),
        (17, 13),
        (17, 14),
        (17, 15),
        (18, 18),
        (18, 19),
        (18, 20),
        (18, 21),
    ]

    colorset = set()

    for res, item in fonts:
        print('FONT', res, item)
        data = pathlib.Path(data_path / 'RES.{res:03d}'.format(res=res)).read_bytes()
        rp = ResourcePack(data)

        font_resource = rp.resources.items[item]
        gr = GraphicsResource(font_resource.data)

        print(gr)
        max_h = 32

        amax_h = max(frame.height for frame in gr.frames.items)
        max_h = max(amax_h + 2, max_h)

        max_w = gr.maxWidth
        rows = (gr.frameCount + 15) // 16
        bim = Image.new('P', (min(16, gr.frameCount)  * max_w, rows * max_h))

        # colorset = {1, 97, 100, 102, 134, 137, 233, 79, 112, 144, 82, 241, 117, 88, 91, 124, 253, 254}
        BG = [117, 253]

        for fidx, frame in enumerate(gr.frames.items):
            print(fidx, frame)
            assert frame.width * frame.height == len(frame.raw_data), (frame.width * frame.height, len(frame.raw_data))
            xim = Image.new('P', (max_w, max_h), color=BG[(fidx // 16 + fidx % 16) % 2])
            im = frame.image.get_image()
            colorset |= set(np.asarray(im).tobytes())
            shared = set(BG) & set(np.asarray(im).tobytes())
            # assert not shared, shared
            assert im.size == (frame.width, frame.height), (im.size, (frame.width, frame.height))
            # im.save(target / f'anim_{idx}_frame_{fidx}.png')
            assert frame.width <= max_w and frame.height <= max_h, (frame.width, max_w, frame.height, max_h)
            bim.paste(xim, (max_w * (fidx % 16), max_h * (fidx // 16)))
            bim.paste(im, (frame.x + 2 + max_w * (fidx % 16), frame.y + 2 + max_h * (fidx // 16)))

        # bim.putpalette([((59 + x) ** 2 * 83 // 67) % 256 for x in range(256 * 3)])
        bim.putpalette(palette)
        bim.save(f'font_{res:03d}_{item}.png')

    # RE-EXPORT

    # TODO: import font image to gr

    fonts = itertools.groupby(sorted(fonts, key=operator.itemgetter(0)), key=operator.itemgetter(0))

    for res, group in fonts:

        data = pathlib.Path(r"C:\GOG Games\Sanitarium\Data\RES.{res:03d}".format(res=res)).read_bytes()
        rp = ResourcePack(data)
        save = False

        for ires, item in group:
            assert ires == ires, (res, ires)
            print('IMPORTING FONT', res, item)
            target = f'font_heb_{res:03d}_{item}.png'
            if not os.path.exists(target):
                continue

            save = True
            font_resource = rp.resources.items[item]
            gr = GraphicsResource(font_resource.data)

            max_h = 32
            max_w = gr.maxWidth
            print(gr)

            eim = Image.open(target)

            for fidx, frame in enumerate(gr.frames.items):
                orig = frame.export_data()
                left = max_w * (fidx % 16)
                top = max_h * (fidx // 16)
                cim = eim.crop((left, top, max_w + left, max_h + top))
                rect = crop_bounds_pil(cim, BG)
                if not rect:
                    frame.x = 0
                    frame.y = 0
                    frame.width, frame.height = 0, 0
                    frame.raw_data = b''
                else:
                    ccim = cim.crop(rect)
                    frame.x = rect[0] - 2
                    frame.y = rect[1] - 2
                    frame.width, frame.height = ccim.size
                    frame.raw_data = bytes(ccim.getdata())


                    # frame.width, frame.height = 16, 16
                    # frame.raw_data = bytes(range(0, 256))
                # utils.diffdump(frame.export_data(), orig)

            orig = gr.export_data()
            gr.frames.save()
            # utils.diffdump(gr.export_data(), orig)

            rp.resources.items[item].load(gr.export_data())
            rp.resources.save()
        if save:
            pathlib.Path(f'RES.{res:03d}').write_bytes(rp.export_data())
