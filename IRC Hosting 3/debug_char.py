#!/usr/bin/env python3
"""Debug character and split behavior for 301.7701-2 P[9]."""
import re
import sys
sys.path.insert(0, '.')
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser

# Test the regex
pattern = re.compile(r"^(.*?)(?:\s*[—-]\s*)\(([^)]+)\)\s*(.*)$")

p9_remainder = "Certain foreign entities \u00f9(i) In general. Except as provided in paragraphs"
p18_remainder = "(9) Business entities with multiple charters. (i) An entity created"

print("=== P[9] remainder test ===")
m = pattern.match(p9_remainder)
if m:
    print(f"MATCH: leading={m.group(1)!r}, marker={m.group(2)!r}, rest={m.group(3)!r}")
else:
    print("NO MATCH")

print("\n=== P[18] remainder test ===")  
m = pattern.match(p18_remainder)
if m:
    print(f"MATCH: leading={m.group(1)!r}, marker={m.group(2)!r}, rest={m.group(3)!r}")
else:
    print("NO MATCH")

# Check what char is at the split point in P[9]
sep_char = "\u00f9"  # ù
print(f"\n=== Character analysis ===")
print(f"ù = U+{ord(sep_char):04X} = {ord(sep_char)}")
print(f"— = U+{0x2014:04X} = {0x2014}")  
print(f"- = U+{0x002D:04X} = {0x002D}")
print(f". = U+{0x002E:04X} = {0x002E}")
print(f"\nDoes [—-] match ù? {bool(re.match(r'[—-]', sep_char))}")
print(f"Does [—-] match .? {bool(re.match(r'[—-]', '.'))}")
print(f"Does [—-] match —? {bool(re.match(r'[—-]', '—'))}")
print(f"Does [—-] match -? {bool(re.match(r'[—-]', '-'))}")

# Now parse the section and count (i) under (8)
parser = TreasuryRegsXMLParser("Treasury Regulations/CFR-2025-title26-vol20.xml")
sections = parser.parse(requested_sections=["301.7701-2"])

def count_tables(nodes, depth=0):
    count = 0
    for n in nodes:
        if n.tagName == "EXTRACT" or "[TABLE]" in (n.content or ""):
            print(f"  {'  '*depth}TABLE found under: sectionId={n.sectionId!r}")
            count += 1
        count += count_tables(n.subsections, depth+1)
    return count

for sec in sections:
    print(f"\n=== Table count in {sec.sectionId!r} ===")
    total = count_tables(sec.subsections)
    print(f"Total tables: {total}")
