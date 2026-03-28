import xml.etree.ElementTree as ET

ns = {'uslm': 'http://xml.house.gov/schemas/uslm/1.0'}
tree = ET.parse('IRC/usc26.xml')
root = tree.getroot()

# Get identifier of section 170
for s in root.findall('.//uslm:section', ns):
    ident = s.get('identifier', '')
    if ident.endswith('/s170'):
        print('Section 170 identifier:', ident)
        break

# Also show first 15 subtitle/chapter/subchapter identifiers
count = 0
for elem in root.iter():
    local = elem.tag.split('}')[-1]
    if local in ('subtitle', 'chapter', 'subchapter', 'part'):
        ident = elem.get('identifier', '')
        if ident and count < 15:
            heading = elem.find('uslm:heading', ns)
            ht = heading.text.strip() if heading is not None and heading.text else ''
            print(f'{local}: {ident!r} -> {ht[:60]}')
            count += 1
