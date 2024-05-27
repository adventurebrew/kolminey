import csv
import io
import os
from collections.abc import Iterator
from contextlib import contextmanager
import itertools
import pathlib
import struct
from typing import IO, TYPE_CHECKING, NamedTuple

from pakal.archive import BaseArchive, make_opener
from pakal.examples.common import read_uint32_le

if TYPE_CHECKING:
    from pakal.archive import ArchiveIndex


ZFS_ENTRY = struct.Struct('<16s5I')

class ZFSEntry(NamedTuple):
    name: bytes
    offset: int
    id: int
    size: int
    time: int
    unk: int


def extract(stream: IO[bytes], context) -> Iterator[tuple[str, ZFSEntry]]:
    magic = stream.read(4)
    assert magic == b'ZFSF', magic
    unk1 = read_uint32_le(stream)
    assert unk1 == 1, unk1
    max_name_len = read_uint32_le(stream)
    assert max_name_len == 16, max_name_len
    files_per_block = read_uint32_le(stream)
    assert files_per_block == 100, files_per_block
    file_count = read_uint32_le(stream)
    context.xor_key = stream.read(4)
    print(context.xor_key)
    file_section_offset = read_uint32_le(stream)
    print(file_section_offset)

    assert stream.tell() == file_section_offset, (stream.tell(), file_section_offset)

    i = 0
    block_no = 0
    while True:
        next_offset = read_uint32_le(stream)
        empty = False
        for block_idx in range(files_per_block):
            entry = ZFSEntry(
                name=stream.read(max_name_len),
                offset=read_uint32_le(stream),
                id=read_uint32_le(stream),
                size=read_uint32_le(stream),
                time=read_uint32_le(stream),
                unk=read_uint32_le(stream),
            )
            print(block_no, block_idx, entry)
            if entry.size > 0:
                assert not empty, entry
                yield entry.name.rstrip(b'\0').decode('cp862'), entry
                i+= 1
            else:
                assert entry == ZFSEntry(b'\0' * 16, 0, 0, 0, 0, 0), entry
                empty = True
        stream.seek(next_offset, io.SEEK_SET)
        block_no += 1
        if next_offset == 0:
            break
    assert i == file_count, (i, file_count)


def unxor(data: bytes, key: bytes) -> bytes:
    return bytes(x ^ key[i % 4] for i, x in enumerate(data))


def unpack(stream: IO[bytes], entry: ZFSEntry, context) -> IO[bytes]:
    stream.seek(entry.offset)
    data = stream.read(entry.size)
    assert len(data) == entry.size, len(data)

    if set(context.xor_key) != {0}:  # xor_key is not empty
        data = unxor(data, context.xor_key)
    return io.BytesIO(data)


class ZFSArchive(BaseArchive[ZFSEntry]):
    def _create_index(self) -> 'ArchiveIndex[ZFSEntry]':
        return dict(extract(self._stream, context=self))

    @contextmanager
    def _read_entry(self, entry: ZFSEntry) -> Iterator[IO[bytes]]:
        yield unpack(self._stream, entry, context=self)


def decrypt_utf16(content: str) -> tuple[str, set[str]]:
    print(repr(content))
    c, z = zip(*zip(*[iter(content)] * 2))
    st = ''.join(c)
    assert '\0' not in st, repr(st)
    zer = set(''.join(z))
    assert not (zer - {'\0', ' '}), repr(zer)
    assert len(zer) == 1, repr(zer)
    return st, zer


def encrypt_utf16(st: str, sep: set[str]) -> str:
    return ''.join(''.join(x) for x in zip(st, itertools.cycle(sep)))


def extract_texts(csv_writer, archive: ZFSArchive):
    for entry in archive.glob('*.txt'):
        with entry.open('rb', encoding='cp862') as file:
            content = file.read()
            dlines = content.split(b'\r\n\0')
            # st, sep = decrypt_utf16(content)

            if len(dlines) == 1:
                print('DLINES', dlines)
                continue

            # assert encrypt_utf16(st, sep) == content, (encrypt_utf16(st, sep), content)
            for bline in dlines:
                line = bline.decode('utf-16-le')
                # line = line.replace('"', '""')
                if '>' not in line:
                    lines = ['', line]
                else:
                    lines = list(line.split('>', maxsplit=1))
                    lines[0] = f'{lines[0]}>'
                csv_writer.writerow([entry.name, *lines])


def rebuild_archive(archive: ZFSArchive, patches: dict[str, bytes]):
    unk1 = 1
    max_name_len = 16
    files_per_block = 100
    file_count = len(archive.index)
    xor_key = b'\0\0\0\0'
    file_section_offset = 28
    header = bytearray(
        b'ZFSF'
        + struct.pack(
            '<4I4sI',
            unk1,
            max_name_len,
            files_per_block,
            file_count,
            xor_key,
            file_section_offset
        )
    )
    assert len(header) == file_section_offset, len(header)

    offset = file_section_offset
    entries = iter(archive.index.items())
    while file_count > 0:
        block_index = bytearray(b'\0\0\0\0' + b'\0' * 36 * files_per_block)
        offset += len(block_index)
        block_data = bytearray()
        for idx in range(files_per_block):
            if file_count == 0:
                break
            name, entry = next(entries)
            size = entry.size
            if name in patches:
                size = len(patches[name])
                content = patches[name]
            else:
                content = unpack(archive._stream, entry, context=archive).read()
                assert len(content) == size, (len(content), size)
            block_index[4+idx*36:4+(idx + 1)*36]= struct.pack(
                '<16s5I',
                name.encode('cp862'),
                offset,
                entry.id,
                size,
                entry.time,
                entry.unk
            )
            file_count -= 1
            block_data += content
            offset += size
        assert len(block_index) == 4 + files_per_block * 36, (len(block_index), 4 + files_per_block * 36)
        # block_index += struct.pack('<16s5I', b'\0' * 16, 0, 0, 0, 0, 0)
        next_offset = offset
        if file_count > 0:
            block_index[:4] = struct.pack('<I', next_offset)
        header += block_index
        header += block_data

    return bytes(header)



open2 = make_opener(ZFSArchive)


if __name__ == '__main__':
    files = ['zn/subpatch.zfs', 'zgi/subtitle.zfs']
    for file in files:
        filepath = pathlib.Path(file)
        orig = pathlib.Path(filepath).read_bytes()
        with open2(filepath) as archive:
            archive.extractall('output')
            with open(f'texts-{filepath.stem}.csv', 'w', encoding='utf-8', newline='') as out:
                csv_writer = csv.writer(out)
                extract_texts(csv_writer, archive)

            with open(f'texts-{filepath.stem}-he.csv', 'r', encoding='utf-8', newline='') as inp:
                csv_reader = csv.reader(inp)
                patches = {}
                for name, group in itertools.groupby(csv_reader, lambda x: x[0]):
                    content = []
                    for x, pref, line, *rest in group:
                        assert x == name, (x, name)
                        line = pref + line
                        content.append(line.encode('utf-16-le'))
                    # assert content.encode('utf-16-le') == encrypt_utf16(content, {'\0'}).encode('cp862'), (content, content.encode('utf-16-le'), encrypt_utf16(content, {'\0'}).encode('cp862'))
                    patches[name] = b'\r\n\0'.join(content)

            ctnt = rebuild_archive(archive, patches)
            with open(f'rebuild-{filepath.stem}.zfs', 'wb') as out:
                out.write(ctnt)

        with open2(f'rebuild-{filepath.stem}.zfs') as f:
            f.extractall('output2')
            print(len(ctnt), len(orig))
            # assert ctnt[100:5000] == orig[100:2000], (ctnt[100:2000], orig[100:2000])
