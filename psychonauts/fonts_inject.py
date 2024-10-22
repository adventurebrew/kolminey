
from pathlib import Path
from PIL import Image
import yaml


if __name__ == '__main__':
    path = Path(r"C:\GOG Games\Psychonauts\WorkResource\Fonts")
    for fntfile in path.glob('*.dff'):
        overrd_info = f'{fntfile.stem}_heb.txt'
        overrd_img = f'{fntfile.stem}_heb.png'
        if not (Path(overrd_info).exists() and Path(overrd_img).exists()):
            print(f"Missing {overrd_info} or {overrd_img} - {Path(overrd_info).exists()} {Path(overrd_img).exists()}")
            continue
        output = bytearray()
        with open(overrd_info, 'r') as f:
            info = yaml.safe_load(f)
            print(info)
        output.extend(b'FFFD')
        if len(info['charmap']) != 256:
            print(f"charmap length is not 256: {len(info['charmap'])}")
            continue
        output.extend((len(info['charmap'])).to_bytes(4, 'little'))
        output.extend((len(info['crops'])).to_bytes(4, 'little'))
        output.extend(bytes(info['charmap'].values()))
        for crop in info['crops'].values():
            x1, y1, x2, y2, base, dmy = crop.split()
            output.extend(int(x1).to_bytes(2, 'little'))
            output.extend(int(y1).to_bytes(2, 'little'))
            output.extend(int(x2).to_bytes(2, 'little'))
            output.extend(int(y2).to_bytes(2, 'little'))
            output.extend(int(base).to_bytes(2, 'little'))
            output.extend(int(dmy).to_bytes(2, 'little'))
        output.extend((3).to_bytes(4, 'little'))
        im = Image.open(overrd_img)
        output.extend(im.width.to_bytes(4, 'little'))
        output.extend(im.height.to_bytes(4, 'little'))
        output.extend(im.tobytes())
        with open(fntfile.with_suffix('.dff').name, 'wb') as f:
            f.write(bytes(output))
        print(f"Done {fntfile}")
