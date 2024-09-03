
import io
import pathlib
import csv

from strings import write_strings_file
import requests

from bidi import get_display

char_map = {
    'א': 'u',
    'ב': 'c',
    'ג': 'b',
    'ד': 'n',
    'ה': 'd',
    'ו': 'l',
    'ז': 'r',
    'ח': 'o',
    'ט': 'a',
    'י': 'i',
    'כ': 's',
    'ל': 'h',
    'מ': 'v',
    'נ': 't',
    'ס': 'k',
    'ע': 'e',
    'פ': 'x',
    'צ': 'z',
    'ק': 'q',
    'ר': 'f',
    'ש': 'w',
    'ת': '<',
    'ץ': 'g',
    'ף': 'y',
    'ך': 'p',
    'ן': 'j',
    'ם': '>',
}


def replace_chars(text, char_map):
    return ''.join(char_map.get(c, c) for c in text)


PATTERN = 'https://docs.google.com/spreadsheets/d/{key}/gviz/tq?tqx=out:csv&sheet={sheet_name}'

def download_csv_sheet(key, sheet_name):
    url = PATTERN.format(key=key, sheet_name=sheet_name)
    response = requests.get(url)
    response.raise_for_status()
    return response.content


def read_online_csv(key, sheet_name):
    with io.BytesIO(download_csv_sheet(key, sheet_name)) as bstream:
        with io.TextIOWrapper(bstream, encoding='utf-8', errors='strict') as stream:
            reader = csv.DictReader(stream)
            yield from reader


def translate_entry(entry):
    text, translation = entry['text'], entry.get('translation')
    return dict(
        entry,
        text='\n'.join(replace_chars(get_display(line), char_map) for line in translation.split('\n')) if translation else text
    )


if __name__ == '__main__':
    sheets_key = pathlib.Path('google_sheets_id.txt')
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
    entries = list(read_online_csv(key, sheet_name))
    entries = [translate_entry(entry) for entry in entries]
    pathlib.Path('mdk2.str').write_bytes(write_strings_file(entries))
