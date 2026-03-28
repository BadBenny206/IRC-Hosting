#!/usr/bin/env python3
"""
Generate static HTML pages that mirror the IRC Hosting 2 server output.
This script uses the same rendering functions as the server, but writes to dist_pages/
and rewrites all links to work as static files.
"""

import sys
import os
import re
import json
from pathlib import Path
from urllib.parse import quote, unquote

# Add current directory to path for imports
HOSTING_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOSTING_DIR))
os.chdir(str(HOSTING_DIR))

import server

OUTPUT_DIR = Path(__file__).resolve().parent / "dist_pages"

def encode_filename(section_num: str) -> str:
    """Encode section number for safe filename."""
    return section_num.replace("/", "_").replace("\\", "_")

def create_link_mappings(irc_nums: list, treas_nums: list) -> tuple:
    """Pre-build mappings of section numbers to filenames for faster lookup."""
    irc_map = {}
    treas_map = {}
    
    for num in irc_nums:
        irc_map[num] = f'irc_{encode_filename(num)}.html'
        irc_map[quote(num)] = f'irc_{encode_filename(num)}.html'
    
    for num in treas_nums:
        treas_map[num] = f'treas_{encode_filename(num)}.html'
        treas_map[quote(num)] = f'treas_{encode_filename(num)}.html'
    
    return irc_map, treas_map

def rewrite_links_for_static(html: str, irc_map: dict, treas_map: dict) -> str:
    """Rewrite all server-style links to static file paths using pre-built maps."""
    
    # Replace Treasury links: /treas.html?s=... → treas_....html
    for treas_num, filename in treas_map.items():
        patterns = [
            (f'/treas.html?s={treas_num}"', f'{filename}"'),
        ]
        for search, replace in patterns:
            if search in html:
                html = html.replace(search, replace)
    
    # Replace IRC links: /irc.html?s=... → irc_....html
    for irc_num, filename in irc_map.items():
        patterns = [
            (f'/irc.html?s={irc_num}"', f'{filename}"'),
        ]
        for search, replace in patterns:
            if search in html:
                html = html.replace(search, replace)
    
    # Fix JavaScript search navigation - server already generates irc_${ircMatch} but missing .html
    html = html.replace(
        "`irc_${ircMatch}`",
        "`irc_${ircMatch}.html`"
    )
    html = html.replace(
        "`treas_${encodeURIComponent(treasMatch)}`",
        "`treas_${encodeURIComponent(treasMatch)}.html`"
    )
    # Handle all server-style URL patterns
    html = html.replace(
        "window.location.href = `/irc.html?s=${encodeURIComponent(ircMatch)}`",
        "window.location.href = `irc_${ircMatch}.html`"
    )
    html = html.replace(
        "window.location.href = `/irc.html?s=${ircMatch}`",
        "window.location.href = `irc_${ircMatch}.html`"
    )
    html = html.replace(
        "window.location.href = `/treas.html?s=${encodeURIComponent(treasMatch)}`",
        "window.location.href = `treas_${encodeURIComponent(treasMatch)}.html`"
    )
    html = html.replace(
        "window.location.href = `/treas.html?s=${treasMatch}`",
        "window.location.href = `treas_${encodeURIComponent(treasMatch)}.html`"
    )
    # Fix section-page style URLs (used on irc_*.html and treas_*.html pages)
    html = html.replace(
        "window.location.href = `${toTreasuryAnchor(treasuryMatch)}.html`",
        "window.location.href = `treas_${encodeURIComponent(treasuryMatch)}.html`"
    )
    html = html.replace(
        "window.location.href = `sec-${ircMatch.toLowerCase()}.html`",
        "window.location.href = `irc_${ircMatch}.html`"
    )
    # Fix home link
    html = html.replace('href="/"', 'href="index.html"')
    
    return html

def export_static(test_mode=False):
    """Export all pages to static HTML files."""
    global OUTPUT_DIR
    if test_mode:
        OUTPUT_DIR = Path(__file__).resolve().parent / "test_pages"
        print("TEST MODE: index + 5 IRC + 5 Treasury -> test_pages/")

    print("Loading IRC and Treasury data...")
    server.load_data()

    if test_mode:
        server.irc_nums = server.irc_nums[:5]
        server.treas_ordered = server.treas_ordered[:5]
    print("Building link mappings...")
    irc_map, treas_map = create_link_mappings(server.irc_nums, server.treas_nums)
    
    print(f"Exporting to {OUTPUT_DIR}...")
    
    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Export index
    print("  Generating index.html...")
    try:
        index_html = server.build_index_html()
        index_html = rewrite_links_for_static(index_html, irc_map, treas_map)
        (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
        print("    OK index.html")
    except Exception as e:
        print(f"    FAIL: {e}")
    
    # Export all IRC sections
    print(f"  Generating {len(server.irc_nums)} IRC section pages...")
    irc_count = 0
    for i, section_num in enumerate(server.irc_nums):
        try:
            html = server.build_irc_html(section_num)
            if html:
                html = rewrite_links_for_static(html, irc_map, treas_map)
                filename = f"irc_{encode_filename(section_num)}.html"
                (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")
                irc_count += 1
                if (irc_count) % 200 == 0:
                    print(f"    [{irc_count}/{len(server.irc_nums)}]")
        except Exception as e:
            print(f"    Error on IRC {section_num}: {e}")
    print(f"    Generated {irc_count} IRC pages")
    
    # Export all Treasury sections
    print(f"  Generating {len(server.treas_ordered)} Treasury section pages...")
    treas_count = 0
    for i, section in enumerate(server.treas_ordered):
        try:
            html = server.build_treas_html(section)
            if html:
                html = rewrite_links_for_static(html, irc_map, treas_map)
                filename = f"treas_{encode_filename(section.sectionNumber)}.html"
                (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")
                treas_count += 1
                if (treas_count) % 500 == 0:
                    print(f"    [{treas_count}/{len(server.treas_ordered)}]")
        except Exception as e:
            print(f"    Error on Treasury {section.sectionNumber}: {e}")
    print(f"    Generated {treas_count} Treasury pages")
    
    total = len(list(OUTPUT_DIR.glob('*.html')))
    print("\nExport complete!")
    print(f"  Total files: {total}")
    print(f"  Location: {OUTPUT_DIR}")

if __name__ == "__main__":
    test_mode = "--test" in sys.argv
    export_static(test_mode=test_mode)
