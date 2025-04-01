import csv
import io
import pathlib
import requests

from speech_inject import patch_game

PATTERN = 'https://docs.google.com/spreadsheets/d/{key}/export?format=csv&sheet={sheet_name}'

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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Inject text into The Longest Journey')
    parser.add_argument('-b', '--basedir', type=str, help='Path to game directory', default='.')
    parser.add_argument('-d', '--destination', type=str, help='Directory for writing patched files', default='.')
    args = parser.parse_args()

    basedir = pathlib.Path(args.basedir)
    patch_dir = pathlib.Path(args.destination)
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
    patch_game(basedir, read_online_csv(key, sheet_name), patch_dir)
