import xml.etree.ElementTree as ET

root = ET.parse(r'C:\Users\jcargalbley\Documents\playwright\IRC Hosting 2\Treasury Regulations\CFR-2025-title26-vol20.xml').getroot()

for section_elem in root.iter():
    if section_elem.tag == 'SECTION':
        sectno = section_elem.findtext('SECTNO', '')
        if '301.7701-2' in sectno:
            print(f'Section: {sectno}')
            print(f'Children in order:')
            for i, child in enumerate(section_elem):
                if child.tag in ('P', 'EXTRACT', 'EXAMPLE', 'SUBJECT', 'SECTNO'):
                    text_preview = (ET.tostring(child, encoding='unicode')[:80]).replace('\n', ' ')
                    print(f'  [{i}] {child.tag}: {text_preview}...')
            break
