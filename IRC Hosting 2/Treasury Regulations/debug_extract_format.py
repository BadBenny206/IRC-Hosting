import xml.etree.ElementTree as ET

# Parse directly
root = ET.parse(r'C:\Users\jcargalbley\Documents\playwright\IRC Hosting 2\Treasury Regulations\CFR-2025-title26-vol20.xml').getroot()

# Find 301.7701-2
for section_elem in root.iter():
    if section_elem.tag == 'SECTION':
        sectno = section_elem.findtext('SECTNO', '')
        if '301.7701-2' in sectno:
            print(f'Found section {sectno}')
            # Find EXTRACT
            for child in section_elem:
                if child.tag == 'EXTRACT':
                    print(f'Found EXTRACT')
                    # Find FP elements
                    fp_elements = child.findall(".//FP")
                    print(f'FP elements found: {len(fp_elements)}')
                    
                    # Extract text from first 3
                    rows = []
                    for i, fp in enumerate(fp_elements[:3]):
                        # Get text
                        text_parts = []
                        for elem in fp.iter():
                            if elem.text and elem.text.strip():
                                text_parts.append(elem.text.strip())
                            if elem.tail and elem.tail.strip():
                                text_parts.append(elem.tail.strip())
                        text_content = " ".join(text_parts).strip()
                        print(f'  FP[{i}]: {text_content}')
                        rows.append(text_content)
                    
                    # Build table markup
                    if rows:
                        table_text = "\n".join(rows)
                        result = f"\n[TABLE]\n{table_text}\n[END TABLE]"
                        print(f'\nTable markup result:\n{result[:100]}...')
                    break
            break
