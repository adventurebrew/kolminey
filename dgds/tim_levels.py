import pathlib
import struct
import functools
import itertools
import csv
import textwrap

import archive

UINT16LE = struct.Struct('<H')
UINT32LE = struct.Struct('<I')

def readcstr(f):
    toeof = iter(functools.partial(f.read, 1), b'')
    return b''.join(itertools.takewhile(b'\0'.__ne__, toeof))


def write_lev(entry, title, desc, encoding='windows-1255'):
    with entry.open('rb') as f:
        header = f.read(4)

        _title = readcstr(f)
        _objective = readcstr(f)

        rest = f.read()

        return header + title.encode(encoding) + b'\x00' + desc.encode(encoding) + b'\x00' + rest


def read_lev(entry, titled=True):
    with entry.open('rb') as f:
        _magic = UINT16LE.unpack(f.read(UINT16LE.size))[0]
        _version = UINT16LE.unpack(f.read(UINT16LE.size))[0]

        title = '-'
        objective = '-'
        if titled:
            title = readcstr(f).decode()
            objective = readcstr(f).decode()

        _bonus1 = UINT16LE.unpack(f.read(UINT16LE.size))[0]
        _bonus2 = UINT16LE.unpack(f.read(UINT16LE.size))[0]

        
        _air_pressure = UINT16LE.unpack(f.read(UINT16LE.size))[0]
        _gravity = UINT16LE.unpack(f.read(UINT16LE.size))[0]

        # print(_magic, _version, title, objective, _bonus1, _bonus2, _air_pressure, _gravity)
        return str(entry), title, objective


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('fname', help='Path to the game resource map')
    args = parser.parse_args()

    fname = pathlib.Path(args.fname)
    texts = pathlib.Path('tim-he - tem.csv')

    output_path = pathlib.Path('out')
    with archive.open(fname) as arc:
        levels = itertools.chain(arc.glob('*.LEV'), arc.glob('*.GKC'))
        with open(output_path / 'levels.csv', 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            descs = sorted(read_lev(lev, titled=lev.suffix == '.LEV') for lev in levels)
            csv_writer.writerow(['Filename', 'Title', 'Objective'])
            csv_writer.writerows(descs)

        builder = ''
        with texts.open('r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # next(reader)
            for name, _, title, _, desc in reader:
                entry = next(arc.glob(name))
                print(' '.join(x[::-1] for x in textwrap.wrap(desc, width=42)))
                builder += f'>{title[::-1]}'
                pathlib.Path(name).write_bytes(write_lev(entry, title[::-1], ' '.join(x[::-1] for x in textwrap.wrap(desc, width=42))))

        # # Inject level names in the exe of the CD version which have the embedded levels
        # start_offset = 215216
        # end_offset = 220253
        # ln = end_offset - start_offset
        # with open(pathlib.Path(fname).parent / 'TIM.exe', 'rb') as f:
        #     tim_exe = f.read(start_offset)
        #     skipped = f.read(ln)
        #     assert skipped[-100:] == b'\x00' * 100, skipped[-100:]
        #     tim_exe += builder.encode('windows-1255')
        #     tim_exe += bytes(ln - len(builder))
        #     tim_exe += f.read()
        #     pathlib.Path('TIM.exe').write_bytes(tim_exe)
