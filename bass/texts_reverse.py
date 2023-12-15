import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import csv

def prettify(elem):
    """Return a pretty-printed XML string for the Element."""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_string = reparsed.toprettyxml(indent="  ", encoding='utf-8').decode()
    # Replace "&quot;" with "\""
    return pretty_string.replace('&quot;', '"')

def csv_to_xml(csv_file):
    # Open CSV file for reading
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader)  # Skip header row

        # Initialize variables
        current_file = None
        current_block = None
        root = None

        # Iterate over rows in CSV file
        for row in reader:
            file_name, block_id, text_id, comment, text_content, translation = row

            # If new file, write previous file (if any) and start new root and block
            if file_name != current_file:
                if root is not None:
                    with open(current_file, 'w', encoding='utf-8') as f:
                        f.write(prettify(root))
                        print(f'written {current_file}')

                root = ET.Element('bassru-text')
                current_block = ET.SubElement(root, 'block', {'id': block_id})
                current_file = file_name

            # If new block, start new block
            elif block_id != current_block.get('id'):
                current_block = ET.SubElement(root, 'block', {'id': block_id})

            # Add text element to current block
            ET.SubElement(current_block, 'text', {'id': text_id, 'comment': comment, 'mode': 'ru'}).text = translation if translation else text_content

        # Write last file
        if root is not None:
            with open(current_file, 'w', encoding='utf-8') as f:
                f.write(prettify(root))
                print(f'written {current_file}')

# Convert CSV to XML
csv_to_xml('output.csv')
