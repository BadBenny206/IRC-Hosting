#!/usr/bin/env python3
import sys
sys.path.insert(0, r"C:\Users\jcargalbley\Documents\playwright\IRC Hosting 3")

from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
from export_static_html import _build_treas_html
from pathlib import Path

xml_file = r"C:\Users\jcargalbley\Documents\playwright\IRC Hosting 2\Treasury Regulations\CFR-2025-title26-vol21.xml"
parser = TreasuryRegsXMLParser(xml_file)
sections = parser.parse()

# Find 301.7701-2
for section in sections:
    if "301.7701-2" in section.sectionNumber:
        html = _build_treas_html(section, parser._rendered_section_numbers)
        output = Path("dist_pages/test/treas_301_7701_2.html")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding='utf-8')
        
        # Check if American Samoa is in the output
        if "American Samoa" in html:
            print("✓ SUCCESS: American Samoa found in generated HTML!")
        else:
            print("✗ FAIL: American Samoa NOT in HTML")
        break
