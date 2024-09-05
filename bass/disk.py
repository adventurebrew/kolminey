from contextlib import contextmanager
import io
import os
import pathlib
from typing import IO, Iterator, NamedTuple

from pakal.archive import BaseArchive, make_opener, ArchiveIndex, ArchivePath

from rnc_deco import RncDecoder
import rnccs


def load_file(data_disk_handle, file_info):

    offset, size, flags = file_info

    data_disk_handle.seek(offset, os.SEEK_SET)

    content = data_disk_handle.read(size)

    file_header = content[:22]

    uncompressed = (flags >> 23) & 0x1

    if uncompressed or not ((READ_LE_UINT16(file_header) >> 7) & 1):
        return content

    print("File is RNC compressed.")

    decomp_size = (READ_LE_UINT16(file_header) & 0xFF00) << 8
    decomp_size |= READ_LE_UINT16(file_header[12:14])

    input_data = content[22:]
    unpacked = bytearray(decomp_size)
    decoded_size = RncDecoder().unpackM1(input_data, size - 22, unpacked)
    decoded = bytes(rnccs.decompress(input_data))

    print(decoded_size)

    if not decoded:  # Unpack returned 0: file was probably not packed.
        print('Actually... it\'s not')
        return content

    decoded2 = bytes(unpacked)
    # assert a + b'\0' * (decomp_size - len(a)) == b, b[len(a):]

    assert decoded2.startswith(decoded), (decoded, decoded2)
    assert len(decoded) <= len(decoded2), (len(decoded), len(decoded2))

    assert decoded_size > 0, decoded_size
    if not (flags >> 22) & 0x1:  # do we include the header?
        print('HEADER')
        # decomp_size += 22
        decoded = file_header + decoded

    print(decoded2[len(decoded):])
    assert len(decoded) == decomp_size, (len(decoded), decomp_size)

    return decoded


def READ_LE_UINT16(data):
    return int.from_bytes(data[:2], byteorder='little')

def READ_LE_UINT24(data):
    return int.from_bytes(data[:3], byteorder='little')

def READ_LE_UINT32(data):
    return int.from_bytes(data[:4], byteorder='little')


def WRITE_LE_UINT32(num):
    return num.to_bytes(4, byteorder='little')

def WRITE_LE_UINT24(num):
    return num.to_bytes(3, byteorder='little')


class DiskFileEntry(NamedTuple):
    offset: int
    size: int
    flags: int


def write_file_info(entry: DiskFileEntry) -> bytes:
    file_offset = entry.offset
    file_size = entry.size
    file_flags = entry.flags

    if file_offset & 0xF == 0 or file_offset > 0x7FFFFF:
        file_offset >>= 4
        cflag = 1
    else:
        cflag = 0

    assert file_flags & 0xFC00000 == file_flags, file_flags
    assert file_size & 0x3FFFFF == file_size, file_size
    assert file_offset & 0x7FFFFF == file_offset, file_offset

    file_offset = (file_offset & 0x7FFFFF) | (cflag << 23)
    file_flags = (file_flags & 0xFC00000) | (file_size & 0x3FFFFF)

    data = WRITE_LE_UINT24(file_offset) + WRITE_LE_UINT24(file_flags)
    assert read_file_info(data)[:2] == entry[:2], (read_file_info(data), entry)
    assert (read_file_info(data).flags >> 23) & 0x1 == (entry.flags >> 23) & 1, (read_file_info(data).flags >> 23, entry.flags >> 23)

    return data


def read_file_info(data: bytes) -> DiskFileEntry:
    file_offset = READ_LE_UINT24(data)
    file_flags = READ_LE_UINT24(data[3:])
    file_size = file_flags & 0x3FFFFF
    file_flags &= 0xFC00000

    cflag = (file_offset >> 23) & 0x1
    file_offset &= 0x7FFFFF

    if cflag:
        file_offset <<= 4
        assert file_offset & 0xF == 0 or file_offset > 0x7FFFFF, file_offset

    return DiskFileEntry(file_offset, file_size, file_flags)


def read_file_entries(stream: IO[bytes]) -> Iterator[tuple[str, DiskFileEntry]]:
    dinner_table_entries = int.from_bytes(stream.read(4), byteorder='little')
    for _ in range(dinner_table_entries):
        file_num = READ_LE_UINT16(stream.read(2))
        yield str(file_num), read_file_info(stream.read(6))


class DiskArchive(BaseArchive[DiskFileEntry]):
    patches: dict[str, bytes] | None = None

    def _create_index(self) -> 'ArchiveIndex[DiskFileEntry]':
        if not self._filename:
            raise ValueError('Must open via filename')
        dinner = pathlib.Path(self._filename).with_suffix('.dnr')
        with dinner.open('rb') as dnr_handle:
            return dict(read_file_entries(dnr_handle))

    @contextmanager
    def _read_entry(self, entry: DiskFileEntry) -> Iterator[IO[bytes]]:
        yield io.BytesIO(load_file(self._stream, entry))

    def get_file(self, fname: str) -> ArchivePath:
        return ArchivePath(fname, self)

    def patch_file(self, fname: str, data: bytes) -> None:
        if not self.patches:
            self.patches = {}
        self.patches[fname] = data

    def save_as(self, fname: str, index='sky.dnr') -> None:
        index_data = dict(self.index.items())

        last_offset = 0
        patches = self.patches or {}
        print(patches.keys())

        with pathlib.Path(fname).open('wb') as disk_output:
            for fname, (offset, size, flags) in index_data.items():
                if fname in patches:
                    self.index[fname] = DiskFileEntry(last_offset, len(patches[fname]), flags | (1 << 23))
                    disk_output.write(patches[fname])
                else:
                    self.index[fname] = DiskFileEntry(last_offset, size, flags)
                    self._stream.seek(offset)
                    disk_output.write(self._stream.read(size))
                last_offset = disk_output.tell()
                if last_offset > 0x7FFFFF:
                    disk_output.write(b'\0' * ((16 - last_offset ) % 16))
                    last_offset = disk_output.tell()
                    assert last_offset & 0xF == 0, last_offset

            with pathlib.Path(index).open('wb') as index_file:
                index_file.write(len(self.index).to_bytes(4, byteorder='little'))
                for fname, entry in self.index.items():
                    print(fname)
                    index_file.write(int(fname).to_bytes(2, byteorder='little'))
                    index_file.write(write_file_info(entry))



open = make_opener(DiskArchive)

if __name__ == '__main__':
    from rnccs import RNCCompressor, decompress

    open_archive = open
    output_dir = pathlib.Path('outbin')

    disk_path = 'game/sky.dsk'

    with open_archive(disk_path) as arc:
        for fname in arc:
            print(fname)
            data = arc.get_file(fname.name).read_bytes()

            recomp = RNCCompressor.compress(data)
            redecomp = decompress(recomp)
            assert redecomp == data, (len(redecomp), len(data))
            # fn = arc.get_file(fname.name)
            # with fn.open('rb') as f:
            #     print(f.read())
        # arc.extractall(output_dir)
