from collections.abc import Iterable
import csv
from dataclasses import dataclass
import io
import itertools
import os
from pathlib import Path
import struct
import re

import textwrap
from typing import IO

from bidi import get_display  # type: ignore[import-untyped]
import requests

# https://www.lua.org/source/4.0/dump.c.html
# https://github.com/TrupSteam/psychonauts-translator/tree/main

@dataclass
class LuaHeader:
    signature: bytes
    version: int
    endianess: int
    sizeof_int: int
    sizeof_size_t: int
    sizeof_instruction: int
    SIZE_INSTRUCTION: int
    SIZE_OP: int
    SIZE_B: int
    sizeof_number: int

    @classmethod
    def parse(cls, stream: IO[bytes]) -> 'LuaHeader':
        header_struc = struct.Struct('<4s9B')
        header = cls(*header_struc.unpack(stream.read(header_struc.size)))
        if header.signature != b'\x1bLua':
            raise ValueError('Unexpected LUB Signature found: {0!r}'.format(header.signature))
        if header.version != 0x40:
            raise ValueError('Unexpected LUB Version found: {0!r}'.format(header.version))
        TEST_NUMBER = stream.read(header.sizeof_number)
        assert len(TEST_NUMBER) == header.sizeof_number, len(TEST_NUMBER)
        return header


def read_uint32(stream: IO[bytes]) -> int:
    return int.from_bytes(stream.read(4), 'little')


def read_lua_string(stream: IO[bytes]) -> str:
    size = read_uint32(stream)
    text = stream.read(size)
    assert text[-1] == 0, text[-1]
    return text.decode(errors='surrogateescape').rstrip('\0')

def read_local(stream: IO[bytes]) -> tuple[str, int, int]:
    name = read_lua_string(stream)
    startpc = read_uint32(stream)
    endpc = read_uint32(stream)
    return name, startpc, endpc

def read_lua_block(stream: IO[bytes]) -> bytes:
    num_count = read_uint32(stream)
    return stream.read(num_count * 4)

def read_lua_code(header: LuaHeader, stream: IO[bytes]) -> bytes:
    ncode = read_uint32(stream)
    return stream.read(header.SIZE_INSTRUCTION // 8 * ncode)


def extract_string_constants(header: LuaHeader, stream: IO[bytes]) -> Iterable[str]:
    str_count = read_uint32(stream)
    yield from (read_lua_string(stream) for _ in range(str_count))
    
    _numbers = read_lua_block(stream)
    func_count = read_uint32(stream)
    for _ in range(func_count):
        yield from extract_lua_text(header, stream)


def extract_lua_text(header: LuaHeader, stream: IO[bytes]) -> Iterable[str]:
    _name = read_lua_string(stream)
    _func_args = stream.read(13)
    num_locals = read_uint32(stream)
    _lua_locals = [read_local(stream) for _ in range(num_locals)]
    _lines = read_lua_block(stream)
    yield from extract_string_constants(header, stream)
    _code = read_lua_code(header, stream)


def parse_compiled_lua(stream: IO[bytes]) -> Iterable[str]:
    header = LuaHeader.parse(stream)
    yield from extract_lua_text(header, stream)


def parse_lua_path(path: str | os.PathLike[str]) -> Iterable[str]:
    with Path(path).open('rb') as stream:
        yield from parse_compiled_lua(stream)


ID_PATTERN = re.compile('[0-9A-Z]{9}')


def attach_ids(it: Iterable[str]) -> Iterable[tuple[str, str]]:
    last_id = None

    for fstr in it:
        if ID_PATTERN.match(fstr):
            last_id = fstr
        elif last_id:
            yield last_id, fstr
            last_id = None


def write_csv(outpath: str | os.PathLike[str], texts: Iterable[tuple[str | os.PathLike[str], Iterable[tuple[str, str]]]]) -> None:
    with open(outpath, errors='surrogateescape', mode='w') as f:
        print('File', 'ID', 'String', sep=',', file=f)
        for path, lines in texts:
            for lid, line in lines:
                outpath = Path(path).with_suffix('.csv').name
                escaped = line.replace('"', '""')
                print(Path(path).stem, lid, f'"{escaped}"', sep=',', file=f)


PATTERN = 'https://docs.google.com/spreadsheets/d/{key}/gviz/tq?tqx=out:csv&sheet={sheet_name}'


def download_csv_sheet(key: str, sheet_name: str) -> bytes:
    url = PATTERN.format(key=key, sheet_name=sheet_name)
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def read_online_csv(key: str, sheet_name: str) -> Iterable[dict[str, str]]:
    with io.BytesIO(download_csv_sheet(key, sheet_name)) as bstream:
        with io.TextIOWrapper(bstream, encoding='utf-8', errors='strict') as stream:
            reader = csv.DictReader(stream)
            yield from reader


def encode_lua_string(string: bytes) -> bytes:
    return struct.pack('<I', len(string) + 1) + string + b'\x00'


def write_lub_files(basepath: str | os.PathLike[str], lines: Iterable[dict[str, str]]) -> None:
    for spath, lines in itertools.groupby(lines, lambda x: x['File']):
        data = bytearray((Path(basepath) / spath).with_suffix('.lub').read_bytes())
        for line in lines:
            id_offset = data.index(line['ID'].encode())
            assert data[id_offset + 9] == 0, data[id_offset + 9]
            orig_size = int.from_bytes(data[id_offset + 10 : id_offset + 14], 'little')
            orig_text = data[id_offset + 14 : id_offset + 14 + orig_size].rstrip(b'\x00')
            text_string = line['String'].encode('windows-1252')
            assert orig_text == text_string, (orig_text, text_string)
            if line['Translation']:
                workstring = '\n'.join(get_display(s) for s in textwrap.wrap(line['Translation'], 21))
                text_string = workstring.encode('windows-1255')
            data[id_offset + 10 : id_offset + 14 + orig_size] = encode_lua_string(text_string)
        Path(spath).with_suffix('.lub').write_bytes(data)


if __name__ == '__main__':
    path = Path(r'C:\GOG Games\Psychonauts\WorkResource\Localization\English')
    write_csv(
        path.with_suffix('.csv').name,
        ((fpath, attach_ids(parse_lua_path(fpath))) for fpath in Path(path).glob('*.lub')),
    )

    sheets_key = Path('google_sheets_id.txt')
    if not sheets_key.exists():
        print(
            'Unable to load texts from sheets:\n'
            '\tPlease make sure you have a file named google_sheets_id.txt in the current directory\n'
            '\twith the following format:\n\t```\n'
            '\tSHEET_ID,SHEET_NAME\n'
            '\t```\n\twhere SHEET_ID is the ID of the Google Sheet and SHEET_NAME is the name of the sheet to read from'
        )
        exit(1)
    key, sheet_name = sheets_key.read_text().strip().split(',')
    write_lub_files(path, read_online_csv(key, sheet_name))
