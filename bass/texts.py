# Converts exports of https://github.com/old-games/game-utilities/tree/master/Beneath%20a%20Steel%20Sky to csv

import os
import xml.etree.ElementTree as ET
import csv
import glob

def xml_to_csv(xml_files_glob, csv_file):
    # Open CSV file for writing
    with open(csv_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["file_name", "block_id", "text_id", "comment", "text", "translation"])

        # Iterate over XML files
        for xml_file in glob.glob(xml_files_glob):
            print(xml_file)
            # Parse XML data
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Iterate over blocks in XML data
            for block in root.findall('block'):
                block_id = block.get('id')

                # Iterate over text elements in each block
                for text in block.findall('text'):
                    text_id = text.get('id')
                    comment = text.get('comment')
                    text_content = text.text

                    # Write data to CSV file
                    writer.writerow([os.path.basename(xml_file), block_id, text_id, comment, text_content, ''])

# Convert XML to CSV
xml_to_csv('orig/*.xml', 'output.csv')
