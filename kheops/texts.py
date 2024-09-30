import pathlib
import struct
from typing import cast, IO

import cryobf

ENTRY = struct.Struct('<4I')

def csvquote(text):
    text = text.replace('"', '""')
    return f'"{text}"'


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('archive')  # loc_UK_cmn.bf
    parser.add_argument('textfile')  # TXT/TreasureIsland.bin
    args = parser.parse_args()

    with cryobf.open(args.archive) as archive:
        text_entries = archive.glob(args.textfile)
        for textfile in text_entries:
            with textfile.open('rb') as bfin:
                fin = cast(IO[bytes], bfin)
                header = fin.read(12)
                first_offset = int.from_bytes(fin.read(4), 'little')
                num_entries = int.from_bytes(fin.read(4), 'little')
                entries = [ENTRY.unpack(fin.read(ENTRY.size)) for _ in range(num_entries)]
                with open(f'{textfile.stem}.csv', 'w', encoding='utf-8') as out:
                    print('ID', 'Voice', 'Text', 'Translation', sep=',', file=out)
                    assert fin.tell() == first_offset, (fin.tell(), first_offset)
                    for i, entry in enumerate(entries):
                        ident = entry[0]
                        voice = fin.read(entry[1])
                        text = fin.read(entry[2])
                        assert entry[3] == 0, entry
                        print(ident, voice.decode('cp1252').rstrip('\0'), csvquote(text.decode('cp1252').rstrip('\0')), '', sep=',', file=out)

                    assert not fin.read(), 'Extra data at end of file'

            original = textfile.read_bytes()

            import csv
            output = bytearray()
            index = bytearray(header)
            with open(f'{textfile.stem}-New.csv', 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            offset = len(rows) * ENTRY.size + len(header) + 8
            index += offset.to_bytes(4, 'little')
            index += len(rows).to_bytes(4, 'little')
            for row in rows:
                voice = row['Voice'].encode('cp1252')
                text = row['Text'].encode('cp1252').replace(b'\n\n', b'\r\n')
                if row['Translation']:
                    text = row['Translation'].encode('cp1255').replace(b'\n\n', b'\r\n')
                voice = b'\0' if not voice else voice + b'\0\0\0'
                text = b'\0' if not text else text + b'\0\0\0'
                rentry = ENTRY.pack(int(row['ID']), len(voice), len(text), 0)
                output += voice + text
                index += rentry
                print(row)
                # assert original[offset:offset+len(voice)] == voice, (original[offset:offset+len(voice)], voice)
                # assert original[offset+len(voice):offset+len(voice)+len(text)] == text, (original[offset+len(voice):offset+len(voice)+len(text)], text)
                offset += len(voice) + len(text)

            # assert bytes(index + output) == original, 'Rebuilt file does not match original' 
            pathlib.Path(f'{textfile.stem}-NEW.bin').write_bytes(bytes(index + output))
