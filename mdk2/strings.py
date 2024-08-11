import csv
import operator
import pathlib


def read_uint32(data, offset):
    return int.from_bytes(data[offset:offset+4], 'little', signed=False)


def write_uint32(value):
    return value.to_bytes(4, 'little', signed=False)


def parse_string_file(strings_data):
    unk1 = read_uint32(strings_data, 0x00)
    unk2 = read_uint32(strings_data, 0x04)
    assert (unk1, unk2) == (2003, 2), (unk1, unk2)
    num_entries = read_uint32(strings_data, 0x08)
    table_offset = read_uint32(strings_data, 0x0C)
    assert table_offset == 0x18
    texts_offset = read_uint32(strings_data, 0x10)
    assert texts_offset == 0x18 + 12 * num_entries
    voices_offset = read_uint32(strings_data, 0x14)

    tables = strings_data[0x18:0x18 + 12 * num_entries]
    texts = strings_data[texts_offset:voices_offset].decode('utf-16')
    voices = strings_data[voices_offset:]

    # read table - 4 bytes index 4 bytes relative offset in texts, 4 bytes relative offset in voices

    table_indexed = [read_uint32(tables, i) for i in range(0, len(tables), 12)]
    table_texts = [read_uint32(tables, i+4) for i in range(0, len(tables), 12)]
    table_voices = [read_uint32(tables, i+8) for i in range(0, len(tables), 12)]

    for entry, text, voice in zip(table_indexed, table_texts, table_voices):
        line = texts[text // 2:].split('\0')[0].replace('"', '""') if text != 0xFFFFFFFF else None
        voice = voices[voice:].split(b'\0')[0].decode('ascii') if voice != 0xFFFFFFFF else None
        yield entry, line, voice

def write_csv(fname, entries):
    with open(fname, 'w', encoding='utf-8', errors='strict') as f:
        print('index', 'text', 'voice', sep=',', file=f)
        for entry, line, voice in entries:
            if line is None:
                line = '-'
            if voice is None:
                voice = '-'
            print(entry, f'"{line}"', f'"{voice}"', sep=',', file=f)

def read_csv(fname):
    with open(fname, 'r', encoding='utf-8', errors='strict') as f:
        reader = csv.DictReader(f)
        yield from reader

def write_strings_file(entries):
    entries = list(entries)
    strings_data = bytearray()
    strings_data += write_uint32(2003)
    strings_data += write_uint32(2)
    num_entries = len(entries)
    strings_data += write_uint32(num_entries)
    table_offset = len(strings_data) + 12
    assert table_offset == 0x18, table_offset
    strings_data += write_uint32(table_offset)
    texts_offset = table_offset + 12 * num_entries
    strings_data += write_uint32(texts_offset)

    tables = bytearray()
    texts = bytearray()
    voices = bytearray()
    for entry in entries:
        print(entry)
        index, text, voice = operator.itemgetter('index', 'text', 'voice')(entry)
        eindex = int(index)
        text_offset = len(texts)
        if text != '-':
            texts += (text + '\0').encode('utf-16le')
        else:
            text_offset = 0xFFFFFFFF
        voice_offset = len(voices)
        if voice != '-':
            voices += voice.ljust(16, '\0').encode('ascii') 
        else:
            voice_offset = 0xFFFFFFFF
        tables += write_uint32(eindex)
        tables += write_uint32(text_offset)
        tables += write_uint32(voice_offset)

    voices_offset = texts_offset + len(texts)
    strings_data += write_uint32(voices_offset)

    return bytes(strings_data + tables + texts + voices)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Convert mdk2.str format to csv and vice versa')
    parser.add_argument('-i', '--input', required=True, help='Input file to read from')
    parser.add_argument('-f', '--format', choices=['csv', 'str'], default=None, help='Format of the input file, output format is inferred as the opposite')
    parser.add_argument('output', nargs='?', help='Output file to write to')

    args = parser.parse_args()
    # Based on the given files extensions, we can either read or write.

    input_path = pathlib.Path(args.input)
    frmt = args.format or input_path.suffix[1:]
    if frmt not in ('csv', 'str'):
        raise ValueError(f'Unknown format {frmt} for {args.input}, please specify with -f')

    if frmt == 'str':
        output = args.output or input_path.with_suffix('.csv')
        strings_data = pathlib.Path(args.input).read_bytes()
        write_csv(output, parse_string_file(strings_data))
    elif frmt == 'csv':
        output = args.output or input_path.with_suffix('.str')
        entries = list(read_csv(args.input))
        pathlib.Path(output).write_bytes(write_strings_file(entries))
    else:
        raise ValueError(f'Unknown file extension for {args.input}')
