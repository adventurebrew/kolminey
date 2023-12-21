import disk


import numpy as np

from grid import create_char_grid


fonts = [
    {'name': 'main', 'file': 60150, 'spacing': 0, 'height': 12},
    {'name': 'menu', 'file': 60520, 'spacing': 0, 'height': 12},
    {'name': 'terminal', 'file': 60521, 'spacing': 1, 'height': 12},
]


def generate_game_characters(char_set_ptr, dt_char_spacing, char_height):
    num_chars = 128  # The first 128 bytes are the widths of the characters

    # Read char_sprite_ptr for each character in advance
    char_widths = char_set_ptr[:num_chars]
    char_data_ptr = char_set_ptr[num_chars:]

    # Create an array of char_sprite_ptr in advance
    char_sprite_ptrs = [char_data_ptr[i * char_height * 4 : (i + 1) * char_height * 4] for i in range(num_chars)]

    for char_width, char_sprite_ptr in zip(char_widths, char_sprite_ptrs, strict=True):
        char_width += 1 - dt_char_spacing

        # Create a 2D numpy array for the character
        char_array = np.zeros((char_height, char_width), dtype=np.uint8)

        for i in range(char_height):
            data = int.from_bytes(char_sprite_ptr[i*4:i*4+2], byteorder='big')
            mask = int.from_bytes(char_sprite_ptr[i*4+2:i*4+4], byteorder='big')

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

        yield char_array


palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]


if __name__ == '__main__':
    disk_path = 'game/sky.dsk'

    with disk.open(disk_path) as dsk:
        for font in fonts:
            font_data = dsk.get_file(str(font['file'])).read_bytes()

            im = create_char_grid(128 + 0x20, enumerate(generate_game_characters(font_data, font['spacing'], font['height']), start=0x20))
            im.putpalette(palette)
            im.save(f'{font["name"]}.png')

            # for i, char in enumerate(generate_game_characters(font_data, font['spacing'], font['height']), start=0x20):
            #     print(bytes([i]).decode('cp862', errors='ignore'), char.shape)
