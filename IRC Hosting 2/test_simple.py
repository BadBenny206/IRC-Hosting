#!/usr/bin/env python3
"""
Simple test - just verify basic page generation works.
No link rewriting yet.
"""

import sys
import os
from pathlib import Path

# Add current directory to path for imports
HOSTING_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HOSTING_DIR))
os.chdir(str(HOSTING_DIR))

import server
import re

OUTPUT_DIR = Path(__file__).resolve().parent / "test_pages"

def rewrite_urls_for_static(html):
    """Rewrite server URLs to static file paths."""
    if not html:
        return html
    
    # Build maps for all IRC and Treasury sections
    irc_map = {str(num): f"irc_{num}.html" for num in server.irc_nums}
    treas_map = {section.sectionNumber: f"treas_{section.sectionNumber.replace('/', '_')}.html" 
                 for section in server.treas_ordered}
    
    # Escape special regex characters in keys for the map
    def escape_for_regex(s):
        return re.escape(s)
    
    # Replace IRC links: /irc.html?s=123 or /irc.html?s=123-a 
    def replace_irc_link(match):
        section = match.group(1)
        return irc_map.get(section, match.group(0))
    
    # Replace Treasury links: /treas.html?s=1.1-1 etc
    def replace_treas_link(match):
        section = match.group(1)
        return treas_map.get(section, match.group(0))
    
    # Replace /irc.html?s=SECTION_NUM with irc_SECTION_NUM.html
    html = re.sub(r'/irc\.html\?s=([^"\'&\s]+)', replace_irc_link, html)
    
    # Replace /treas.html?s=SECTION_NUM with treas_SECTION_NUM.html  
    html = re.sub(r'/treas\.html\?s=([^"\'&\s]+)', replace_treas_link, html)
    
    # Replace links in href attributes that start with /irc or /treas
    html = re.sub(r'href=["\']?/irc\.html\?s=([^"\'&\s]+)', lambda m: f'href="{irc_map.get(m.group(1), m.group(0))}"', html)
    html = re.sub(r'href=["\']?/treas\.html\?s=([^"\'&\s]+)', lambda m: f'href="{treas_map.get(m.group(1), m.group(0))}"', html)
    
    return html

def test_basic_generation():
    """Test that pages can be generated without errors."""
    print("Loading data...")
    server.load_data()
    print("✓ Data loaded successfully\n")
    
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Test 1: Index
    print("1. Testing index.html generation...")
    try:
        html = server.build_index_html()
        html = rewrite_urls_for_static(html)  # Rewrite URLs
        if html and len(html) > 1000:
            (OUTPUT_DIR / "index.html").write_text(html, encoding="utf-8")
            print(f"   ✓ Generated {len(html):,} bytes")
        else:
            print(f"   ✗ Index HTML too short: {len(html) if html else 'None'} bytes")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return
    
    # Test 2: Single IRC section
    print("\n2. Testing IRC section generation...")
    try:
        html = server.build_irc_html("1")
        html = rewrite_urls_for_static(html)  # Rewrite URLs
        if html and len(html) > 500:
            (OUTPUT_DIR / "irc_1.html").write_text(html, encoding="utf-8")
            # Check for search script
            if "window.location.href" in html and "ircMatch" in html:
                print(f"   ✓ Generated {len(html):,} bytes with search script")
            else:
                print(f"   ⚠ Generated but missing search script")
        else:
            print(f"   ✗ IRC HTML too short: {len(html) if html else 'None'} bytes")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return
    
    # Test 3: Single Treasury section
    print("\n3. Testing Treasury regulation generation...")
    try:
        if server.treas_ordered:
            section = server.treas_ordered[0]
            html = server.build_treas_html(section)
            html = rewrite_urls_for_static(html)  # Rewrite URLs
            if html and len(html) > 500:
                filename = f"treas_{section.sectionNumber.replace('/', '_')}.html"
                (OUTPUT_DIR / filename).write_text(html, encoding="utf-8")
                if "window.location.href" in html and "treasMatch" in html:
                    print(f"   ✓ Generated {len(html):,} bytes with search script")
                else:
                    print(f"   ⚠ Generated but missing search script")
            else:
                print(f"   ✗ Treasury HTML too short: {len(html) if html else 'None'} bytes")
        else:
            print("   ✗ No Treasury sections available")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n✓ All basic tests passed!")
    print(f"Test pages saved to: {OUTPUT_DIR}")
    print(f"\nNow manually test:")
    print(f"  1. Open index.html in browser - check layout")
    print(f"  2. Try search on index - click on a link")
    print(f"  3. Check that IRC page loads")
    print(f"  4. Try search on IRC page")
    print(f"  5. Check that Treasury reg page loads")

if __name__ == "__main__":
    test_basic_generation()
