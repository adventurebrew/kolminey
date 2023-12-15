import pathlib

from PIL import Image

import disk
from screen import convert_palette, image_from_buffer, load_flirt, pack_flirt


SEQUENTIAL = True


if __name__ == '__main__':
    blank_buffer = bytearray([255] * 320 * 200)
    graphics_dir = pathlib.Path('graphics')
    graphics_dir.mkdir(exist_ok=True)

    disk_path = 'sky.dsk'

    with disk.open(disk_path) as dsk:
        palette = dsk.get_file('60080').read_bytes()
        palette = convert_palette(palette)
        buffer = dsk.get_file('60081').read_bytes()[:320*200]
        im = image_from_buffer(buffer, palette)
        bg = im
        im.save(graphics_dir / 'title-bg.png')
        for flrt_file in ('60082', '60083', '60084', '60085', '60086'):
            if not SEQUENTIAL:
                im = image_from_buffer(blank_buffer, palette)
            print(flrt_file)

            first_screen = im.tobytes()
            screens = [first_screen]
            flrt = dsk.get_file(flrt_file).read_bytes()
            # for idx, screen in enumerate(load_flirt(flrt, blank_buffer)):
            for idx, (seq, screen) in enumerate(load_flirt(flrt, bytearray(im.tobytes()))):
                im = Image.open(str(graphics_dir / f'{flrt_file}.bin-{idx:03d}.png'))
                if im.mode != 'P':
                    if im.mode == 'RGBA':
                        im = im.convert('RGB')
                    im = im.quantize(palette=bg)
                screens.append(im.tobytes())

            im = image_from_buffer(first_screen, palette)
            test_data = pack_flirt(screens)
            dsk.patch_file(flrt_file, test_data)
            pathlib.Path(f'{flrt_file}.bin').write_bytes(test_data)
            for idx, (seqa, screen) in enumerate(load_flirt(test_data, bytearray(im.tobytes()))):
                print(f'{flrt_file} - frame {idx}')
                im = image_from_buffer(screen, palette)
                im.save(graphics_dir / f'{flrt_file}.bin-{idx:03d}-again.png')

        dsk.save_as('sky.dsk')
