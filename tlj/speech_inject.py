from contextlib import contextmanager
import csv
import io
import pathlib
import struct
import sys
from typing import IO, Iterator, TextIO, cast
import xarc

from speech import ResObject, import_resource, build_archive_name, read_string, rtypes
from xarc_inject import patch_archive


def write_string(s: bytes) -> bytes:
    return len(s).to_bytes(2, 'little') + s

reverse_rtypes = {v: k for k, v in rtypes.items()}

def patch_resource(res: ResObject):
    out = bytearray()
    out += reverse_rtypes[res.rtype].to_bytes(1, 'little')
    out += res.subtype.to_bytes(1, 'little')
    out += res.index.to_bytes(2, 'little')
    out += write_string(res.name)
    out += len(res.data).to_bytes(4, 'little')
    out += res.data
    out += len(res.children).to_bytes(2, 'little')
    out += b'\0\0'
    for c in res.children:
        out += patch_resource(c)

    return bytes(out)


def traverse_resource(basedir, arc, path: pathlib.Path, res: ResObject, lines: Iterator[dict[str, str]]):
    # print('  ' * indent, res.rtype, res.subtype, res.index, res.name)

    for c in res.children:
        traverse_resource(basedir, arc, path, c, lines)

    if res.rtype == 'Image' and res.subtype == 4:
        line = next(lines)
        assert str(path) == line['Archive'], (str(path), line['Archive'])
        assert res.name.decode('windows-1251') == line['Name'], (res.name, line['Name'])

        orig = res.data
        with io.BytesIO(res.data) as s:
            imagefile = read_string(s)
            hotspot = struct.unpack('<2I', s.read(8))
            transparent = int.from_bytes(s.read(4), 'little')
            transparent_color = int.from_bytes(s.read(4), 'little')

            polygon_count = int.from_bytes(s.read(4), 'little')
            polygons = []
            for _ in range(polygon_count):
                point_count = int.from_bytes(s.read(4), 'little')
                polygons.append([struct.unpack('<2I', s.read(8)) for _ in range(point_count)])

            # IMAGE TEXT ONLY
            size = struct.unpack('<2I', s.read(8))
            text = read_string(s)
            color = struct.unpack('<4B', s.read(4))  # last byte is ignored
            font = int.from_bytes(s.read(4), 'little')

        text = line['Text'].replace('\r\r\n', '\r\n').encode('windows-1251')
        translation = line.get('Translation')
        if translation:
            text = translation.replace('\r\r\n', '\r\n').encode('windows-1255')
        res.data = (
            write_string(imagefile)
            + hotspot[0].to_bytes(4, 'little')
            + hotspot[1].to_bytes(4, 'little')
            + transparent.to_bytes(4, 'little')
            + transparent_color.to_bytes(4, 'little')
            + len(polygons).to_bytes(4, 'little')
            + b''.join(
                len(polygon).to_bytes(4, 'little') + b''.join(x.to_bytes(4, 'little') for point in polygon for x in point)
                for polygon in polygons
            )
            + size[0].to_bytes(4, 'little')
            + size[1].to_bytes(4, 'little')
            + write_string(text)
            + b''.join(x.to_bytes(1, 'little') for x in color)
            + font.to_bytes(4, 'little')
        )
        print(res.rtype, res.subtype, res.index, res.name, line)


    if res.rtype == 'Speech':
        line = next(lines)
        assert str(path) == line['Archive'], (str(path), line['Archive'])
        assert res.name.decode('windows-1251') == line['Name'], (res.name, line['Name'])

        text = line['Text'].replace('\r\r\n', '\r\n').encode('windows-1251')
        translation = line.get('Translation')
        if translation:
            text = translation.replace('\r\r\n', '\r\n').encode('windows-1255')
        res.data = write_string(text) + int(line['Character']).to_bytes(4, 'little')
        print(res.rtype, res.subtype, res.index, res.name, line)


def load_archive(basedir: pathlib.Path, fname: pathlib.Path, lines: Iterator[dict[str, str]], locs=()):
    with xarc.open(basedir / fname) as arc:
        # with arc.open(fname.with_suffix('.xrc').name, 'rb') as f:
        #     orig = f.read()
        with arc.open(fname.with_suffix('.xrc').name, 'rb') as f:
            res = import_resource(cast(IO[bytes], f))
            for c in res.children:
                if c.rtype == 'Level':
                    archive_name = build_archive_name(c)
                    load_archive(basedir, fname.parent / archive_name, lines)
                elif c.rtype == 'Location':
                    archive_name = build_archive_name(c)
                    assert res.rtype == 'Level'
                    load_archive(basedir, fname.parent / archive_name, lines)

            for loc in locs:
                load_archive(basedir, fname.parent / loc / f'{loc}.xarc', lines)
            traverse_resource(basedir, arc, fname, res, lines)
            patched = patch_resource(res)

            # assert orig == patched, (orig, patched)

            ('patch' / fname.parent).mkdir(parents=True, exist_ok=True)
            ('patch' / fname).write_bytes(patch_archive(basedir, fname, {fname.with_suffix('.xrc').name: patched}))


@contextmanager
def redirect_stdout(file: TextIO):
    old_stdout = sys.stdout
    sys.stdout = file
    yield
    sys.stdout = old_stdout


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('basedir', type=str, help='Path to game directory')
    parser.add_argument('csvpath', type=str, help='File to read texts from')
    args = parser.parse_args()

    with open(args.csvpath, 'r', newline='', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        load_archive(pathlib.Path(args.basedir), pathlib.Path('x.xarc'), csv_reader)
        load_archive(
            pathlib.Path(args.basedir),
            pathlib.Path('Static/Static.xarc'),
            csv_reader,
            locs=(
                'DiaryFMV',
                'DiaryIndexLocation',
                'DiaryLog',
                'DiaryPages',
                'LoadSaveLocation',
                'MainMenuLocation',
                'OptionLocation',
            ),
        )

        assert not next(csv_reader, None)
