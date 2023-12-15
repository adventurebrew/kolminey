import os
import struct

import numpy as np


UINT32LE = struct.Struct('<I')

# 0000h	4	Glyphs #
# 0004h	Glyphs #	Width of each glyph.
# 0004h + Glyphs #	1	Glyphs height.
# 0005h + Glyphs #	(Sum of widths) * glyphs # * height	Uncompressed raw data.

from grid import create_char_grid

palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]

if __name__ == '__main__':
    import sys
    import glob

    if not len(sys.argv) > 1:
        print('Usage: gob_font.py FILENAME')
        exit(1)
    filenames = sys.argv[1]

    filenames = list(glob.iglob(sys.argv[1]))
    print(filenames)

    for fname in filenames:
        basename = os.path.basename(fname)
        print(f'DECODING {basename}')

        with open(fname, 'rb') as f:        
            # Alternatively (as implemented in ScummVM), num_glyphs is one byte and height is 4 bytes in Big Endian
            num_glyphs = UINT32LE.unpack(f.read(UINT32LE.size))[0]
            height = f.read(1)[0]

            glyphs_widths = list(f.read(num_glyphs))

            print(glyphs_widths, height)
            glyphs = [np.frombuffer(f.read(width * height), dtype=np.uint8).reshape(height, width) for width in glyphs_widths]

            print(glyphs[0])

            rest = f.read()
            assert rest == b'', rest

        chars = range(len(glyphs))

        im = create_char_grid(chars.stop, zip(chars, glyphs))
        im.putpalette(palette)
        im.save(os.path.join('out', f'{basename}.png'))
