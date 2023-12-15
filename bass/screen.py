import pathlib

from PIL import Image

import disk


GAME_COLORS = 240

top_16_colors = [
    0, 0, 0,
    38, 38, 38,
    63, 63, 63,
    0, 0, 0,
    0, 0, 0,
    0, 0, 0,
    0, 0, 0,
    54, 54, 54,
    45, 47, 49,
    32, 31, 41,
    29, 23, 37,
    23, 18, 30,
    49, 11, 11,
    39, 5, 5,
    29, 1, 1,
    63, 63, 63,
]


def convert_palette(palette):
    palette = bytearray(palette[:240 * 3] + bytes(top_16_colors))
    for i in range(256):
        palette[i * 3 + 0] = (palette[i * 3 + 0] << 2) + (palette[i * 3 + 0] >> 4)
        palette[i * 3 + 1] = (palette[i * 3 + 1] << 2) + (palette[i * 3 + 1] >> 4)
        palette[i * 3 + 2] = (palette[i * 3 + 2] << 2) + (palette[i * 3 + 2] >> 4)
    return bytes(palette)


def image_from_buffer(buffer, palette):
    im = Image.frombuffer('P', (320, 200), buffer, 'raw', 'P', 0, 1)
    im.putpalette(palette)
    return im


def load_flirt(data, buffer):
    frames_left, *seq_data = data
    screen = bytearray(buffer)
    pos = 0
    start = 0

    for _ in range(frames_left):
        screen_pos = 0
        while screen_pos < 320 * 192:

            nr_to_skip = seq_data[pos]
            pos += 1
            screen_pos += nr_to_skip
            if nr_to_skip == 0xFF:
                continue

            while True:
                nr_to_do = seq_data[pos]
                pos += 1

                screen[screen_pos:screen_pos+nr_to_do] = seq_data[pos:pos+nr_to_do]
                pos += nr_to_do
                screen_pos += nr_to_do

                if nr_to_do != 0xFF:
                    break

        yield seq_data[start:pos], bytes(screen)
        start = pos


def pack_flirt(screens):
    frames_left = len(screens) - 1
    seq_data = []
    buffer = screens[0]

    for screen in screens[1:]:
        screen_pos = 0
        while screen_pos < 320*192:
            # Find the longest sequence of same bytes
            nr_to_skip = 0
            while screen[screen_pos] == buffer[screen_pos] and screen_pos < 320*192:
                nr_to_skip += 1
                screen_pos += 1

            while nr_to_skip >= 255:
                seq_data.append(0xFF)
                nr_to_skip -= 255

            seq_data.append(nr_to_skip)

            nr_to_do = 0
            change_buffer = []
            while screen[screen_pos] != buffer[screen_pos] and screen_pos < 320*192:
                change_buffer.append(screen[screen_pos])
                screen_pos += 1
                nr_to_do += 1

            assert nr_to_do == len(change_buffer), (nr_to_do, len(change_buffer))
            while nr_to_do > 255:
                print('warning: nr_to_do > 255')
                seq_data.append(0xFF)
                seq_data.extend(change_buffer[:255])
                change_buffer = change_buffer[255:]
                nr_to_do -= 255

            seq_data.append(nr_to_do)
            seq_data.extend(change_buffer)

        buffer = screen

    return bytes([frames_left] + seq_data)


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
        im.save(graphics_dir / 'title-bg.png')
        tidx = 0
        for flrt_file in ('60082', '60083', '60084', '60085', '60086'):
            if not SEQUENTIAL:
                im = image_from_buffer(blank_buffer, palette)

            print(flrt_file)

            first_screen = im.tobytes()
            screens = [first_screen]
            seqs = []
            flrt = dsk.get_file(flrt_file).read_bytes()
            # for idx, screen in enumerate(load_flirt(flrt, blank_buffer)):
            for idx, (seq, screen) in enumerate(load_flirt(flrt, bytearray(im.tobytes()))):
                im = image_from_buffer(screen, palette)
                screens.append(im.tobytes())
                im.save(graphics_dir / f'{flrt_file}.bin-{idx:03d}.png')
                im.save(graphics_dir / f'title-{tidx:03d}.png')
                tidx += 1
                seqs.append(seq)

            im = image_from_buffer(first_screen, palette)
            test_data = pack_flirt(screens)
            for idx, (seqa, screen) in enumerate(load_flirt(test_data, bytearray(im.tobytes()))):
                print(f'{flrt_file} - frame {idx}')
                im = image_from_buffer(screen, palette)
                # im.save(graphics_dir / f'{flrt_file}-{idx:03d}-again.png')
                assert im.tobytes() == screens[idx + 1]
                assert seqa == seqs[idx], (seqa, seqs[idx])
