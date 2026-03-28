import xml.etree.ElementTree as ET

# Parse XML
tree = ET.parse('IRC/usc26.xml')
root = tree.getroot()

print(f"Root tag: {root.tag}")

# Search for section elements with iter (ignores namespace)
count = 0
for section in root.iter('section'):
    ident = section.get('identifier')
    if ident and '/s1' in ident:
        count += 1
        num_elem = section.find('num')
        print(f"Found section {count}: {ident}")
        print(f"  num: {num_elem.text if num_elem is not None else 'None'}")
        if count >= 1:
            break

print(f"Total 'section' elements: {count}")

# Try with namespace
ns = {'uslm': 'http://xml.house.gov/schemas/uslm/1.0'}
sections_ns = root.findall('.//uslm:section', ns)
print(f"Sections found with namespace: {len(sections_ns)}")

# Try full namespace URI
full_ns = '{http://xml.house.gov/schemas/uslm/1.0}'
count2 = 0
for elem in root.iter(f'{full_ns}section'):
    count2 += 1
print(f"Sections found with full namespace URI: {count2}")
