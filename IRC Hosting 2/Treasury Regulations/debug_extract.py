import xml.etree.ElementTree as ET
import glob

for f in sorted(glob.glob('CFR-2025-title26-vol*.xml')):
    tree = ET.parse(f)
    root = tree.getroot()
    for section in root.iter():
        if section.tag == 'SECTION':
            sectno = section.findtext('SECTNO', '')
            if '301.7701-2' in sectno:
                print(f'Found in {f}')
                print(f'SECTNO: {sectno}')
                for child in section:
                    if child.tag == 'EXTRACT':
                        print(f'EXTRACT children:')
                        for i, fp in enumerate(child):
                            print(f'  [{i}] {fp.tag}: {fp.text[:60] if fp.text else "(empty)"}')
                            if i >= 5:
                                print('  ...')
                                break
                exit()
