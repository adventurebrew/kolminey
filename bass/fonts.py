import disk


import numpy as np

from grid import create_char_grid, read_image_grid, resize_frame


fonts = [
    {'name': 'main', 'file': 60150, 'spacing': 0, 'height': 12},
    {'name': 'menu', 'file': 60520, 'spacing': 0, 'height': 12},
    {'name': 'terminal', 'file': 60521, 'spacing': 1, 'height': 12},
]


def char_data_to_array(char_data, char_width, char_height):
    # Create a 2D numpy array for the character
    char_array = np.zeros((char_height, char_width), dtype=np.uint8)

    for i in range(char_height):
        data = int.from_bytes(char_data[i*4:i*4+2], byteorder='big')
        mask = int.from_bytes(char_data[i*4+2:i*4+4], byteorder='big')

        for j in range(char_width):
            mask_bit = (mask & 0x8000) != 0
            mask <<= 1
            data_bit = (data & 0x8000) != 0
            data <<= 1

            if mask_bit:
                if data_bit:
                    char_array[i, j] = 128
                else:
                    char_array[i, j] = 172  # black edge

        # data_bin = f'{data:016b}'[:char_width]
        # mask_bin = f'{mask:016b}'[:char_width]
        # print('AAA', data_bin, mask_bin)
        # for j in range(char_width):
        #     if j >= len(mask_bin):
        #         break
        #     if mask_bin[j] == '1':
        #         if data_bin[j] == '1':
        #             char_array[i, j] = 128
        #         else:
        #             char_array[i, j] = 172  # black edge
        #     else:
        #         assert data_bin[j] == '0', data_bin[j]

    return char_array


def char_array_to_data(char_array):
    char_height, char_width = char_array.shape

    char_data = bytearray(char_height * 4)
    for i in range(char_height):
        data = ''
        mask = ''

        for j in range(char_width):
            if char_array[i, j] == 128:
                data += '1'
                mask += '1'
            elif char_array[i, j] == 172:
                data += '0'
                mask += '1'
            else:
                mask += '0'
                data += '0'

        datab = int(data.ljust(16, '0'), 2)
        maskb = int(mask.ljust(16, '0'), 2)

        char_data[i*4:i*4+2] = datab.to_bytes(2, byteorder='big')
        char_data[i*4+2:i*4+4] = maskb.to_bytes(2, byteorder='big')

    return char_data


def generate_game_characters(char_set_ptr, dt_char_spacing, char_height, verify=True):
    num_chars = 128  # The first 128 bytes are the widths of the characters

    # Read char_sprite_ptr for each character in advance
    char_widths = char_set_ptr[:num_chars]
    char_data_ptr = char_set_ptr[num_chars:]

    # Create an array of char_sprite_ptr in advance
    char_sprite_ptrs = [char_data_ptr[i * char_height * 4 : (i + 1) * char_height * 4] for i in range(num_chars)]

    for char_width, char_sprite_ptr in zip(char_widths, char_sprite_ptrs, strict=True):
        char_width += 1 - dt_char_spacing

        decoded = char_data_to_array(char_sprite_ptr, char_width, char_height)
        if verify:
            reencoded = char_array_to_data(decoded)
            redecoded = char_data_to_array(reencoded, char_width, char_height)
            assert np.array_equal(decoded, redecoded), (decoded, redecoded)
        yield decoded


palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]


def write_char_data(chars, dt_char_spacing, char_height):
    num_chars = 128

    chars = list(chars)
    assert len(chars) == num_chars, len(chars)
    char_widths = bytearray()
    chars_data = [bytearray(char_height * 4) for _ in range(num_chars)]
    for char, char_data in zip(chars, chars_data, strict=True):
        if char is None:
            char_widths.append(dt_char_spacing - 1)
            char_data[:] = b'\0' * len(char_data)
            continue
        _, char = char
        char_widths.append(char.shape[1] + dt_char_spacing - 1)
        char_data[:] = char_array_to_data(char)
        assert len(char_data) == char_height * 4, len(char_data)

    assert len(char_widths) == num_chars, len(char_widths)
    return bytes(char_widths + b''.join(chars_data))


def read_chars(filename):
    chars = [resize_frame(char) for char in read_image_grid(filename)]
    first, after, remaining = chars[:0x20], chars[0x20:0xA0], chars[0xA0:]
    assert all(char is None for char in first)
    assert all(char is None for char in remaining)
    assert len(after) == 128, len(after)

    yield from after


if __name__ == '__main__':
    disk_path = 'game/sky.dsk'

    with disk.open(disk_path) as dsk:
        for font in fonts:
            font_data = dsk.get_file(str(font['file'])).read_bytes()

            im = create_char_grid(128 + 0x20, enumerate(generate_game_characters(font_data, font['spacing'], font['height']), start=0x20))
            im.putpalette(palette)
            im.save(f'{font["name"]}_orig.png')

        for font in fonts:
            font_data = write_char_data(read_chars(f'{font["name"]}.png'), font['spacing'], font['height'])
            im = create_char_grid(128 + 0x20, enumerate(generate_game_characters(font_data, font['spacing'], font['height']), start=0x20))
            im.putpalette(palette)
            im.save(f'{font["name"]}_test.png')
            dsk.patch_file(str(font['file']), font_data)

        dsk.save_as('sky.dsk')
            # for i, char in enumerate(generate_game_characters(font_data, font['spacing'], font['height']), start=0x20):
            #     print(bytes([i]).decode('cp862', errors='ignore'), char.shape)
