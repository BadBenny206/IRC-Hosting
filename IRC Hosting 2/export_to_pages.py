#!/usr/bin/env python3
"""
Static HTML export for GitHub Pages - Simple version.
Uses the same rendering as the working server.
"""

import os
import shutil
import json
from pathlib import Path
from IRC_Parser_XML import IRCXMLParser
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser

HOSTING_DIR = Path(__file__).parent

def load_data():
    """Load all data - mimic server.py exactly."""
    
    print("Loading current live app data...")
    
    # IRC
    print("[IRC] Loading usc26.xml...")
    irc_xml = HOSTING_DIR / "IRC" / "usc26.xml"
    irc_parser = IRCXMLParser(str(irc_xml))
    irc_root = irc_parser.load_xml()
    irc_parser._heading_map = irc_parser._build_heading_map(irc_root)
    irc_parser._section_parent_map = irc_parser._build_section_parent_map(irc_root)
    irc_parser._section_elem_map = irc_parser._build_section_element_map(irc_root)
    irc_nums = sorted(irc_parser.discover_all_section_numbers(irc_root))
    print(f"[IRC] {len(irc_nums)} sections indexed")
    
    # Treasury
    print("[Treasury] Parsing XML volumes...")
    treas_glob = str(HOSTING_DIR / "Treasury Regulations" / "CFR-2025-title26-vol*.xml")
    treas_parser = TreasuryRegsXMLParser(treas_glob)
    treas_parsed = treas_parser.parse()
    treas_nums = [s.sectionId for s in treas_parsed]
    print(f"[Treasury] {len(treas_nums)} sections indexed")
    
    return irc_parser, treas_parser, irc_root, irc_nums, treas_nums, treas_parsed

def export():
    """Main export function."""
    irc_parser, treas_parser, irc_root, irc_nums, treas_nums, treas_parsed = load_data()
    
    print("\nBuilding static site...")
    
    # Clean up
    dist = "dist_pages"
    if os.path.exists(dist):
        shutil.rmtree(dist)
    os.makedirs(dist)
    
    # Export IRC pages
    print(f"\nExporting {len(irc_nums)} IRC section pages...")
    
    irc_parser.sections = []
    for num in irc_nums:
        elem = irc_parser._find_section_element(irc_root, num)
        if elem is not None:
            section = irc_parser._build_section_node(elem)
            section.hierarchy = irc_parser._section_hierarchy(section.identifier)
            irc_parser.sections.append(section)
    
    for i, num in enumerate(irc_nums):
        if i % 500 == 0:
            print(f"  {i}/{len(irc_nums)}")
        
        elem = irc_parser._find_section_element(irc_root, num)
        if elem is None:
            continue
        
        section = irc_parser._build_section_node(elem)
        
        # Simple text rendering
        text = extract_section_text(section)
        
        # HTML
        html = build_page(f"IRC § {num}", text, irc_nums, treas_nums)
        
        with open(f"{dist}/irc_{num}.html", 'w', encoding='utf-8') as f:
            f.write(html)
    
    # Export Treasury pages
    print(f"\nExporting {len(treas_nums)} Treasury regulation pages...")
    
    for i, reg in enumerate(treas_parsed):
        if i % 500 == 0:
            print(f"  {i}/{len(treas_nums)}")
        
        # Simple text rendering
        text = extract_regulation_text(reg)
        
        # HTML
        html = build_page(f"Treas. Reg. {reg.sectionId}", text, irc_nums, treas_nums)
        
        safe_name = reg.sectionId.replace('/', '_').replace('.', '_')
        with open(f"{dist}/treas_{safe_name}.html", 'w', encoding='utf-8') as f:
            f.write(html)
    
    # Index page
    print("\nCreating index page...")
    index = build_index_page(irc_nums, treas_nums)
    with open(f"{dist}/index.html", 'w', encoding='utf-8') as f:
        f.write(index)
    
    print(f"\nSuccess! Generated {len(irc_nums) + len(treas_nums) + 1} pages in {dist}/")

def extract_section_text(section):
    """Extract text from IRC section."""
    parts = []
    
    title = section.title if section.title else "(Untitled)"
    parts.append(f"<h2>{title}</h2>")
    
    if section.content:
        parts.append(f"<p>{section.content}</p>")
    
    if section.subsections:
        for sub in section.subsections:
            parts.append(extract_subsection_text(sub, depth=1))
    
    return "\n".join(parts)

def extract_subsection_text(subsection, depth=0):
    """Extract text from subsection."""
    parts = []
    
    indent = "&nbsp;" * (depth * 4)
    
    if subsection.title:
        parts.append(f"{indent}<strong>{subsection.title}</strong>")
    
    if subsection.content:
        parts.append(f"{indent}{subsection.content}")
    
    if subsection.subsections:
        for sub in subsection.subsections:
            parts.append(extract_subsection_text(sub, depth + 1))
    
    return "<div style='margin-left: 20px;'>" + "<br/>".join(parts) + "</div>"

def extract_regulation_text(reg):
    """Extract text from Treasury regulation."""
    parts = []
    
    title = reg.title if reg.title else "(Untitled)"
    parts.append(f"<h2>{title}</h2>")
    
    if reg.content:
        parts.append(f"<p>{reg.content}</p>")
    
    if reg.subsections:
        for sub in reg.subsections:
            parts.append(extract_regulation_subsection(sub, depth=1))
    
    return "\n".join(parts)

def extract_regulation_subsection(sub, depth=0):
    """Extract regulation subsection."""
    parts = []
    
    indent = "&nbsp;" * (depth * 4)
    
    if sub.title:
        parts.append(f"{indent}<strong>{sub.title}</strong>")
    
    if sub.content:
        parts.append(f"{indent}{sub.content}")
    
    if sub.subsections:
        for s in sub.subsections:
            parts.append(extract_regulation_subsection(s, depth + 1))
    
    return "<div style='margin-left: 20px;'>" + "<br/>".join(parts) + "</div>"

def build_page(title, content, irc_nums, treas_nums):
    """Build a complete HTML page."""
    
    irc_json = json.dumps([int(n) if str(n).isdigit() else n for n in irc_nums])
    treas_json = json.dumps(treas_nums)
    
    search_script = f"""<script>
document.getElementById('search').addEventListener('keypress', function(e) {{
    if (e.key !== 'Enter') return;
    let query = this.value.trim().toLowerCase();
    if (!query) return;
    
    const ircSections = {irc_json};
    const treasSections = {treas_json};
    
    // Try IRC
    let ircNum = parseInt(query.replace(/[a-z]$/i, ''));
    if (!isNaN(ircNum) && ircSections.includes(ircNum)) {{
        window.location.href = 'irc_' + ircNum + '.html';
        return;
    }}
    
    // Try Treasury
    if (treasSections.includes(query)) {{
        let safe = query.replace(/\\//g, '_').replace(/\\./g, '_');
        window.location.href = 'treas_' + safe + '.html';
        return;
    }}
    
    alert('Not found: ' + query);
}});
</script>"""
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .nav {{ margin-bottom: 20px; }}
        .nav a {{ color: #0066cc; text-decoration: none; font-weight: bold; }}
        .nav a:hover {{ text-decoration: underline; }}
        .search {{ margin-bottom: 20px; }}
        .search input {{ width: 100%; padding: 12px; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
        .content {{ background: white; padding: 30px; border-radius: 4px; line-height: 1.8; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    </style>
</head>
<body>
    <div class="nav">
        <a href="index.html">← Home</a> | {title}
    </div>
    
    <div class="search">
        <input type="text" id="search" placeholder="Search (e.g., 721 or 1.501-3)">
    </div>
    
    <div class="content">
        {content}
    </div>
    
    {search_script}
</body>
</html>"""

def build_index_page(irc_nums, treas_nums):
    """Build index page."""
    
    irc_list = "\n".join([f'        <li><a href="irc_{n}.html">§ {n}</a></li>' for n in irc_nums[:100]])
    treas_list = "\n".join([f'        <li><a href="treas_{s.replace("/", "_").replace(".", "_")}.html">Treas. Reg. {s}</a></li>' for s in treas_nums[:100]])
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Tax Authority Reference</title>
    <style>
        body {{ font-family: Georgia, serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        h1 {{ color: #003da5; }}
        .section {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        h2 {{ color: #333; margin-top: 0; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ padding: 5px 0; }}
        a {{ color: #0066cc; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .search {{ margin-bottom: 20px; }}
        .search input {{ width: 100%; padding: 12px; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
    </style>
</head>
<body>
    <h1>Tax Authority Reference</h1>
    
    <div class="search">
        <input type="text" id="search" placeholder="Quick search (e.g., 721 or 1.501-3)" autofocus>
    </div>
    
    <div class="section">
        <h2>Internal Revenue Code (IRC)</h2>
        <p>Total sections: {len(irc_nums)}</p>
        <ul>
{irc_list}
            <li><a href="#"><strong>View all {len(irc_nums)} sections...</strong></a></li>
        </ul>
    </div>
    
    <div class="section">
        <h2>Treasury Regulations (26 CFR)</h2>
        <p>Total sections: {len(treas_nums)}</p>
        <ul>
{treas_list}
            <li><a href="#"><strong>View all {len(treas_nums)} sections...</strong></a></li>
        </ul>
    </div>
    
    <script>
    document.getElementById('search').addEventListener('keypress', function(e) {{
        if (e.key === 'Enter') {{
            let query = this.value.trim().toLowerCase();
            if (!query) return;
            // Just trigger search on any page - basic navigation
            alert('Search: ' + query + ' - Use the search on any page');
        }}
    }});
    </script>
</body>
</html>"""

if __name__ == '__main__':
    export()
