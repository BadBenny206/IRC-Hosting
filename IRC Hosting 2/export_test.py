#!/usr/bin/env python3
"""Test export - index + 5 IRC sections + 5 treasury sections with URL rewriting"""

import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import server

OUTPUT_DIR = Path(__file__).parent / "test_pages"
OUTPUT_DIR.mkdir(exist_ok=True)

def rewrite_urls(html):
    """Convert server URLs to static file paths"""
    # /irc.html?s=123 -> irc_123.html
    html = re.sub(r'/irc\.html\?s=([^"]+)"', r'irc_\1.html"', html)
    # /treas.html?s=123 -> treas_123.html
    html = re.sub(r'/treas\.html\?s=([^"&]+)', r'treas_\1.html', html)
    # href="/" -> href="index.html"
    html = re.sub(r'href="/"', 'href="index.html"', html)
    return html

# Load data
print("Loading data...", end=" ", flush=True)
server.load_data()
print("✓")

# Export index
print("Exporting index...", end=" ", flush=True)
html = server.build_index_html()
html = rewrite_urls(html)
(OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
print("✓")

# Export 5 IRC sections
print("Exporting 5 IRC sections...", end=" ", flush=True)
for i, section_num in enumerate(server.irc_nums[:5]):
    html = server.build_irc_html(section_num)
    html = rewrite_urls(html)
    (OUTPUT_DIR / f"irc_{section_num}.html").write_text(html, encoding="utf-8")
print("✓")

# Export 5 treasury sections
print("Exporting 5 treasury sections...", end=" ", flush=True)
for treas_section in server.treas_ordered[:5]:
    html = server.build_treas_html(treas_section)
    html = rewrite_urls(html)
    filename = treas_section.replace(" ", "_").replace(".", "-")
    (OUTPUT_DIR / f"treas_{filename}.html").write_text(html, encoding="utf-8")
print("✓")

print("\nDone! Files in test_pages/")
print("Open test_pages/index.html in browser to test")
