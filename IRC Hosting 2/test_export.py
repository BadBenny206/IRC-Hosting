#!/usr/bin/env python3
"""
Test export - generate only a few pages to verify search and links work.
"""

import sys
import os
from pathlib import Path
from urllib.parse import quote

# Add current directory to path for imports
HOSTING_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOSTING_DIR))
os.chdir(str(HOSTING_DIR))

import server

OUTPUT_DIR = Path(__file__).resolve().parent / "test_pages"

def encode_filename(section_num: str) -> str:
    """Encode section number for safe filename."""
    return section_num.replace("/", "_").replace("\\", "_")

def rewrite_links_for_static(html: str, irc_nums: list, treas_nums: list) -> str:
    """Rewrite all server-style links to static file paths using regex."""
    import re
    
    # Single-pass regex replacement for IRC links
    def replace_irc(match):
        section_num = match.group(1)
        return f'irc_{encode_filename(section_num)}.html"'
    
    html = re.sub(r'/irc\.html\?s=([^"]+)"', replace_irc, html)
    
    # Single-pass regex replacement for Treasury links
    def replace_treas(match):
        section_num = match.group(1)
        return f'treas_{encode_filename(section_num)}.html"'
    
    html = re.sub(r'/treas\.html\?s=([^"]+)"', replace_treas, html)
    
    # Replace the JavaScript search navigation functions
    html = html.replace(
        "window.location.href = `/irc.html?s=${encodeURIComponent(ircMatch)}`",
        "window.location.href = 'irc_' + ircMatch.replace(/[/\\\\]/g, '_') + '.html'"
    )
    html = html.replace(
        "window.location.href = `/treas.html?s=${encodeURIComponent(treasMatch)}`",
        "window.location.href = 'treas_' + treasMatch.replace(/[/\\\\]/g, '_') + '.html'"
    )
    
    return html

def test_export():
    """Export a small test set to verify functionality."""
    print("Loading IRC and Treasury data...")
    server.load_data()
    
    print(f"Exporting test pages to {OUTPUT_DIR}...")
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Export index
    print("\n1. Generating index.html...")
    index_html = server.build_index_html()
    index_html = rewrite_links_for_static(index_html, server.irc_nums, server.treas_nums)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("   ✓ index.html written")
    
    # Export 5 IRC sections
    print("\n2. Generating 5 test IRC section pages...")
    test_irc = ['1', '11', '101', '704', '1502']
    for section_num in test_irc:
        html = server.build_irc_html(section_num)
        if html:
            html = rewrite_links_for_static(html, server.irc_nums, server.treas_nums)
            filename = f"irc_{encode_filename(section_num)}.html"
            (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")
            print(f"   ✓ {filename}")
        else:
            print(f"   ✗ Failed to generate IRC {section_num}")
    
    # Export 5 Treasury sections
    print("\n3. Generating 5 test Treasury regulation pages...")
    test_treas = server.treas_ordered[:5]  # First 5
    for section in test_treas:
        html = server.build_treas_html(section)
        if html:
            html = rewrite_links_for_static(html, server.irc_nums, server.treas_nums)
            filename = f"treas_{encode_filename(section.sectionNumber)}.html"
            (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")
            print(f"   ✓ {filename}")
        else:
            print(f"   ✗ Failed to generate Treasury {section.sectionNumber}")
    
    total = len(list(OUTPUT_DIR.glob('*.html')))
    print(f"\n✓ Test export complete!")
    print(f"  Total files: {total}")
    print(f"  Test location: {OUTPUT_DIR}")
    print(f"\nNow test these manually:")
    print(f"  1. Open test_pages/index.html - try searching for '1' or '1.704-1'")
    print(f"  2. Open test_pages/irc_1.html - try searching for '11' or '704'")
    print(f"  3. Open test_pages/treas_*.html - verify page content looks right")

if __name__ == "__main__":
    test_export()
