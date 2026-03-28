"""Diagnostic: print first 20 sections with their hierarchy to debug index order."""
import sys, os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from IRC_Parser_XML import IRCXMLParser

parser = IRCXMLParser("IRC/usc26.xml")
root = parser.load_xml()
parser._heading_map = parser._build_heading_map(root)
parser._section_parent_map = parser._build_section_parent_map(root)

# Collect first 20 sections from the XML (document order)
count = 0
for elem in root.findall(".//uslm:section", parser.ns):
    identifier = elem.get("identifier", "")
    m = re.search(r"/s(\d+[A-Za-z]*)$", identifier)
    if not m:
        continue
    num_elem = elem.find("uslm:num", parser.ns)
    raw_num = num_elem.text if num_elem is not None and num_elem.text else m.group(1)
    snum = parser._clean_section_number(raw_num)
    hier = parser._section_hierarchy(identifier)
    types = [(e["type"], e.get("num","")[:30]) for e in hier]
    print(f"  sec={snum!r:12s}  id={identifier!r:60s}  hier={types}")
    count += 1
    if count >= 20:
        break
