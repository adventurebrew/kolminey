from collections.abc import Iterator
from contextlib import contextmanager
import io
import pathlib
from typing import IO, NamedTuple

from pakal.archive import BaseArchive, ArchiveIndex, make_opener


FILENAME_LENGTH = 13

def read_uint32le(f):
    return int.from_bytes(f.read(4), 'little')

def read_uint16le(f):
    return int.from_bytes(f.read(2), 'little')


class DGDSFileEntry(NamedTuple):
    volume: str
    checksum: int
    pos: int
    size: int


def read_index(fa: IO[bytes], base_path) -> Iterator[tuple[str, DGDSFileEntry]]:
    seen_names: dict[str, tuple[int, int]] = {}

    _hash_idx = fa.read(4)
    nvolumes = read_uint16le(fa)
    for _ in range(nvolumes):
        bfname, sep = fa.read(FILENAME_LENGTH).split(b'\0', 1)
        assert sep in {b'\0.', b''}, sep
        fname = bfname.decode('ascii')

        num_entries = read_uint16le(fa)
        entries = [(read_uint32le(fa), read_uint32le(fa)) for _ in range(num_entries)]

        with (base_path / fname).open('rb') as f:
            for checksum, pos in entries:
                assert f.tell() == pos, (f.tell(), pos)
                f.seek(pos)
                bename, rest = f.read(FILENAME_LENGTH).split(b'\0', 1)
                ename = bename.decode('ascii')
                size = read_uint32le(f)

                if size > (1 << 31) or not ename or size == 0:
                    # assert False, (ename, size)
                    continue

                seen = seen_names.get(ename, None)
                if seen:
                    assert (checksum, size) == seen, (ename, checksum, size, seen)
                seen_names[ename] = (checksum, size)

                assert f.tell() == pos + FILENAME_LENGTH + 4

                yield ename, DGDSFileEntry(fname, checksum, f.tell(), size)

                f.seek(size, io.SEEK_CUR)


def read_entry(fname, pos, size):
    # print(fname, pos, size)
    with fname.open('rb') as f:
        f.seek(pos)
        return f.read(size)


class DGDSArchive(BaseArchive[DGDSFileEntry]):
    def _create_index(self) -> 'ArchiveIndex[DGDSFileEntry]':
        if not self._filename:
            raise ValueError('must be opened with a filename')
        return dict(read_index(self._stream, self._filename.parent))

    @contextmanager
    def _read_entry(self, entry: DGDSFileEntry) -> Iterator[IO[bytes]]:
        assert self._filename
        content = read_entry(self._filename.parent / entry.volume, entry.pos, entry.size)
        with io.BytesIO(content) as f:
            yield f


open = make_opener(DGDSArchive)

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('fname', help='Path to the game resource map')
    args = parser.parse_args()

    fname = pathlib.Path(args.fname)

    with open(fname) as a:
        a.extractall('extracted')
