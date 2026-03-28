import xml.etree.ElementTree as ET
from pathlib import Path

found = False
for vol_file in sorted(Path('Treasury Regulations').glob('CFR-2025-title26-vol*.xml')):
    if found:
        break
    tree = ET.parse(str(vol_file))
    root = tree.getroot()
    for sec in root.findall('.//SECTION'):
        sno = (sec.findtext('SECTNO') or '').strip()
        if '1.704-1' in sno:
            print('Found in', vol_file.name, 'sno=', sno)
            paras = sec.findall('P')
            for i, p in enumerate(paras[:40]):
                txt = (p.text or '')[:140]
                print(f'P[{i}]: {txt}')
            found = True
            break

if not found:
    print('Not found')
