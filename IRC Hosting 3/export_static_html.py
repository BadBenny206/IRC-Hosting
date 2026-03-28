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


def _sanitize_filename(section_number: str) -> str:
    """Sanitize section number for use in filename by replacing special characters."""
    # First remove § and normalize whitespace
    safe = section_number.replace("§", "").strip()
    # Replace common delimiters with underscores
    safe = safe.replace("/", "_").replace(".", "_").replace("-", "_")
    # Replace any non-alphanumeric characters (including Unicode parentheses) with underscores
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', safe)
    # Clean up multiple consecutive underscores
    safe = re.sub(r'_+', '_', safe)
    # Remove leading/trailing underscores
    safe = safe.strip("_")
    return safe


def _normalize_treas_search_key(value: str) -> str:
    """Match the Treasury search normalization used by the client-side JS."""
    normalized = str(value)
    normalized = re.sub(r"26\s*cfr", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"treasury\s+regulations?", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"regulations?", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.replace("§", "")
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.strip().lower()


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
            content: ''; position: fixed; top: 0; left: 0; right: 0;
            height: 120px;
            background: #eef4fb; z-index: 500; pointer-events: none;
        }
        body::after {
            content: ''; position: fixed; top: 120px; left: 0; right: 0; height: 61px;
            background-image: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
            background-repeat: no-repeat; background-size: 100% 181px; background-position: 0 -120px;
            z-index: -1; pointer-events: none;
        }
        .reader-shell { max-width: 1320px; margin: 0 auto; }
        .reader-topbar {
            display: flex; justify-content: space-between; align-items: center;
            gap: 24px; padding: 18px 22px; position: fixed; top: var(--topbar-offset);
            left: 50%; transform: translateX(-50%);
            width: min(calc(100vw - 64px), 1320px); z-index: 1000;
            background: rgba(255,255,255,0.97);
            border: 1px solid rgba(0,61,165,0.12); border-radius: 18px; box-shadow: var(--shadow);
            will-change: transform;
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
        .section-search { display: flex; gap: 10px; align-items: center; flex-wrap: nowrap; justify-content: flex-end; width: 100%; }
        .section-search-input { flex: 1 1 auto; min-width: 0; padding: 10px 12px; border-radius: 12px; border: 1px solid rgba(0,61,165,0.22); font: inherit; }
        .section-search-button { padding: 10px 14px; border: 0; border-radius: 12px; background: var(--kpmg-blue); color: #fff; font: inherit; font-weight: bold; cursor: pointer; flex-shrink: 0; white-space: nowrap; }
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
        .subsection-wrapper { margin-bottom: 8px; position: relative; z-index: 1; }
        .subsection-heading { color: var(--kpmg-blue); font-weight: bold; margin-top: 16px; margin-bottom: 8px; padding-left: 14px; border-left: 4px solid var(--kpmg-blue); position: relative; z-index: 1; scroll-margin-top: calc(var(--content-offset) + 12px); }
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
    """Search JS that navigates to static irc_N.html / treas_N.html files.
    Logic ported directly from server.py _search_script(), with URL generation
    changed from query-string routing to static filename routing."""
    # Build a Python-side map of normalized treas number -> sanitized filename
    # so the JS can resolve the filename without reimplementing _sanitize_filename.
    treas_filename_map = {}
    for t in treas_numbers:
        norm = _normalize_treas_search_key(t)
        safe = _sanitize_filename(t)
        treas_filename_map[norm] = safe
    return f"""
        const availableIrcSections = {json.dumps(irc_numbers)};
        const availableTreasurySections = {json.dumps(treas_numbers)};
        const treasFilenameMap = {json.dumps(treas_filename_map)};
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

        const toTreasUrl = v => {{
            const norm = normalizeTreas(String(v));
            const safe = treasFilenameMap[norm];
            return safe ? 'treas_' + safe + '.html' : null;
        }};

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
            if (treasMatch) {{
                const url = toTreasUrl(treasMatch);
                if (url) {{ clearErr(); window.location.href = url; return; }}
            }}
            const ircMatch = ircSectionMap.get(normI);
            if (ircMatch) {{
                clearErr();
                const safeNum = String(ircMatch).replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
                window.location.href = 'irc_' + safeNum + '.html';
                return;
            }}
            showErr(`No IRC section or Treasury regulation matched ${{raw}}.`);
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


def _process_treas_content(content: str) -> str:
    """Process Treasury content, converting [TABLE] markers to HTML tables."""
    if not content or "[TABLE]" not in content:
        return html_lib.escape(content)
    
    parts = content.split("[TABLE]")
    before_table = parts[0].strip()
    html_out = ""
    
    if before_table:
        html_out += html_lib.escape(before_table)
    
    if len(parts) > 1:
        table_part = parts[1].split("[END TABLE]")[0].strip()
        html_out += '<div class="table-wrapper" style="margin: 12px 0;"><table style="border-collapse:collapse;width:100%;">'
        rows = [row for row in table_part.split("\n") if row.strip()]
        is_header = False
        for row in rows:
            cells = row.split(" | ")
            if is_header:
                html_out += "<thead><tr>" + "".join(f"<th style='border:1px solid #ccc;padding:8px;text-align:left;'>{html_lib.escape(cell.strip())}</th>" for cell in cells) + "</tr></thead>"
                is_header = False
            else:
                html_out += "<tr>" + "".join(f"<td style='border:1px solid #ccc;padding:8px;'>{html_lib.escape(cell.strip())}</td>" for cell in cells) + "</tr>"
        html_out += "</table></div>"
    
    return html_out


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
    raw_content = html_lib.unescape(node.content) if node.content else ""
    content_html = _process_treas_content(raw_content)
    
    lines = (
        '                    <div class="subsection-wrapper">\n'
        f'                        <div class="subsection-heading level-{node.level}" '
        f'id="{anchor_id}" style="margin-left:{hm}px">{sid}</div>\n'
        f'                        <div class="subsection-content level-{node.level}" '
        f'style="margin-left:{cm}px">{content_html}</div>\n'
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
            para_html = _process_treas_content(para)
            body_parts.append(
                f'                    <div class="subsection-content">{para_html}</div>\n'
            )
    
    # Render any top-level subsections not yet covered by the paragraph loop above.
    # _render_treas_node is already recursive, so we only need to check root level.
    for sub in section.subsections:
        if sub.identifier not in rendered:
            body_parts.append(_render_treas_node(sub))
            rendered.add(sub.identifier)

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


def _patch_irc_html_for_static(html: str, irc_nums: list, treas_nums: list) -> str:
    """Patch exported IRC pages for static navigation and search layout."""
    static_js = _static_search_script(irc_nums, treas_nums)
    patched = html
    patched = re.sub(
        r'\n\s*background-attachment:\s*fixed;\s*',
        '\n',
        patched,
        count=1,
    )
    patched = re.sub(
        r'(body::before\s*\{[^}]*?height:\s*)var\(--content-offset,\s*200px\)(;)',
        r'\1120px\2',
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'(body::before\s*\{.*?\}\s*)',
        r'''\1

        body::after {
            content: '';
            position: fixed;
            top: 120px;
            left: 0;
            right: 0;
            height: 61px;
            background-image: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
            background-repeat: no-repeat;
            background-size: 100% 181px;
            background-position: 0 -120px;
            z-index: 998;
            pointer-events: none;
        }
''',
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'body::before\s*\{.*?z-index:\s*999;.*?\}',
        """body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 120px;
            background: #eef4fb;
            z-index: 500;
            pointer-events: none;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'body::after\s*\{.*?z-index:\s*998;.*?\}',
        """body::after {
            content: '';
            position: fixed;
            top: 120px;
            left: 0;
            right: 0;
            height: 61px;
            background-image: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
            background-repeat: no-repeat;
            background-size: 100% 181px;
            background-position: 0 -120px;
            z-index: -1;
            pointer-events: none;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'\.reader-shell\s*\{[^}]*?position:\s*relative;[^}]*?z-index:\s*1;[^}]*?\}',
        """.reader-shell {
            max-width: 1320px;
            margin: 0 auto;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'\.section-search\s*\{.*?\}',
        """.section-search {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: nowrap;
            justify-content: flex-end;
            width: 100%;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'\.section-search-input\s*\{.*?\}',
        """.section-search-input {
            flex: 1 1 auto;
            min-width: 0;
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid rgba(0, 61, 165, 0.22);
            font: inherit;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'(\.subsection-wrapper\s*\{[^}]*?)scroll-margin-top[^;]+;',
        r'\1',
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'(\.subsection-heading\s*\{)',
        r'\1\n            scroll-margin-top: calc(var(--content-offset) + 12px);',
        patched,
        count=1,
    )
    patched = re.sub(
        r'\.section-search-button\s*\{.*?\}',
        """.section-search-button {
            padding: 10px 14px;
            border: 0;
            border-radius: 12px;
            background: var(--kpmg-blue);
            color: #ffffff;
            font: inherit;
            font-weight: bold;
            cursor: pointer;
            flex-shrink: 0;
            white-space: nowrap;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'\.sidebar-card\s*\{[^}]*?\}',
        """.sidebar-card {
            background: var(--paper);
            border: 1px solid rgba(0, 61, 165, 0.12);
            border-radius: 18px;
            box-shadow: var(--shadow);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            min-height: 0;
            flex: 1;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    patched = re.sub(
        r'\.sidebar-card-body\s*\{[^}]*?\}',
        """.sidebar-card-body {
            padding: 8px;
            flex: 1 1 0;
            min-height: 0;
            overflow-y: auto;
        }""",
        patched,
        flags=re.DOTALL,
        count=1,
    )
    # Replace the generated search script without using a large DOTALL regex.
    search_start = patched.find("const availableIrcSections")
    sync_start = patched.find("const syncOffsets")
    if search_start != -1 and sync_start != -1 and search_start < sync_start:
        patched = patched[:search_start] + static_js + patched[sync_start:]
    return patched


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
            html = _patch_irc_html_for_static(html, irc_section_nums, treas_nums)
            safe_num = _sanitize_filename(section.sectionNumber)
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
            safe_id = _sanitize_filename(section.sectionNumber)
            with open(OUTPUT_DIR / f"treas_{safe_id}.html", "w", encoding="utf-8") as f:
                f.write(html)
            treas_success += 1
        except Exception as e:
            pass  # Silent on errors to avoid Unicode issues
    print(f"  {len(treas_ordered)}/{len(treas_ordered)} - Done: {treas_success} Treasury pages")

    # ========== BUILD TREASURY-BY-IRC MAP ==========
    # Only map Treasury regs from CFR parts that implement Title 26 IRC sections.
    # This mirrors server.py's _related_irc() logic exactly.
    _ALLOWED_PARTS = {"1","20","25","31","35","40","41","44","48","49",
                      "53","54","55","56","57","58","60","301"}

    def _related_irc(section_id: str):
        s = re.sub(r"\s+", "", section_id.replace("§", "")).strip()
        m = re.match(r"^(\d+)\.(\d+[A-Za-z]*(?:\([^)]+\))*)-(\d+[A-Za-z]*)", s)
        if not m or m.group(1) not in _ALLOWED_PARTS:
            return None
        tm = re.match(r"(\d+[A-Za-z]*)", m.group(2))
        return tm.group(1) if tm else None

    print("\nBuilding Treasury-by-IRC map...")
    treas_by_irc = {}
    for treas_section in treas_ordered:
        irc_num = _related_irc(treas_section.sectionId or "")
        if irc_num:
            treas_by_irc.setdefault(irc_num, []).append(treas_section)

    print(f"Mapped {len(treas_by_irc)} IRC sections to Treasury regulations")

    # ========== INDEX PAGE ==========
    print("\nGenerating index.html...")
    index_html = _build_index_page(irc_section_nums, treas_nums, treas_ordered, 
                                     irc_sections=irc_all_sections, treas_by_irc_map=treas_by_irc)
    with open(OUTPUT_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    total = irc_success + treas_success + 1
    print(f"\nSuccess! Generated {total} total pages in dist_pages/")
    print(f"  - {irc_success} IRC sections")
    print(f"  - {treas_success} Treasury regulations")
    print(f"  - 1 index page")


def _build_index_page(irc_nums, treas_nums, treas_objects, irc_sections=None, treas_by_irc_map=None):
    """Build the index page.

    When irc_sections (list of SectionNode with .hierarchy set) is provided
    the page uses the full hierarchical browse identical to the server.py
    dynamic index (subtitle → chapter → subchapter → section list).
    Falls back to a simple flat list when not provided.
    
    treas_by_irc_map: dict mapping IRC section number to list of Treasury regulation objects
    """
    search_js = _static_search_script(irc_nums, treas_nums)
    treas_by_irc_map = treas_by_irc_map or {}

    def _reg_links(section_number: str) -> str:
        """Generate nested Treasury regulation links for an IRC section."""
        regs = treas_by_irc_map.get(section_number, [])
        if not regs:
            return ""
        parts = ['<div class="index-reg-list"><div class="index-reg-prefix">Treasury Regulations</div>']
        for reg in regs:
            safe_id = _sanitize_filename(reg.sectionNumber)
            parts.append(
                f'<a class="index-reg-link" href="treas_{safe_id}.html">'
                f'{html_lib.escape(reg.sectionId or "")}. {html_lib.escape(reg.title or "")}</a>'
            )
        parts.append('</div>')
        return "".join(parts)

    # ---- Build hierarchical TOC (server.py format) ----
    if irc_sections:
        def _sort_key(sec):
            num = re.sub(r'^\[\s*', '', sec.sectionNumber).strip()
            m = re.match(r'^(\d+)(.*)', num)
            return (int(m.group(1)), m.group(2)) if m else (0, num)

        sorted_secs = sorted(irc_sections, key=_sort_key)
        toc_parts = []
        cur_sub = cur_ch = cur_sch = ""
        list_open = False

        for sec in sorted_secs:
            h = sec.hierarchy if hasattr(sec, 'hierarchy') and sec.hierarchy else []
            subtitle   = next((e for e in h if e["type"] == "subtitle"),   None)
            chapter    = next((e for e in h if e["type"] == "chapter"),    None)
            subchapter = next((e for e in h if e["type"] == "subchapter"), None)

            sid  = subtitle["identifier"]   if subtitle   else ""
            cid  = chapter["identifier"]    if chapter    else ""
            scid = subchapter["identifier"] if subchapter else ""

            if sid != cur_sub:
                if list_open:
                    toc_parts.append("            </ul>"); list_open = False
                cur_sub = sid; cur_ch = cur_sch = ""
                if subtitle:
                    toc_parts.append(f'            <h2 class="index-subtitle">{html_lib.escape(subtitle["display"])}</h2>')

            if cid != cur_ch:
                if list_open:
                    toc_parts.append("            </ul>"); list_open = False
                cur_ch = cid; cur_sch = ""
                if chapter:
                    toc_parts.append(f'            <h3 class="index-chapter">{html_lib.escape(chapter["display"])}</h3>')

            if scid != cur_sch:
                if list_open:
                    toc_parts.append("            </ul>"); list_open = False
                cur_sch = scid
                if subchapter:
                    toc_parts.append(f'            <h4 class="index-subchapter">{html_lib.escape(subchapter["display"])}</h4>')

            if not list_open:
                toc_parts.append('            <ul class="index-list">'); list_open = True

            safe = sec.sectionNumber.replace("/", "_").replace(".", "_")
            regs_html = _reg_links(sec.sectionNumber)
            toc_parts.append(
                f'                <li class="index-list-item" style="list-style:none">'
                f'<a class="index-link" href="irc_{safe}.html">'
                f'{html_lib.escape(sec.sectionId)}. {html_lib.escape(sec.title or "")}</a>{regs_html}</li>'
            )

        if list_open:
            toc_parts.append("            </ul>")
        toc_html = "\n".join(toc_parts)
    else:
        # Simple fallback when hierarchy isn't available
        items = []
        for num in irc_nums:
            safe = num.replace("/", "_").replace(".", "_")
            regs_html = _reg_links(num)
            items.append(f'                <li class="index-list-item" style="list-style:none">'
                         f'<a class="index-link" href="irc_{safe}.html">§ {num}</a>{regs_html}</li>')
        toc_html = '            <ul class="index-list">\n' + "\n".join(items) + "\n            </ul>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Internal Revenue Code</title>
    <style>
        :root {{
            --kpmg-blue: #003DA5; --ink: #243245; --muted: #68768a;
            --paper: #ffffff; --line: rgba(0,61,165,0.12);
            --shadow: 0 12px 28px rgba(0,34,85,0.08);
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0; padding: 32px; font-family: Arial, sans-serif;
            color: var(--ink);
            background: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
        }}
        .index-shell {{ max-width: 1320px; margin: 0 auto; }}
        .index-hero {{
            background: rgba(255,255,255,0.88); border: 1px solid var(--line);
            border-radius: 22px; box-shadow: var(--shadow); padding: 28px 30px; margin-bottom: 24px;
        }}
        .index-eyebrow {{ font-size: 12px; font-weight: bold; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }}
        .index-hero h1 {{ margin: 0; color: var(--kpmg-blue); font-size: 34px; }}
        .index-toolbar {{ display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-top: 20px; }}
        .section-search {{ display: flex; gap: 10px; align-items: center; flex-wrap: nowrap; }}
        .section-search-input {{ min-width: 220px; padding: 12px 14px; border-radius: 12px; border: 1px solid rgba(0,61,165,0.22); font: inherit; }}
        .section-search-button {{ padding: 12px 16px; border: 0; border-radius: 12px; background: var(--kpmg-blue); color: #fff; font: inherit; font-weight: bold; cursor: pointer; white-space: nowrap; }}
        .section-search-hint {{ font-size: 13px; color: var(--muted); }}
        .search-error {{ margin-top: 12px; font-size: 13px; color: #b42318; }}
        .index-list-shell {{
            background: rgba(255,255,255,0.92); border: 1px solid var(--line);
            border-radius: 22px; box-shadow: var(--shadow); padding: 24px 30px;
        }}
        .index-list-title {{ margin: 0 0 18px 0; color: var(--kpmg-blue); font-size: 22px; }}
        .index-subtitle {{ margin: 26px 0 6px 0; color: var(--kpmg-blue); font-size: 18px; font-weight: bold; border-bottom: 2px solid var(--line); padding-bottom: 6px; }}
        .index-chapter {{ margin: 16px 0 4px 14px; color: var(--ink); font-size: 15px; font-weight: bold; }}
        .index-subchapter {{ margin: 10px 0 4px 28px; color: var(--muted); font-size: 12px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.06em; }}
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


if __name__ == "__main__":
    export_static_site()
