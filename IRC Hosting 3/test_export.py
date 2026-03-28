#!/usr/bin/env python3
"""
Quick test export: index + 5 IRC + 6 Treasury pages into dist_pages/test/
"""

import sys
import json
import html as html_lib
from pathlib import Path

HOSTING_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOSTING_DIR))

from IRC_Parser_XML import IRCXMLParser
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
from export_static_html import (
    _static_search_script, _build_treas_html, _build_index_page, _patch_irc_html_for_static, _sanitize_filename,
)

OUTPUT_DIR = HOSTING_DIR / "dist_pages" / "test"
IRC_TEST_SECTIONS = ["1", "368", "704", "707", "723"]
TREAS_TEST_SECTIONS = ["1.704-1", "1.704-2", "1.707-0", "1.707-1", "1.707-5", "301.7701-2"]

print("[IRC] Loading XML...")
irc_parser = IRCXMLParser(r"C:\Users\jcargalbley\Documents\playwright\IRC Hosting 2\IRC\usc26.xml")
root = irc_parser.load_xml()
irc_parser.parse_sections(root, IRC_TEST_SECTIONS)
irc_sections = irc_parser.sections
irc_parser._rendered_section_numbers = [s.sectionNumber for s in irc_sections]
print(f"  {len(irc_sections)} IRC sections indexed")

print("\n[Treasury] Parsing XML...")
treas_parser = TreasuryRegsXMLParser(r"C:\Users\jcargalbley\Documents\playwright\IRC Hosting 2\Treasury Regulations\CFR-2025-title26-vol*.xml")
treas_sections = treas_parser.parse(requested_sections=TREAS_TEST_SECTIONS)
treas_parser._rendered_section_numbers = [s.sectionNumber for s in treas_sections]
print(f"Loaded {len(treas_sections)} distinct Treasury Regulation sections from 21 XML files")

# Find only the requested Treasury sections
found_treas = []
for target in TREAS_TEST_SECTIONS:
    for section in treas_sections:
        if section.sectionNumber == target:
            found_treas.append(section)
            html = _build_treas_html(section, [s.sectionNumber for s in irc_sections], [s.sectionNumber for s in treas_sections])
            filename = _sanitize_filename(section.sectionNumber)
            output_file = OUTPUT_DIR / f"treas_{filename}.html"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(html, encoding='utf-8')
            print(f"  [OK] treas {section.sectionNumber}")
            break

# Now write IRC pages
print("\n[Writing] IRC pages...")
for section in irc_sections:
    html = irc_parser._build_html(section)
    html = _patch_irc_html_for_static(html, [s.sectionNumber for s in irc_sections], [s.sectionNumber for s in found_treas])
    filename = _sanitize_filename(section.sectionNumber)
    output_file = OUTPUT_DIR / f"irc_{filename}.html"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html, encoding='utf-8')
    print(f"  [OK] irc {section.sectionNumber}")

print("\n[Writing] index.html...")
index_html = _build_index_page(
    irc_nums=[s.sectionNumber for s in irc_sections],
    treas_nums=[s.sectionNumber for s in found_treas],
    treas_objects=found_treas,
    irc_sections=irc_sections
)
(OUTPUT_DIR / "index.html").write_text(index_html, encoding='utf-8')
print("  index.html")

print(f"\nDone! {len(irc_sections) + len(found_treas) + 1} files in:\n  {OUTPUT_DIR}")

