#!/usr/bin/env python3
"""
Static HTML exporter — generates all IRC and Treasury regulation pages
using the parsers' rendering logic directly (no server.py import).
"""

import sys
import re
import json
import html as html_lib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from IRC_Parser_XML import IRCXMLParser
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser, RegulationNode

HOSTING_DIR = Path(__file__).parent
OUTPUT_DIR = HOSTING_DIR / "dist_pages"


# ---------------------------------------------------------------------------
# Shared CSS/JS (mirrored from server.py so we never import that module)
# ---------------------------------------------------------------------------

SHARED_CSS = """
    <style>
        :root {
            --kpmg-blue: #003DA5; --kpmg-blue-dark: #002d77; --ink: #333;
            --muted: #68768a; --line: #d8e1ee; --paper: #ffffff;
            --shadow: 0 12px 28px rgba(0,34,85,0.08);
            --topbar-offset: 16px; --sticky-gap: 20px; --content-offset: 156px;
        }
        * { box-sizing: border-box; }
        html { scroll-behavior: smooth; }
        body {
            font-family: Arial, sans-serif; line-height: 1.6; margin: 0; padding: 32px;
            color: var(--ink);
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
            border: 1px solid rgba(0,61,165,0.12); border-radius: 18px; box-shadow: var(--shadow);
        }
        .reader-eyebrow { font-size: 12px; font-weight: bold; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
        .reader-heading { font-size: 28px; font-weight: bold; color: var(--kpmg-blue); margin: 0; }
        .reader-subheading { margin: 6px 0 0 0; font-size: 13px; color: var(--muted); }
        .section-nav { display: flex; flex-direction: column; align-items: flex-end; gap: 12px; flex: 0 0 320px; }
        .section-nav-chip {
            display: inline-flex; align-items: center; gap: 8px; min-height: 40px; padding: 10px 14px;
            border-radius: 999px; border: 1px solid rgba(0,61,165,0.18); background: var(--paper);
            color: var(--muted); font-size: 12px; font-weight: bold; text-transform: uppercase;
            letter-spacing: 0.04em; text-decoration: none;
        }
        .section-nav-chip:hover { border-color: var(--kpmg-blue); color: var(--kpmg-blue); }
        .section-nav-home { width: 100%; display: flex; justify-content: flex-end; }
        .section-search { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: flex-end; width: 100%; }
        .section-search-input { flex: 1 1 220px; min-width: 0; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(0,61,165,0.22); font: inherit; }
        .section-search-button { padding: 10px 14px; border: 0; border-radius: 12px; background: var(--kpmg-blue); color: #fff; font: inherit; font-weight: bold; cursor: pointer; }
        .search-error { width: 100%; font-size: 13px; color: #b42318; }
        .reader-layout { display: grid; grid-template-columns: 280px minmax(0,1fr); gap: 28px; align-items: start; }
        .reader-sidebar { position: sticky; top: var(--content-offset); height: calc(100vh - var(--content-offset) - 40px); display: flex; flex-direction: column; }
        .sidebar-card { background: var(--paper); border: 1px solid rgba(0,61,165,0.12); border-radius: 18px; box-shadow: var(--shadow); overflow: hidden; display: flex; flex-direction: column; min-height: 0; flex: 1; }
        .sidebar-card-header { padding: 18px 18px 14px 18px; background: linear-gradient(180deg, rgba(0,61,165,0.08) 0%, rgba(0,61,165,0.02) 100%); border-bottom: 1px solid var(--line); flex-shrink: 0; }
        .sidebar-card-title { margin: 0; font-size: 13px; font-weight: bold; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
        .sidebar-card-body { padding: 8px; flex: 1 1 0; min-height: 0; overflow-y: auto; }
        .toc-link { display: grid; grid-template-columns: 56px minmax(0,1fr); gap: 10px; align-items: start; padding: 10px 12px; border-radius: 12px; color: var(--ink); text-decoration: none; transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease; }
        .toc-link.treasury { display: block; }
        .toc-link:hover { background: rgba(0,61,165,0.06); color: var(--kpmg-blue); }
        .toc-link.is-active { background: rgba(0,61,165,0.1); color: var(--kpmg-blue-dark); transform: translateX(2px); }
        .toc-marker { font-weight: bold; color: var(--kpmg-blue); }
        .toc-text { font-size: 13px; line-height: 1.45; }
        .toc-link.treasury .toc-text { color: var(--kpmg-blue); font-weight: bold; }
        .sidebar-card-footer { padding: 12px 18px 16px 18px; border-top: 1px solid var(--line); flex-shrink: 0; }
        .back-to-top { color: var(--kpmg-blue); text-decoration: none; font-size: 13px; font-weight: bold; }
        .reader-main { min-width: 0; }
        .section-card { background: var(--paper); border: 1px solid rgba(0,61,165,0.12); border-radius: 22px; box-shadow: var(--shadow); padding: 30px 34px 36px 34px; }
        .section-title { font-size: 32px; font-weight: bold; color: var(--kpmg-blue); border-bottom: 4px solid var(--kpmg-blue); padding-bottom: 12px; margin-bottom: 14px; }
        .subsection-wrapper { margin-bottom: 8px; scroll-margin-top: var(--content-offset); position: relative; z-index: 1; }
        .subsection-heading { color: var(--kpmg-blue); font-weight: bold; margin-top: 16px; margin-bottom: 8px; padding-left: 14px; border-left: 4px solid var(--kpmg-blue); position: relative; z-index: 1; }
        .subsection-heading.level-1 { font-size: 16px; }
        .subsection-heading.level-2 { font-size: 15px; border-left-width: 3px; }
        .subsection-heading.level-3 { font-size: 14px; border-left-width: 2px; }
        .subsection-heading.level-4, .subsection-heading.level-5, .subsection-heading.level-6 { font-size: 13px; border-left-width: 2px; }
        .subsection-content { line-height: 1.8; white-space: pre-wrap; word-wrap: break-word; font-size: 13px; margin-bottom: 10px; }
        .table-wrapper { margin: 14px 0 18px 0; border: 2px solid var(--kpmg-blue); border-radius: 14px; overflow: hidden; }
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
                const visible = entries.filter(e => e.isIntersecting)
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


def _static_search_script(irc_numbers, treas_numbers):
    """Search JS that navigates to static irc_N.html / treas_N.html files."""
    return f"""
        const availableIrcSections = {json.dumps(irc_numbers)};
        const availableTreasurySections = {json.dumps(treas_numbers)};
        const ircSectionMap = new Map(availableIrcSections.map(v => [String(v).trim().toLowerCase(), v]));
        const treasurySectionMap = new Map();
        const searchForm = document.querySelector('[data-section-search]');
        const searchError = document.querySelector('[data-search-error]');

        const normalizeIrc = v => v.replace(/[^0-9a-zA-Z]/g, '').trim().toLowerCase();
        const normalizeTreas = v => v
            .replace(/26\\s*cfr/ig, '').replace(/treasury\\s+regulations?/ig, '')
            .replace(/regulations?/ig, '').replace(/\u00a7/g, '').replace(/[\u2013\u2014]/g, '-')
            .replace(/\\s+/g, '').trim().toLowerCase();

        availableTreasurySections.forEach(v => {{
            treasurySectionMap.set(normalizeTreas(String(v)), v);
        }});

        const showErr = msg => {{ if (searchError) {{ searchError.hidden = false; searchError.textContent = msg; }} }};
        const clearErr = () => {{ if (searchError) {{ searchError.hidden = true; searchError.textContent = ''; }} }};

        searchForm?.addEventListener('submit', e => {{
            e.preventDefault();
            const raw = String(new FormData(searchForm).get('section') || '').trim();
            if (!raw) {{ showErr('Enter a section number or regulation number.'); return; }}
            const normT = normalizeTreas(raw);
            const looksLikeTreas = normT.includes('.') || normT.includes('-');
            if (looksLikeTreas) {{
                const treasMatch = treasurySectionMap.get(normT);
                if (treasMatch) {{
                    clearErr();
                    const safeId = String(treasMatch).replace(/\\/g, '_').replace(/\\./g, '_');
                    window.location.href = 'treas_' + safeId + '.html';
                    return;
                }}
            }}
            const normI = normalizeIrc(raw);
            const ircMatch = ircSectionMap.get(normI);
            if (ircMatch) {{
                clearErr();
                const safeNum = String(ircMatch).replace(/\\//g, '_').replace(/\\./g, '_');
                window.location.href = 'irc_' + safeNum + '.html';
                return;
            }}
            showErr('No IRC section or Treasury regulation matched ' + raw + '.');
        }});
"""


# ---------------------------------------------------------------------------
# Treasury rendering helpers (inlined from server.py)
# ---------------------------------------------------------------------------

def _treas_anchor_id(sid: str) -> str:
    if "(" in sid:
        pi = sid.index("(")
        a = sid[pi:].replace(")", "").replace("(", "-").strip("-").lower().replace(" ", "")
        if not a:
            a = re.sub(r"\s+", "", sid.replace("\u00a7", ""))
            a = a.replace("(", "-").replace(")", "-").replace(".", "-").replace("--", "-").strip("-").lower()
        return a
    a = re.sub(r"\s+", "", sid.replace("\u00a7", ""))
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
        if len(token) > 1 and all(c in roman_lower for c in token):
            return "roman-lower"
        return "alpha-lower"
    return "other"


def _treas_sidebar_nodes(section: RegulationNode) -> list:
    roots = [sub for sub in section.subsections if sub.level == 1]
    if not roots:
        return []
    preferred_order = ["alpha-lower", "digit", "alpha-upper", "roman-lower", "roman-upper", "other"]
    kinds_present = {_treas_marker_kind(sub.displayId) for sub in roots}
    preferred_kind = next((k for k in preferred_order if k in kinds_present), None)
    if preferred_kind is None:
        return roots
    filtered = [s for s in roots if _treas_marker_kind(s.displayId) == preferred_kind]
    return filtered or roots


def _render_treas_node(node: RegulationNode) -> str:
    anchor_id = _treas_anchor_id(node.sectionId)
    hm = max(0, node.indentation)
    cm = hm + 24
    sid = html_lib.escape(html_lib.unescape(node.displayId) if node.displayId else "")
    cnt = html_lib.escape(html_lib.unescape(node.content) if node.content else "")
    lines = (
        '                    <div class="subsection-wrapper">\n'
        f'                        <div class="subsection-heading level-{node.level}" '
        f'id="{anchor_id}" style="margin-left:{hm}px">{sid}</div>\n'
        f'                        <div class="subsection-content level-{node.level}" '
        f'style="margin-left:{cm}px">{cnt}</div>\n'
    )
    for child in node.subsections:
        lines += _render_treas_node(child)
    lines += "                    </div>\n"
    return lines


def _build_treas_html(section: RegulationNode, irc_nums: list, treas_nums: list) -> str:
    title = html_lib.escape(section.title or "")
    toc_items = []
    for sub in _treas_sidebar_nodes(section):
        anc = _treas_anchor_id(sub.sectionId)
        lbl = (f"{sub.displayId} {sub.title}").strip() if sub.title else sub.displayId or ""
        toc_items.append(
            f'                <a class="toc-link treasury" href="#{anc}" data-target="{anc}">'
            f'<span class="toc-text">{html_lib.escape(lbl)}</span></a>'
        )
    toc_html = "\n".join(toc_items) or (
        '                <div class="toc-text" style="padding:10px 12px;color:var(--muted)">Full section text</div>'
    )

    body_parts = []
    paras = [p.strip() for p in section.content.split("\n\n") if p.strip()] if section.content else []
    sub_root_map = {}

    def _reg(node, root):
        m = re.match(r"^(p\d+)(?:\.\d+)?$", node.identifier)
        if m:
            sub_root_map.setdefault(m.group(1), root)
        for child in node.subsections:
            _reg(child, root)

    for sub in section.subsections:
        _reg(sub, sub)

    rendered = set()
    for i, para in enumerate(paras, 1):
        pr = sub_root_map.get(f"p{i}")
        if pr:
            if pr.identifier not in rendered:
                body_parts.append(_render_treas_node(pr))
                rendered.add(pr.identifier)
        else:
            body_parts.append(
                f'                    <div class="subsection-content">{html_lib.escape(para)}</div>\n'
            )
    for sub in section.subsections:
        if sub.identifier not in rendered:
            body_parts.append(_render_treas_node(sub))

    meta = [
        '                    <div class="subsection-wrapper">',
        '                        <div class="subsection-heading level-1" style="margin-left:0">Source details</div>',
        '                        <div class="subsection-content" style="margin-left:24px">Source: Treasury Regulations (26 CFR)</div>',
    ]
    if section.citation:
        meta.append(f'                        <div class="subsection-content" style="margin-left:24px">Citation: {html_lib.escape(section.citation)}</div>')
    if section.effective_date:
        meta.append(f'                        <div class="subsection-content" style="margin-left:24px">Effective date: {html_lib.escape(section.effective_date)}</div>')
    if section.volume:
        meta.append(f'                        <div class="subsection-content" style="margin-left:24px">Volume: {html_lib.escape(section.volume)}</div>')
    meta.append('                    </div>')
    body_parts.append("\n".join(meta))
    body_html = "".join(body_parts)

    sid_esc = html_lib.escape(section.sectionId or "")
    search_js = _static_search_script(irc_nums, treas_nums)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{sid_esc} - {title}</title>
{SHARED_CSS}
</head>
<body id="top">
    <div class="reader-shell">
        <div class="reader-topbar">
            <div>
                <div class="reader-eyebrow">Treasury Regulations</div>
                <h1 class="reader-heading">{sid_esc}. {title}</h1>
                <p class="reader-subheading">26 CFR</p>
            </div>
            <div class="section-nav">
                <div class="section-nav-home">
                    <a class="section-nav-chip" href="index.html">Home</a>
                </div>
                <form class="section-search" data-section-search>
                    <input class="section-search-input" type="text" name="section"
                        placeholder="Go to section or regulation number">
                    <button class="section-search-button" type="submit">Go</button>
                    <div class="search-error" data-search-error hidden></div>
                </form>
            </div>
        </div>
        <div style="height:var(--content-offset)"></div>
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
                    <div class="section-title">{sid_esc}. {title}</div>
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


# ---------------------------------------------------------------------------
# Main export
# ---------------------------------------------------------------------------

def export_static_site():
    print("Loading current live app data...")

    # ========== LOAD IRC ==========
    irc_xml = HOSTING_DIR / "IRC" / "usc26.xml"
    print(f"[IRC] Loading {irc_xml.name}...")
    irc_parser = IRCXMLParser(str(irc_xml))
    irc_root = irc_parser.load_xml()
    irc_parser._heading_map = irc_parser._build_heading_map(irc_root)
    irc_parser._section_parent_map = irc_parser._build_section_parent_map(irc_root)
    irc_parser._section_elem_map = irc_parser._build_section_element_map(irc_root)
    irc_nums_raw = irc_parser.discover_all_section_numbers(irc_root)
    print(f"[IRC] {len(irc_nums_raw)} sections indexed")

    print("[IRC] Pre-building all section nodes...")
    irc_all_sections = []
    for num in irc_nums_raw:
        elem = irc_parser._find_section_element(irc_root, num)
        if elem is not None:
            section = irc_parser._build_section_node(elem)
            section.hierarchy = irc_parser._section_hierarchy(section.identifier)
            irc_all_sections.append(section)
    irc_parser.sections = irc_all_sections
    irc_section_nums = [s.sectionNumber for s in irc_all_sections]
    print(f"[IRC] Pre-built {len(irc_all_sections)} section nodes")

    # ========== LOAD TREASURY ==========
    print("[Treasury] Parsing XML volumes...")
    treas_glob = str(HOSTING_DIR / "Treasury Regulations" / "CFR-2025-title26-vol*.xml")
    treas_parser = TreasuryRegsXMLParser(treas_glob)
    treas_ordered = treas_parser.parse()
    treas_nums = [s.sectionNumber for s in treas_ordered]
    print(f"[Treasury] {len(treas_nums)} sections indexed")

    # ========== SETUP OUTPUT ==========
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nBuilding static site in {OUTPUT_DIR}/")

    # ========== EXPORT IRC PAGES ==========
    # Use pre-built sections directly — avoids re-parsing and any map lookup issues
    print(f"\nExporting {len(irc_all_sections)} IRC sections...")
    irc_success = 0
    for i, section in enumerate(irc_all_sections):
        if i % 500 == 0:
            print(f"  {i}/{len(irc_all_sections)}")
        try:
            html = irc_parser._build_html(section)
            safe_num = section.sectionNumber.replace("/", "_").replace(".", "_")
            with open(OUTPUT_DIR / f"irc_{safe_num}.html", "w", encoding="utf-8") as f:
                f.write(html)
            irc_success += 1
        except Exception as e:
            pass  # Silent on errors to avoid Unicode issues
    print(f"  {len(irc_all_sections)}/{len(irc_all_sections)} - Done: {irc_success} IRC pages")

    # ========== EXPORT TREASURY PAGES ==========
    print(f"\nExporting {len(treas_ordered)} Treasury sections...")
    treas_success = 0
    for i, section in enumerate(treas_ordered):
        if i % 500 == 0:
            print(f"  {i}/{len(treas_ordered)}")
        try:
            html = _build_treas_html(section, irc_section_nums, treas_nums)
            safe_id = section.sectionNumber.replace("/", "_").replace(".", "_")
            with open(OUTPUT_DIR / f"treas_{safe_id}.html", "w", encoding="utf-8") as f:
                f.write(html)
            treas_success += 1
        except Exception as e:
            pass  # Silent on errors to avoid Unicode issues
    print(f"  {len(treas_ordered)}/{len(treas_ordered)} - Done: {treas_success} Treasury pages")

    # ========== INDEX PAGE ==========
    print("\nGenerating index.html...")
    index_html = _build_index_page(irc_section_nums, treas_nums, treas_ordered)
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    total = irc_success + treas_success + 1
    print(f"\nSuccess! Generated {total} total pages in dist_pages/")
    print(f"  - {irc_success} IRC sections")
    print(f"  - {treas_success} Treasury regulations")
    print(f"  - 1 index page")


def _build_index_page(irc_nums, treas_nums, treas_objects):
    irc_links = []
    for num in irc_nums[:100]:
        safe = num.replace("/", "_").replace(".", "_")
        irc_links.append(
            f'                <a class="index-link" href="irc_{safe}.html">IRC \u00a7 {num}</a>'
        )
    treas_links = []
    for s in treas_objects[:100]:
        safe = s.sectionNumber.replace("/", "_").replace(".", "_")
        treas_links.append(
            f'                <a class="index-link" href="treas_{safe}.html">{html_lib.escape(s.sectionId or s.sectionNumber)}</a>'
        )
    search_js = _static_search_script(irc_nums, treas_nums)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tax Authority POC - IRC &amp; Treasury Regulations</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 40px 20px; background: #f5f5f5; color: #333; }}
        h1 {{ color: #003DA5; border-bottom: 3px solid #003DA5; padding-bottom: 10px; }}
        .section {{ background: white; padding: 30px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stats {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 20px; margin: 30px 0; }}
        .stat-card {{ background: linear-gradient(135deg,#003DA5,#002d77); color: white; padding: 25px; border-radius: 8px; text-align: center; }}
        .stat-number {{ font-size: 32px; font-weight: bold; margin: 10px 0; }}
        .stat-label {{ font-size: 14px; opacity: 0.9; }}
        .index-links {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr)); gap: 10px; margin-top: 20px; }}
        .index-link {{ display: block; padding: 12px; background: #f0f4fa; border: 1px solid #003DA5; border-radius: 4px; color: #003DA5; text-decoration: none; font-size: 14px; text-align: center; }}
        .index-link:hover {{ background: #003DA5; color: white; }}
        .section-search {{ display: flex; gap: 10px; margin-top: 12px; }}
        .section-search-input {{ flex: 1; padding: 10px 12px; border-radius: 8px; border: 1px solid #003DA5; font: inherit; }}
        .section-search-button {{ padding: 10px 16px; background: #003DA5; color: #fff; border: 0; border-radius: 8px; font: inherit; font-weight: bold; cursor: pointer; }}
        .search-error {{ margin-top: 8px; font-size: 13px; color: #b42318; }}
    </style>
</head>
<body>
    <div class="section">
        <h1>Tax Authority Proof of Concept</h1>
        <p>Complete searchable repository of Internal Revenue Code (IRC) sections and Treasury Regulations.</p>
    </div>
    <div class="section stats">
        <div class="stat-card">
            <div class="stat-label">IRC Sections</div>
            <div class="stat-number">{len(irc_nums):,}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Treasury Regulations</div>
            <div class="stat-number">{len(treas_nums):,}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Total Pages</div>
            <div class="stat-number">{len(irc_nums) + len(treas_nums) + 1:,}</div>
        </div>
    </div>
    <div class="section">
        <h2>Search</h2>
        <form class="section-search" data-section-search>
            <input class="section-search-input" type="text" name="section"
                placeholder="IRC section (e.g. 721) or Treasury reg (e.g. 1.721-1)">
            <button class="section-search-button" type="submit">Go</button>
        </form>
        <div class="search-error" data-search-error hidden></div>
    </div>
    <div class="section">
        <h2>Browse IRC Sections (first 100)</h2>
        <div class="index-links">
{chr(10).join(irc_links)}
        </div>
    </div>
    <div class="section">
        <h2>Browse Treasury Regulations (first 100)</h2>
        <div class="index-links">
{chr(10).join(treas_links)}
        </div>
    </div>
    <script>
{search_js}
    </script>
</body>
</html>"""


if __name__ == "__main__":
    export_static_site()
