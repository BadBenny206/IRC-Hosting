"""
IRC Hosting 2 — on-demand dynamic server.
Loads IRC and Treasury XML at startup; renders sections on request.
Port 8080.  Run via start.bat or:  py -3.14 server.py
"""

import sys
import os
import json
import html as html_lib
import re
import webbrowser
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Bootstrap: Load parsers from IRC Hosting, but use IRC Hosting 2 as base dir
# ---------------------------------------------------------------------------
HOSTING_DIR = Path(__file__).resolve().parent  # IRC Hosting 2 directory
sys.path.insert(0, str(HOSTING_DIR))
os.chdir(str(HOSTING_DIR))

from IRC_Parser_XML import IRCXMLParser  # noqa: E402
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser, RegulationNode  # noqa: E402

PORT = 8080

# ---------------------------------------------------------------------------
# Global data (populated by load_data())
# ---------------------------------------------------------------------------
irc_parser: IRCXMLParser = None
irc_root = None
irc_nums: list = []          # ordered IRC section numbers, e.g. ["1","11","12",...]
irc_all_sections: list = []  # List of all SectionNode objects for search script

treas_parser: TreasuryRegsXMLParser = None
treas_ordered: list = []     # List[RegulationNode] in order
treas_nums: list = []        # [sectionNumber, ...] e.g. ["1.1-1","1.61-1",...]
treas_by_anchor: dict = {}   # anchor_id (e.g. "sec-1-704-1") -> RegulationNode
treas_set: set = set()       # fast lookup by sectionNumber
_index_html_cache: str = ""  # dynamically built index


# ---------------------------------------------------------------------------
# Dynamic index builder (uses already-loaded globals)
# ---------------------------------------------------------------------------
def _build_dynamic_index() -> str:
    """Build the unified IRC + Treasury index page from in-memory loaded data."""
    import urllib.parse

    _ALLOWED_PARTS = {"1","20","25","31","35","40","41","44","48","49",
                      "53","54","55","56","57","58","60","301"}

    def _related_irc(section_id: str):
        s = re.sub(r"\s+", "", section_id.replace("§", "")).strip()
        m = re.match(r"^(\d+)\.(\d+[A-Za-z]*(?:\([^)]+\))*)-(\d+[A-Za-z]*)", s)
        if not m or m.group(1) not in _ALLOWED_PARTS:
            return None
        tm = re.match(r"(\d+[A-Za-z]*)", m.group(2))
        return tm.group(1) if tm else None

    # Group treasury sections by related IRC section number
    treas_by_irc: dict = {}
    for sec in treas_ordered:
        irc_num = _related_irc(sec.sectionId)
        if irc_num:
            treas_by_irc.setdefault(irc_num, []).append(sec)

    def _reg_links(section_number: str) -> str:
        regs = treas_by_irc.get(section_number, [])
        if not regs:
            return ""
        parts = ['<div class="index-reg-list"><div class="index-reg-prefix">Treasury Regulations</div>']
        for reg in regs:
            parts.append(
                f'<a class="index-reg-link" href="/treas.html?s={urllib.parse.quote(reg.sectionNumber)}">'
                f'{html_lib.escape(reg.sectionId)}. {html_lib.escape(reg.title)}</a>'
            )
        parts.append('</div>')
        return "".join(parts)

    # Collect IRC sections with hierarchy info
    irc_data = []
    for section_elem in irc_root.findall(".//uslm:section", irc_parser.ns):
        identifier = section_elem.get("identifier", "")
        m = re.search(r"/s(\d+[A-Za-z]*)$", identifier)
        if not m:
            continue
        heading_elem = section_elem.find("uslm:heading", irc_parser.ns)
        snum = m.group(1)
        title = irc_parser._extract_heading_text(heading_elem)
        irc_data.append({
            "sectionNumber": snum,
            "sectionId": f"§ {snum}",
            "title": title,
            "identifier": identifier,
            "hierarchy": irc_parser._section_hierarchy(identifier),
        })

    def _irc_sort(s):
        num = re.sub(r"^\[\s*", "", s["sectionNumber"]).strip()
        m = re.match(r"^(\d+)(.*)", num)
        return (int(m.group(1)), m.group(2)) if m else (0, num)

    irc_data.sort(key=_irc_sort)

    # Build TOC HTML
    toc_parts: list = []
    cur_sub = cur_ch = cur_sch = ""
    list_open = False

    for sec in irc_data:
        hier = sec["hierarchy"]
        subtitle   = next((e for e in hier if e["type"] == "subtitle"),    None)
        chapter    = next((e for e in hier if e["type"] == "chapter"),     None)
        subchapter = next((e for e in hier if e["type"] == "subchapter"),  None)

        sid  = subtitle["identifier"]   if subtitle   else ""
        cid  = chapter["identifier"]    if chapter    else ""
        scid = subchapter["identifier"] if subchapter else ""

        if sid != cur_sub:
            if list_open:
                toc_parts.append("            </ul>")
                list_open = False
            cur_sub = sid
            cur_ch = cur_sch = ""
            if subtitle:
                toc_parts.append(f'            <h2 class="index-subtitle">{html_lib.escape(subtitle["display"])}</h2>')

        if cid != cur_ch:
            if list_open:
                toc_parts.append("            </ul>")
                list_open = False
            cur_ch = cid
            cur_sch = ""
            if chapter:
                toc_parts.append(f'            <h3 class="index-chapter">{html_lib.escape(chapter["display"])}</h3>')

        if scid != cur_sch:
            if list_open:
                toc_parts.append("            </ul>")
                list_open = False
            cur_sch = scid
            if subchapter:
                toc_parts.append(f'            <h4 class="index-subchapter">{html_lib.escape(subchapter["display"])}</h4>')

        if not list_open:
            toc_parts.append('            <ul class="index-list">')
            list_open = True

        regs_html = _reg_links(sec["sectionNumber"])
        toc_parts.append(
            f'                <li class="index-list-item" style="list-style:none">'
            f'<a class="index-link" href="/irc.html?s={urllib.parse.quote(sec["sectionNumber"])}">'
            f'{html_lib.escape(sec["sectionId"])}. {html_lib.escape(sec["title"])}'
            f'</a>{regs_html}</li>'
        )

    if list_open:
        toc_parts.append("            </ul>")

    toc_html = "\n".join(toc_parts)
    search_js = _search_script(irc_nums, treas_nums)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internal Revenue Code</title>
    <style>
        :root {{
            --kpmg-blue: #003DA5;
            --ink: #243245;
            --muted: #68768a;
            --paper: #ffffff;
            --line: rgba(0, 61, 165, 0.12);
            --shadow: 0 12px 28px rgba(0, 34, 85, 0.08);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0; padding: 32px;
            font-family: Arial, sans-serif;
            color: var(--ink);
            background: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
        }}
        .index-shell {{ max-width: 1320px; margin: 0 auto; }}
        .index-hero {{
            background: rgba(255,255,255,0.88); border: 1px solid var(--line);
            border-radius: 22px; box-shadow: var(--shadow);
            padding: 28px 30px; margin-bottom: 24px;
        }}
        .index-eyebrow {{
            font-size: 12px; font-weight: bold; letter-spacing: 0.08em;
            text-transform: uppercase; color: var(--muted); margin-bottom: 8px;
        }}
        .index-hero h1 {{ margin: 0; color: var(--kpmg-blue); font-size: 34px; }}
        .index-toolbar {{
            display: flex; flex-wrap: wrap; gap: 12px;
            align-items: center; margin-top: 20px;
        }}
        .section-search {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .section-search-input {{
            min-width: 220px; padding: 12px 14px; border-radius: 12px;
            border: 1px solid rgba(0,61,165,0.22); font: inherit;
        }}
        .section-search-button {{
            padding: 12px 16px; border: 0; border-radius: 12px;
            background: var(--kpmg-blue); color: #fff; font: inherit;
            font-weight: bold; cursor: pointer;
        }}
        .section-search-hint {{ font-size: 13px; color: var(--muted); }}
        .search-error {{ margin-top: 12px; font-size: 13px; color: #b42318; }}
        .index-list-shell {{
            background: rgba(255,255,255,0.92); border: 1px solid var(--line);
            border-radius: 22px; box-shadow: var(--shadow); padding: 24px 30px;
        }}
        .index-list-title {{ margin: 0 0 18px 0; color: var(--kpmg-blue); font-size: 22px; }}
        .index-subtitle {{
            margin: 26px 0 6px 0; color: var(--kpmg-blue); font-size: 18px;
            font-weight: bold; border-bottom: 2px solid var(--line); padding-bottom: 6px;
        }}
        .index-chapter {{ margin: 16px 0 4px 14px; color: var(--ink); font-size: 15px; font-weight: bold; }}
        .index-subchapter {{
            margin: 10px 0 4px 28px; color: var(--muted); font-size: 12px;
            font-weight: bold; text-transform: uppercase; letter-spacing: 0.06em;
        }}
        .index-list {{ margin: 4px 0 10px 0; padding-left: 56px; list-style: none; }}
        .index-list-item + .index-list-item {{ margin-top: 8px; }}
        .index-link {{ color: var(--kpmg-blue); text-decoration: none; font-size: 16px; line-height: 1.5; }}
        .index-link:hover {{ text-decoration: underline; }}
        .index-reg-list {{ margin-top: 6px; margin-left: 28px; display: flex; flex-direction: column; gap: 6px; }}
        .index-reg-link {{ color: var(--ink); text-decoration: none; font-size: 14px; line-height: 1.45; }}
        .index-reg-link:hover {{ color: var(--kpmg-blue); text-decoration: underline; }}
        .index-reg-prefix {{ color: var(--muted); font-size: 12px; font-weight: bold; letter-spacing: 0.04em; text-transform: uppercase; }}
    </style>
</head>
<body>
    <div class="index-shell">
        <section class="index-hero">
            <div class="index-eyebrow">Internal Revenue Code</div>
            <h1>US Code Title 26</h1>
            <div class="index-toolbar">
                <form class="section-search" data-section-search>
                    <input class="section-search-input" type="text" name="section"
                        placeholder="Go to section or regulation number">
                    <button class="section-search-button" type="submit">Go</button>
                </form>
                <div class="section-search-hint">Type an IRC section such as 1502 or a Treasury regulation such as 1.1502-1.</div>
            </div>
            <div class="search-error" data-search-error hidden></div>
        </section>
        <section class="index-list-shell">
            <h2 class="index-list-title">Browse Sections</h2>
{toc_html}
        </section>
    </div>
    <script>
{search_js}
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Startup loader
# ---------------------------------------------------------------------------
def load_data():
    global irc_parser, irc_root, irc_nums
    global treas_parser, treas_ordered, treas_nums, treas_by_anchor, treas_set

    # Data directory (IRC Hosting 2 - where XML files live)
    data_dir = HOSTING_DIR
    
    irc_xml = data_dir / "IRC" / "usc26.xml"
    print(f"[IRC] Loading {irc_xml.name}...")
    irc_parser = IRCXMLParser(str(irc_xml))
    irc_root = irc_parser.load_xml()
    irc_parser._heading_map = irc_parser._build_heading_map(irc_root)
    irc_parser._section_parent_map = irc_parser._build_section_parent_map(irc_root)
    irc_parser._section_elem_map = irc_parser._build_section_element_map(irc_root)
    irc_nums = irc_parser.discover_all_section_numbers(irc_root)
    print(f"[IRC] {len(irc_nums)} sections indexed")

    # Treasury regulations - use parent data directory for XML files
    print(f"[Treasury] Parsing XML volumes (this takes ~30s)...")
    treas_glob_pattern = str(data_dir / "Treasury Regulations" / "CFR-2025-title26-vol*.xml")
    treas_parser = TreasuryRegsXMLParser(treas_glob_pattern)
    treas_ordered = treas_parser.parse()
    treas_parser._rendered_section_numbers = [s.sectionNumber for s in treas_ordered]
    treas_nums = treas_parser._rendered_section_numbers
    treas_set = set(treas_nums)
    treas_by_anchor = {s.get_anchor_id(): s for s in treas_ordered}
    print(f"[Treasury] {len(treas_nums)} sections indexed")

    # Write treasury JSON so IRC parser's _load_treasury_section_numbers() finds it
    treasury_json_path = HOSTING_DIR / "output" / "treasury_regs" / "treasury_regs.json"
    treasury_json_path.parent.mkdir(parents=True, exist_ok=True)
    sections_data = [{"sectionId": s.sectionId} for s in treas_ordered]
    with open(treasury_json_path, "w", encoding="utf-8") as f:
        json.dump({"sections": sections_data}, f)
    print(f"[Treasury] Wrote section index JSON")

    # Build index HTML dynamically from loaded data
    global _index_html_cache
    print(f"[Index] Building dynamic index...")
    _index_html_cache = _build_dynamic_index()
    print(f"[Index] Built ({len(_index_html_cache):,} bytes)")

    # Pre-build all IRC section nodes for search script availability
    global irc_all_sections
    print(f"[IRC] Pre-building all section nodes for search...")
    irc_all_sections = []
    for num in irc_nums:
        elem = irc_parser._find_section_element(irc_root, num)
        if elem is not None:
            section = irc_parser._build_section_node(elem)
            section.hierarchy = irc_parser._section_hierarchy(section.identifier)
            irc_all_sections.append(section)
    print(f"[IRC] Pre-built {len(irc_all_sections)} section nodes")

    print(f"\nReady!  Open http://localhost:{PORT}/\n")


# ---------------------------------------------------------------------------
# Shared CSS (used by both IRC and Treasury section pages)
# ---------------------------------------------------------------------------
SHARED_CSS = """
    <style>
        :root {
            --kpmg-blue: #003DA5;
            --kpmg-blue-dark: #002d77;
            --ink: #333;
            --muted: #68768a;
            --line: #d8e1ee;
            --paper: #ffffff;
            --shadow: 0 12px 28px rgba(0, 34, 85, 0.08);
            --topbar-offset: 16px;
            --sticky-gap: 20px;
            --content-offset: 156px;
        }
        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        body {
            font-family: Arial, sans-serif; line-height: 1.6; margin: 0;
            padding: 32px; color: var(--ink);
            background: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
        }
        body::before {
            content: ''; position: fixed; top: 0; left: 0; right: 0; height: 120px;
            background: #eef4fb; z-index: 999; pointer-events: none;
        }
        .reader-shell { max-width: 1320px; margin: 0 auto; }
        .reader-topbar {
            display: flex; justify-content: space-between; align-items: center;
            gap: 24px; padding: 18px 22px; position: fixed; top: var(--topbar-offset);
            left: 50%; transform: translateX(-50%);
            width: min(calc(100vw - 64px), 1320px); z-index: 1000;
            background: rgba(255,255,255,0.97);
            border: 1px solid rgba(0,61,165,0.12); border-radius: 18px;
            box-shadow: var(--shadow);
        }
        .reader-eyebrow {
            font-size: 12px; font-weight: bold; letter-spacing: 0.08em;
            text-transform: uppercase; color: var(--muted); margin-bottom: 6px;
        }
        .reader-heading { font-size: 28px; font-weight: bold; color: var(--kpmg-blue); margin: 0; }
        .reader-subheading { margin: 6px 0 0 0; font-size: 13px; color: var(--muted); }
        .section-nav {
            display: flex; flex-direction: column; align-items: flex-end;
            gap: 12px; flex: 0 0 320px;
        }
        .section-nav-chip {
            display: inline-flex; align-items: center; gap: 8px; min-height: 40px;
            padding: 10px 14px; border-radius: 999px;
            border: 1px solid rgba(0,61,165,0.18); background: var(--paper);
            color: var(--muted); font-size: 12px; font-weight: bold;
            text-transform: uppercase; letter-spacing: 0.04em; text-decoration: none;
        }
        .section-nav-chip:hover { border-color: var(--kpmg-blue); color: var(--kpmg-blue); }
        .section-nav-home { width: 100%; display: flex; justify-content: flex-end; }
        .section-search {
            display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
            justify-content: flex-end; width: 100%;
        }
        .section-search-input {
            flex: 1 1 220px; min-width: 0; padding: 10px 12px; border-radius: 12px;
            border: 1px solid rgba(0,61,165,0.22); font: inherit;
        }
        .section-search-button {
            padding: 10px 14px; border: 0; border-radius: 12px;
            background: var(--kpmg-blue); color: #fff; font: inherit;
            font-weight: bold; cursor: pointer;
        }
        .search-error { width: 100%; font-size: 13px; color: #b42318; }
        .reader-layout {
            display: grid; grid-template-columns: 280px minmax(0,1fr);
            gap: 28px; align-items: start;
        }
        .reader-sidebar {
            position: sticky; top: var(--content-offset);
            height: calc(100vh - var(--content-offset) - 40px);
            display: flex; flex-direction: column;
        }
        .sidebar-card {
            background: var(--paper); border: 1px solid rgba(0,61,165,0.12);
            border-radius: 18px; box-shadow: var(--shadow); overflow: hidden;
            display: flex; flex-direction: column; min-height: 0; flex: 1;
        }
        .sidebar-card-header {
            padding: 18px 18px 14px 18px;
            background: linear-gradient(180deg, rgba(0,61,165,0.08) 0%, rgba(0,61,165,0.02) 100%);
            border-bottom: 1px solid var(--line); flex-shrink: 0;
        }
        .sidebar-card-title {
            margin: 0; font-size: 13px; font-weight: bold; letter-spacing: 0.08em;
            text-transform: uppercase; color: var(--muted);
        }
        .sidebar-card-body { padding: 8px; flex: 1 1 0; min-height: 0; overflow-y: auto; }
        .toc-link {
            display: grid; grid-template-columns: 56px minmax(0,1fr);
            gap: 10px; align-items: start; padding: 10px 12px; border-radius: 12px;
            color: var(--ink); text-decoration: none;
            transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
        }
        .toc-link.treasury { display: block; }
        .toc-link:hover { background: rgba(0,61,165,0.06); color: var(--kpmg-blue); }
        .toc-link.is-active {
            background: rgba(0,61,165,0.1); color: var(--kpmg-blue-dark);
            transform: translateX(2px);
        }
        .toc-marker { font-weight: bold; color: var(--kpmg-blue); }
        .toc-text { font-size: 13px; line-height: 1.45; }
        .toc-link.treasury .toc-text { color: var(--kpmg-blue); font-weight: bold; }
        .sidebar-card-footer { padding: 12px 18px 16px 18px; border-top: 1px solid var(--line); flex-shrink: 0; }
        .back-to-top { color: var(--kpmg-blue); text-decoration: none; font-size: 13px; font-weight: bold; }
        .reader-main { min-width: 0; }
        .section-card {
            background: var(--paper); border: 1px solid rgba(0,61,165,0.12);
            border-radius: 22px; box-shadow: var(--shadow); padding: 30px 34px 36px 34px;
        }
        .section-title {
            font-size: 32px; font-weight: bold; color: var(--kpmg-blue);
            border-bottom: 4px solid var(--kpmg-blue); padding-bottom: 12px; margin-bottom: 14px;
        }
        .subsection-wrapper {
            margin-bottom: 8px; scroll-margin-top: var(--content-offset);
            position: relative; z-index: 1;
        }
        .subsection-heading {
            color: var(--kpmg-blue); font-weight: bold; margin-top: 16px;
            margin-bottom: 8px; padding-left: 14px;
            border-left: 4px solid var(--kpmg-blue); position: relative; z-index: 1;
        }
        .subsection-heading.level-1 { font-size: 16px; }
        .subsection-heading.level-2 { font-size: 15px; border-left-width: 3px; }
        .subsection-heading.level-3 { font-size: 14px; border-left-width: 2px; }
        .subsection-heading.level-4,
        .subsection-heading.level-5,
        .subsection-heading.level-6 { font-size: 13px; border-left-width: 2px; }
        .subsection-content {
            line-height: 1.8; white-space: pre-wrap; word-wrap: break-word;
            font-size: 13px; margin-bottom: 10px;
        }
        .table-wrapper {
            margin: 14px 0 18px 0; border: 2px solid var(--kpmg-blue);
            border-radius: 14px; overflow: hidden;
        }
        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { background: var(--kpmg-blue); color: #fff; padding: 10px 14px; text-align: left; }
        td { padding: 10px 14px; border-top: 1px solid var(--line); }
        tr:nth-child(even) td { background: rgba(0,61,165,0.03); }
        @media (max-width: 980px) {
            :root { --topbar-offset: 12px; }
            body { padding: 18px; }
            .reader-topbar { flex-direction: column; align-items: stretch; }
            .section-nav { flex: 1 1 auto; align-items: stretch; }
            .section-nav-home { justify-content: flex-start; }
            .section-search { justify-content: flex-start; }
            .reader-layout { grid-template-columns: 1fr; }
            .reader-sidebar { position: static; order: -1; }
            .section-card { padding: 22px 20px 28px 20px; }
        }
    </style>
"""

SHARED_JS = """
        const root = document.documentElement;
        const topbar = document.querySelector('.reader-topbar');
        const tocLinks = Array.from(document.querySelectorAll('.toc-link'));
        const headingElems = tocLinks
            .map(link => document.getElementById(link.getAttribute('data-target')))
            .filter(Boolean);

        const syncOffsets = () => {
            if (!topbar) return;
            const stickyGap = parseFloat(getComputedStyle(root).getPropertyValue('--sticky-gap')) || 20;
            const contentOffset = Math.ceil(topbar.getBoundingClientRect().bottom + stickyGap);
            root.style.setProperty('--content-offset', `${contentOffset}px`);
            document.body.style.paddingTop = `${contentOffset}px`;
        };
        syncOffsets();
        window.addEventListener('load', syncOffsets);
        if ('ResizeObserver' in window && topbar) {
            new ResizeObserver(syncOffsets).observe(topbar);
        } else {
            window.addEventListener('resize', syncOffsets);
        }
        if ('IntersectionObserver' in window && tocLinks.length > 0 && headingElems.length > 0) {
            const linkById = new Map(tocLinks.map(l => [l.getAttribute('data-target'), l]));
            const observer = new IntersectionObserver(entries => {
                const visible = entries
                    .filter(e => e.isIntersecting)
                    .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
                if (!visible) return;
                tocLinks.forEach(l => l.classList.remove('is-active'));
                const active = linkById.get(visible.target.id);
                if (active) active.classList.add('is-active');
            }, { rootMargin: '-20% 0px -60% 0px', threshold: [0.1, 0.35, 0.6] });
            headingElems.forEach(el => observer.observe(el));
            tocLinks[0]?.classList.add('is-active');
        }
"""


def _search_script(irc_numbers, treas_numbers):
    """Build unified search JS — navigates to /irc.html?s=N or /treas.html?s=ID."""
    return f"""
        const availableIrcSections = {json.dumps(irc_numbers)};
        const availableTreasurySections = {json.dumps(treas_numbers)};
        const ircSectionMap = new Map(availableIrcSections.map(v => [String(v).trim().toLowerCase(), v]));
        const treasurySectionMap = new Map();
        const treasurySuffixMap = new Map();
        const searchForm = document.querySelector('[data-section-search]');
        const searchError = document.querySelector('[data-search-error]');

        const normalizeIrc = v => v.replace(/[^0-9a-zA-Z]/g, '').trim().toLowerCase();
        const normalizeTreas = v => v
            .replace(/26\\s*cfr/ig, '').replace(/treasury\\s+regulations?/ig, '')
            .replace(/regulations?/ig, '').replace(/§/g, '').replace(/[–—]/g, '-')
            .replace(/\\s+/g, '').trim().toLowerCase();

        availableTreasurySections.forEach(v => {{
            const norm = normalizeTreas(String(v));
            treasurySectionMap.set(norm, v);
            const suffix = norm.replace(/^\\d+\\./, '');
            if (suffix && suffix !== norm) {{
                if (!treasurySuffixMap.has(suffix)) treasurySuffixMap.set(suffix, v);
                else if (treasurySuffixMap.get(suffix) !== v) treasurySuffixMap.set(suffix, null);
            }}
        }});

        const showErr = msg => {{ if (searchError) {{ searchError.hidden = false; searchError.textContent = msg; }} }};
        const clearErr = () => {{ if (searchError) {{ searchError.hidden = true; searchError.textContent = ''; }} }};

        searchForm?.querySelector('[name="section"]')?.addEventListener('focus', e => {{
            e.preventDefault(); window.scrollTo({{top: window.scrollY, behavior: 'auto'}});
        }});

        searchForm?.addEventListener('submit', e => {{
            e.preventDefault();
            const raw = String(new FormData(searchForm).get('section') || '').trim();
            if (!raw) {{ showErr('Enter an IRC section number or Treasury regulation number.'); return; }}
            const normI = normalizeIrc(raw);
            const normT = normalizeTreas(raw);
            const looksLikeTreas = normT.includes('.') || normT.includes('-');
            let treasMatch = treasurySectionMap.get(normT) || null;
            if (!treasMatch && looksLikeTreas && !normT.includes('.')) {{
                treasMatch = treasurySuffixMap.get(normT) || null;
                if (treasMatch === null && treasurySuffixMap.has(normT)) {{
                    showErr(`More than one Treasury regulation matches ${{raw}}. Enter the full number.`);
                    return;
                }}
            }}
            if (treasMatch) {{ clearErr(); window.location.href = `/treas.html?s=${{encodeURIComponent(treasMatch)}}`; return; }}
            const ircMatch = ircSectionMap.get(normI);
            if (ircMatch) {{ clearErr(); window.location.href = `/irc.html?s=${{ircMatch}}`; return; }}
            showErr(`No IRC section or Treasury regulation matched ${{raw}}.`);
        }});
"""


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _treas_anchor_id(sid: str) -> str:
    """Compute the HTML anchor id for a Treasury subsection sectionId."""
    if "(" in sid:
        pi = sid.index("(")
        a = sid[pi:].replace(")", "").replace("(", "-").strip("-").lower().replace(" ", "")
        if not a:
            a = re.sub(r"\s+", "", sid.replace("§", ""))
            a = a.replace("(", "-").replace(")", "-").replace(".", "-").replace("--", "-").strip("-").lower()
        return a
    a = re.sub(r"\s+", "", sid.replace("§", ""))
    return a.replace("(", "-").replace(")", "-").replace(".", "-").replace("--", "-").strip("-").lower()


def _treas_marker_kind(display_id: str) -> str:
    match = re.fullmatch(r"\(([^)]+)\)", (display_id or "").strip())
    if not match:
        return "other"

    token = match.group(1).strip()
    if re.fullmatch(r"\d+", token):
        return "digit"
    if re.fullmatch(r"[A-Z]+", token):
        return "alpha-upper"
    if re.fullmatch(r"[a-z]+", token):
        roman_lower = set("ivxlcdm")
        if len(token) > 1 and all(char in roman_lower for char in token):
            return "roman-lower"
        return "alpha-lower"
    return "other"


def _treas_sidebar_nodes(section: RegulationNode) -> list[RegulationNode]:
    roots = [sub for sub in section.subsections if sub.level == 1]
    if not roots:
        return []

    preferred_order = ["alpha-lower", "digit", "alpha-upper", "roman-lower", "roman-upper", "other"]
    kinds_present = {_treas_marker_kind(sub.displayId) for sub in roots}
    preferred_kind = next((kind for kind in preferred_order if kind in kinds_present), None)
    if preferred_kind is None:
        return roots

    filtered = [sub for sub in roots if _treas_marker_kind(sub.displayId) == preferred_kind]
    return filtered or roots


def _render_treas_node_recursive(node: RegulationNode) -> str:
    """Recursively render a RegulationNode to HTML (matching existing Treasury output style)."""
    anchor_id = _treas_anchor_id(node.sectionId)
    heading_margin = max(0, node.indentation)
    content_margin = heading_margin + 24
    sid_escaped = html_lib.escape(html_lib.unescape(node.displayId) if node.displayId else "")
    content_escaped = html_lib.escape(html_lib.unescape(node.content) if node.content else "")

    lines = (
        '                    <div class="subsection-wrapper">\n'
        f'                        <div class="subsection-heading level-{node.level}" '
        f'id="{anchor_id}" style="margin-left: {heading_margin}px;">{sid_escaped}</div>\n'
        f'                        <div class="subsection-content level-{node.level}" '
        f'style="margin-left: {content_margin}px;">{content_escaped}</div>\n'
    )
    for child in node.subsections:
        lines += _render_treas_node_recursive(child)
    lines += "                    </div>\n"
    return lines


def build_treas_html(section: RegulationNode) -> str:
    """Build a complete Treasury section HTML page."""
    title = html_lib.escape(section.title)

    # TOC
    toc_items = []
    for sub in _treas_sidebar_nodes(section):
        sub_anchor = _treas_anchor_id(sub.sectionId)
        toc_label = sub.displayId
        if sub.title:
            toc_label = f"{toc_label} {sub.title}"
        toc_items.append(
            f'                <a class="toc-link treasury" href="#{sub_anchor}" data-target="{sub_anchor}">'
            f'<span class="toc-text">{html_lib.escape(toc_label)}</span></a>'
        )
    toc_html = "\n".join(toc_items) or (
        '                <div class="toc-text" style="padding:10px 12px;color:var(--muted)">Full section text</div>'
    )

    # Body
    body_parts = []
    paras = [p.strip() for p in section.content.split("\n\n") if p.strip()] if section.content else []
    subsection_roots_by_paragraph = {}

    def _register_subsection_paragraphs(node: RegulationNode, root: RegulationNode):
        match = re.match(r"^(p\d+)(?:\.\d+)?$", node.identifier)
        if match:
            subsection_roots_by_paragraph.setdefault(match.group(1), root)
        for child in node.subsections:
            _register_subsection_paragraphs(child, root)

    for sub in section.subsections:
        _register_subsection_paragraphs(sub, sub)

    rendered_ids = set()
    for i, para in enumerate(paras, 1):
        key = f"p{i}"
        para_root = subsection_roots_by_paragraph.get(key)
        if para_root:
            if para_root.identifier not in rendered_ids:
                body_parts.append(_render_treas_node_recursive(para_root))
                rendered_ids.add(para_root.identifier)
        else:
            body_parts.append(
                f'                    <div class="subsection-content">{html_lib.escape(para)}</div>\n'
            )

    # Render any subsections not covered by paragraphs
    for sub in section.subsections:
        if sub.identifier not in rendered_ids:
            body_parts.append(_render_treas_node_recursive(sub))

    # Metadata footer
    meta = ['                    <div class="subsection-wrapper">',
            '                        <div class="subsection-heading level-1" style="margin-left:0">Source details</div>',
            '                        <div class="subsection-content" style="margin-left:24px">Source: Treasury Regulations (26 CFR)</div>']
    if section.citation:
        meta.append(f'                        <div class="subsection-content" style="margin-left:24px">Citation: {html_lib.escape(section.citation)}</div>')
    if section.effective_date:
        meta.append(f'                        <div class="subsection-content" style="margin-left:24px">Effective date: {html_lib.escape(section.effective_date)}</div>')
    if section.volume:
        meta.append(f'                        <div class="subsection-content" style="margin-left:24px">Volume: {html_lib.escape(section.volume)}</div>')
    meta.append('                    </div>')
    body_parts.append("\n".join(meta))

    body_html = "".join(body_parts)
    search_js = _search_script(irc_nums, treas_nums)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_lib.escape(section.sectionId)} - {title}</title>
{SHARED_CSS}
</head>
<body id="top">
    <div class="reader-shell">
        <div class="reader-topbar">
            <div>
                <div class="reader-eyebrow">Treasury Regulations</div>
                <h1 class="reader-heading">{html_lib.escape(section.sectionId)}. {title}</h1>
                <p class="reader-subheading">26 CFR</p>
            </div>
            <div class="section-nav">
                <div class="section-nav-home">
                    <a class="section-nav-chip" href="/">Home</a>
                </div>
                <form class="section-search" data-section-search>
                    <input class="section-search-input" type="text" name="section"
                        placeholder="Go to section or regulation number">
                    <button class="section-search-button" type="submit">Go</button>
                    <div class="search-error" data-search-error hidden></div>
                </form>
            </div>
        </div>

        <div class="reader-layout">
            <aside class="reader-sidebar" aria-label="On this page navigation">
                <div class="sidebar-card">
                    <div class="sidebar-card-header">
                        <p class="sidebar-card-title">On This Page</p>
                    </div>
                    <div class="sidebar-card-body">
{toc_html}
                    </div>
                    <div class="sidebar-card-footer">
                        <a class="back-to-top" href="#top">Back to top</a>
                    </div>
                </div>
            </aside>

            <main class="reader-main">
                <div class="section-card">
                    <div class="section-title">{html_lib.escape(section.sectionId)}. {title}</div>
{body_html}
                </div>
            </main>
        </div>
    </div>
    <script>
{SHARED_JS}
{search_js}
    </script>
</body>
</html>"""


def build_irc_html(section_num: str) -> str | None:
    """Render an IRC section on-demand; returns HTML string or None if not found."""
    elem = irc_parser._find_section_element(irc_root, section_num)
    if elem is None:
        return None
    section = irc_parser._build_section_node(elem)
    section.hierarchy = irc_parser._section_hierarchy(section.identifier)
    # Use the parser's built-in renderer (it computes its own TOC + search script)
    # Populate sections list with ALL IRC sections so search script has access to them
    irc_parser.sections = irc_all_sections
    return irc_parser._build_html(section)


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------
def build_index_html() -> str:
    """Return the static index.html from IRC Hosting (identical design)."""
    return _index_html_cache


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: suppress default logging
        print(f"  {self.address_string()} {fmt % args}")

    def send_html(self, content: str, status: int = 200):
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_404(self, msg: str = "Not found"):
        self.send_html(f"<h1>404 — {html_lib.escape(msg)}</h1>", 404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        # Index
        if path in ("/", "/index.html"):
            self.send_html(build_index_html())
            return

        # IRC section  /irc.html?s=351
        if path == "/irc.html":
            s = (qs.get("s") or [""])[0].strip()
            if not s:
                self.send_html("<h1>Usage: /irc.html?s=351</h1>", 400)
                return
            html = build_irc_html(s)
            if html is None:
                self.send_404(f"IRC § {s} not found")
            else:
                self.send_html(html)
            return

        # Treasury section  /treas.html?s=1.704-1
        if path == "/treas.html":
            s = (qs.get("s") or [""])[0].strip()
            if not s:
                self.send_html("<h1>Usage: /treas.html?s=1.704-1</h1>", 400)
                return
            # Look up by sectionNumber
            if s not in treas_set:
                # Try normalized lookup
                found = None
                for num in treas_nums:
                    if num.lower() == s.lower():
                        found = num
                        break
                if found:
                    s = found
                else:
                    self.send_404(f"Treasury § {s} not found")
                    return
            section = next((sec for sec in treas_ordered if sec.sectionNumber == s), None)
            if section is None:
                self.send_404(f"Treasury § {s} not found")
                return
            self.send_html(build_treas_html(section))
            return

        # Legacy anchor-style URLs (e.g. sec-1-704-1.html) — look up in treas_by_anchor
        m = re.match(r"^/?(sec-[a-z0-9-]+)\.html$", path)
        if m:
            anchor = m.group(1)
            # Try Treasury first (IRC anchor would be just sec-N)
            treas_sec = treas_by_anchor.get(anchor)
            if treas_sec:
                self.send_html(build_treas_html(treas_sec))
                return
            # Try IRC: strip "sec-" prefix to get section number
            num = anchor[4:]  # drop "sec-"
            html = build_irc_html(num)
            if html:
                self.send_html(html)
                return
            self.send_404(f"Section {anchor} not found")
            return

        self.send_404(f"{self.path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    load_data()
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/")
    # Open browser after a short delay
    def open_browser():
        import time
        time.sleep(0.5)
        webbrowser.open(f"http://localhost:{PORT}/")
    threading.Thread(target=open_browser, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
