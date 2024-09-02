from contextlib import contextmanager
import io
import pathlib
from dataclasses import dataclass
import struct
import sys
from typing import IO, TextIO, cast
import xarc


@dataclass
class ResObject:
    rtype: str
    subtype: int
    index: int
    name: bytes
    data: bytes
    children: list['ResObject']


rtypes = {
        0: 'Invalid',
		1: 'Root',
		2: 'Level',
		3: 'Location',
		4: 'Layer',
		5: 'Camera',
		6: 'Floor',
		7: 'FloorFace',
		8: 'Item',
		9: 'Script',
		10: 'AnimHierarchy',
		11: 'Anim',
		12: 'Direction',
		13: 'Image',
		14: 'AnimScript',
		15: 'AnimScriptItem',
		16: 'SoundItem',
		17: 'Path',
		18: 'FloorField',
		19: 'Bookmark',
		20: 'KnowledgeSet',
		21: 'Knowledge',
		22: 'Command',
		23: 'PATTable',
		26: 'Container',
		27: 'Dialog',
		29: 'Speech',
		30: 'Light',
		31: 'Cursor',
		32: 'BonesMesh',
		33: 'Scroll',
		34: 'FMV',
		35: 'LipSync',
		36: 'AnimSoundTrigger',
		37: 'String',
		38: 'TextureSet',
}

def read_string(stream: IO[bytes]) -> bytes:
    length = int.from_bytes(stream.read(2), 'little')
    data = stream.read(length)
    return data


def import_resource(stream: IO[bytes]):
    rtype, subtype = stream.read(2)
    index = int.from_bytes(stream.read(2), 'little')
    name = read_string(stream)

    data_length = int.from_bytes(stream.read(4), 'little')
    data = stream.read(data_length)

    num_children = int.from_bytes(stream.read(2), 'little')
    unknown3 = int.from_bytes(stream.read(2), 'little')
    assert unknown3 == 0, unknown3

    children = [import_resource(stream) for _ in range(num_children)]
    return ResObject(rtypes[rtype], subtype, index, name, data, children)


def build_archive_name(level):
    name = level.name.decode('utf-8')
    if level.rtype == 'Level' and level.subtype == 1:
        return f'{name}/{name}.xarc'
    else:
        assert (level.rtype == 'Location' and level.subtype == 1) or level.subtype == 2
        return f'{level.index:02x}/{level.index:02x}.xarc'


def quote(s: str) -> str:
    s = str(s).replace('"', '""')
    return f'"{s}"'


def print_resource(basedir, arc, path: pathlib.Path, res: ResObject, indent: int = 0):
    # print('  ' * indent, path, res.rtype, res.subtype, res.index, res.name, len(res.children), res.data)

    for c in res.children:
        print_resource(basedir, arc, path, c, indent=indent + 1)

    if res.rtype == 'Image' and res.subtype == 4:
        with io.BytesIO(res.data) as s:
            # ALL IMAGES
            imagefile = read_string(s)
            hotspot = struct.unpack('<2I', s.read(8))
            transparent = bool(int.from_bytes(s.read(4), 'little'))
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

        print(
            quote(str(path)),
            quote(res.name.decode('windows-1251')),
            quote(''),
            quote(imagefile.decode('windows-1251')),
            quote(text.decode('windows-1251')),
            sep=',',
        )

    if res.rtype == 'Speech':
        with io.BytesIO(res.data) as f:
            text = read_string(f)
            char = int.from_bytes(f.read(4), 'little', signed=True)
            assert not f.read()

        sound, *lipsyncs = res.children
        assert sound.rtype == 'SoundItem'
        assert len(lipsyncs) <= 1
        assert all(lip.rtype == 'LipSync' for lip in lipsyncs), lipsyncs
        with io.BytesIO(sound.data) as s:
            soundfile = read_string(s)
            enabled = int.from_bytes(s.read(4), 'little')
            looping = bool(int.from_bytes(s.read(4), 'little'))
            field_64 = int.from_bytes(s.read(4), 'little')
            loop_indefinitely = bool(int.from_bytes(s.read(4), 'little'))
            max_duration = int.from_bytes(s.read(4), 'little')
            load_from_file = bool(int.from_bytes(s.read(4), 'little'))
            stock_sound_type = int.from_bytes(s.read(4), 'little')
            sound_name = read_string(s)
            field_6C = int.from_bytes(s.read(4), 'little')
            sound_type = int.from_bytes(s.read(4), 'little')
            pan = struct.unpack('<f', s.read(4))[0]
            volume = struct.unpack('<f', s.read(4))[0]

        # if soundfile:
        #     if load_from_file:
        #         soundpath = basedir / path.parent / 'xarc' / soundfile.decode('ascii')
        #         sound_data = soundpath.read_bytes()
        #     else:
        #         with arc.open(soundfile.decode('ascii'), 'rb') as s:
        #             sound_data = s.read()

        print(
            quote(str(path)),
            quote(res.name.decode('windows-1251')),
            char,
            quote(soundfile.decode('windows-1251')),
            quote(text.decode('windows-1251')),
            sep=',',
        )


def load_archive(basedir: pathlib.Path, fname: pathlib.Path, locs=(), indent: int = 0):
    # print('ARCHIVE', fname)
    with xarc.open(basedir / fname) as arc:
        with arc.open(fname.with_suffix('.xrc').name, 'rb') as f:
            res = import_resource(cast(IO[bytes], f))
            for c in res.children:
                if c.rtype == 'Level':
                    archive_name = build_archive_name(c)
                    load_archive(basedir, fname.parent / archive_name, indent=indent + 1)
                elif c.rtype == 'Location':
                    archive_name = build_archive_name(c)
                    assert res.rtype == 'Level'
                    load_archive(basedir, fname.parent / archive_name, indent=indent + 1)

            for loc in locs:
                load_archive(basedir, fname.parent / loc / f'{loc}.xarc', indent=indent + 1)
            print_resource(basedir, arc, fname, res, indent=indent)


@contextmanager
def redirect_stdout(file: TextIO):
    old_stdout = sys.stdout
    sys.stdout = file
    yield
    sys.stdout = old_stdout


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('basedir', type=str, help='File to extract from')
    args = parser.parse_args()

    with open('speech.csv', 'w', encoding='utf-8') as outfile, redirect_stdout(outfile):
        print('Archive,Name,Character,SoundFile,Text')
        load_archive(pathlib.Path(args.basedir), pathlib.Path('x.xarc'))
        load_archive(
            pathlib.Path(args.basedir),
            pathlib.Path('Static/Static.xarc'),
            locs=(
                'DiaryFMV',
                'DiaryIndexLocation',
                'DiaryLog',
                'DiaryPages',
                'LoadSaveLocation',
                'MainMenuLocation',
                'OptionLocation',
            )
        )
