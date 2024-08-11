from io import BytesIO
import pathlib
import struct
from PIL import Image


def lzss_decompress(source, size):
    dest_cursor = 0
    destination = bytearray(2 * size)
    window_cursor = 4078
    window = bytearray(b'\x20' * 4078 + b'\0' * (4096 - 4078))

    with BytesIO(source) as stream:
        while dest_cursor < size:
            flagbyte = stream.read(1)[0]
            mask = 1

            for i in range(8):
                if flagbyte & mask == mask:
                    data = stream.read(1)
                    if not data:
                        return bytes(destination)
                    data = data[0]
                    window[window_cursor] = data
                    destination[dest_cursor] = data
                    dest_cursor += 1
                    window_cursor = (window_cursor + 1) & 0xFFF
                else:
                    low = stream.read(1)
                    if not low:
                        return bytes(destination)
                    low = low[0]
                    high = stream.read(1)
                    if not high:
                        return bytes(destination)
                    high = high[0]
                    length = (high & 0xF) + 2
                    offset = low | ((high & 0xF0) << 4)
                    offset &= 0xFFFF

                    for j in range(length + 1):
                        temp = window[(offset + j) & 0xFFF]
                        window[window_cursor] = temp
                        destination[dest_cursor] = temp
                        dest_cursor += 1
                        window_cursor = (window_cursor + 1) & 0xFFF

                mask = mask << 1

    return bytes(destination)


def rgb555_to_rgba(data):
    rgba_data = bytearray()
    for i in range(0, len(data), 2):
        # Read 2 bytes (16 bits)
        pixel = struct.unpack('<H', data[i:i+2])[0]
        
        # Extract RGB components
        r = (pixel >> 10) & 0x1F
        g = (pixel >> 5) & 0x1F
        b = pixel & 0x1F
        
        # Convert to 8-bit per channel
        r = (r << 3) | (r >> 2)
        g = (g << 3) | (g >> 2)
        b = (b << 3) | (b >> 2)
        
        # Append RGBA values
        rgba_data.extend([r, g, b, 255])
    
    return bytes(rgba_data)


def rgb565_to_rgba(data):
    rgba_data = bytearray()
    for i in range(0, len(data), 2):
        # Read 2 bytes (16 bits)
        pixel = struct.unpack('<H', data[i:i+2])[0]
        
        # Extract RGB components
        r = (pixel >> 11) & 0x1F
        g = (pixel >> 5) & 0x3F
        b = pixel & 0x1F
        
        # Convert to 8-bit per channel
        r = (r << 3) | (r >> 2)
        g = (g << 2) | (g >> 4)
        b = (b << 3) | (b >> 2)
        
        # Append RGBA values
        rgba_data.extend([r, g, b, 255])
    
    return bytes(rgba_data)


def rgba_to_rgb555(data):
    rgb555_data = bytearray()
    for i in range(0, len(data), 4):
        r = data[i] >> 3
        g = data[i + 1] >> 3
        b = data[i + 2] >> 3
        rgb555_pixel = (r << 10) | (g << 5) | b
        rgb555_data.extend(struct.pack('<H', rgb555_pixel))
    return bytes(rgb555_data)


def save_tga_rgb555(img, output):
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    rgb555_data = rgba_to_rgb555(img.tobytes())
    width, height = img.size
    with open(output, 'wb') as out_f:
        # Write TGA header
        out_f.write(b'\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        out_f.write(struct.pack('<HH', width, height))
        out_f.write(b'\x10\x00')  # 16 bits per pixel
        # Write RGB 555 data
        out_f.write(rgb555_data)


if __name__ == '__main__':
    input_path = pathlib.Path('eng_pix')
    output_dir = pathlib.Path("graphics")
    output_dir.mkdir(exist_ok=True)

    for im in input_path.glob("*.tga"):
        print(im)
        with im.open("rb") as f:
            magic = f.read(4)
            if magic == b'TGZ\0':
                decomp_size = int.from_bytes(f.read(4), 'little')
                width = int.from_bytes(f.read(4), 'little')
                height = int.from_bytes(f.read(4), 'little')
                res = bytes(lzss_decompress(f.read(), decomp_size))
                with Image.frombytes("RGBA", (width, height), rgb555_to_rgba(res)) as img:
                    save_tga_rgb555(img, output_dir / f'{im.stem}.tga')
                    img.save(output_dir / f'{im.stem}.png')
            else:
                with Image.open(im) as img:
                    save_tga_rgb555(img, output_dir / f'{im.stem}.tga')
                    img.save(output_dir / f'{im.stem}.png')
