#!/usr/bin/env python3
"""
Fixed static HTML exporter - rewrites JavaScript URLs to work with static files.
"""

import sys
import os
import re
from pathlib import Path

# Add current directory to path for imports
HOSTING_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOSTING_DIR))
os.chdir(str(HOSTING_DIR))

import server

OUTPUT_DIR = Path(__file__).resolve().parent / "dist_pages"

def encode_filename(section_num: str) -> str:
    """Encode section number for safe filename."""
    return section_num.replace("/", "_").replace("\\", "_")

def rewrite_search_links(html: str, irc_nums: list, treas_nums: list) -> str:
    """Rewrite the search script JavaScript to use static filenames."""
    
    # Build maps from the actual data
    irc_to_file = {}
    for num in irc_nums:
        irc_to_file[num.lower().replace("[§ ", "").replace("[", "").replace("]", "")] = f"irc_{encode_filename(num)}.html"
    
    treas_to_file = {}
    for num in treas_nums:
        treas_to_file[num.lower()] = f"treas_{encode_filename(num)}.html"
    
    # Find and replace the search anchor function calls
    # Replace: window.location.href = `${toTreasuryAnchor(treasuryMatch)}.html`;
    # With code that returns the actual filename
    
    # Extract the current toTreasuryAnchor function and replace with one that looks up files
    treas_map_js = "const treasuryFileMap = {" + ", ".join([f'"{num}": "treas_{encode_filename(num)}.html"' for num in treas_nums]) + "};"
    
    # Replace toTreasuryAnchor calls with file lookups
    html = re.sub(
        r'window\.location\.href\s*=\s*`\$\{toTreasuryAnchor\(treasuryMatch\)}\s*\.html`',
        'window.location.href = treasuryFileMap[treasuryMatch] || "index.html"',
        html
    )
    
    # Replace IRC section calls: window.location.href = `sec-${ircMatch.toLowerCase()}.html`;
    # With actual filename lookups
    irc_map_js = "const ircFileMap = {" + ", ".join([f'"{num}": "irc_{encode_filename(num)}.html"' for num in irc_nums]) + "};"
    
    html = re.sub(
        r'window\.location\.href\s*=\s*`sec-\$\{ircMatch\.toLowerCase\(\)}\s*\.html`',
        'window.location.href = ircFileMap[ircMatch] || "index.html"',
        html
    )
    
    # Add the maps right before the search script
    if "const ircSectionMap = " in html:
        html = html.replace(
            "const ircSectionMap = ",
            f"{irc_map_js}\n        {treas_map_js}\n        const ircSectionMap = "
        )
    
    return html

def export_all():
    """Export all pages."""
    print("Loading IRC and Treasury data...")
    server.load_data()
    print(f"Loaded {len(server.irc_nums)} IRC sections, {len(server.treas_nums)} Treasury sections\n")
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Export index
    print("Exporting index.html...")
    try:
        html = server.build_index_html()
        html = rewrite_search_links(html, server.irc_nums, server.treas_nums)
        (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
        print("✓ index.html")
    except Exception as e:
        print(f"✗ index.html: {e}")
        return
    
    # Export IRC sections
    print(f"\nExporting {len(server.irc_nums)} IRC sections...")
    for i, num in enumerate(server.irc_nums):
        if i % 500 == 0:
            print(f"  {i}/{len(server.irc_nums)}")
        try:
            html = server.build_irc_html(num)
            html = rewrite_search_links(html, server.irc_nums, server.treas_nums)
            filename = OUTPUT_DIR / f"irc_{encode_filename(num)}.html"
            filename.write_text(html, encoding="utf-8")
        except Exception as e:
            print(f"  ✗ {num}: {e}")
            if i > 10:  # Stop after first 10 errors
                print("  Too many errors, stopping")
                break
    print(f"✓ Exported IRC sections")
    
    # Export Treasury sections
    print(f"\nExporting {len(server.treas_nums)} Treasury sections...")
    for i, num in enumerate(server.treas_nums):
        if i % 500 == 0:
            print(f"  {i}/{len(server.treas_nums)}")
        try:
            html = server.build_treas_html(num)
            html = rewrite_search_links(html, server.irc_nums, server.treas_nums)
            filename = OUTPUT_DIR / f"treas_{encode_filename(num)}.html"
            filename.write_text(html, encoding="utf-8")
        except Exception as e:
            print(f"  ✗ {num}: {e}")
            if i > 10:
                print("  Too many errors, stopping")
                break
    print(f"✓ Exported Treasury sections")
    
    print(f"\n✓ All files exported to {OUTPUT_DIR}")

if __name__ == "__main__":
    export_all()
