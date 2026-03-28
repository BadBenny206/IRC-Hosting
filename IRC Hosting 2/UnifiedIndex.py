#!/usr/bin/env python3
"""Generate a unified IRC index that preserves the IRC browse structure and lists Treasury Regulations under each IRC section."""

import argparse
import html as html_lib
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from IRC_Parser_XML import IRCXMLParser


class UnifiedIndexGenerator:
    """Build a unified index using IRC hierarchy with Treasury links beneath IRC sections."""

    def __init__(self, irc_xml_path: str, treasreg_json_path: str):
        self.irc_xml_path = Path(irc_xml_path)
        self.treasreg_json_path = Path(treasreg_json_path)
        self.irc_sections: List[Dict] = []
        self.treas_by_irc: Dict[str, List[Dict]] = {}

    def load_irc_sections(self) -> None:
        parser = IRCXMLParser(str(self.irc_xml_path))
        root = parser.load_xml()
        parser._heading_map = parser._build_heading_map(root)
        parser._section_parent_map = parser._build_section_parent_map(root)

        sections: List[Dict] = []
        for section_elem in root.findall(".//uslm:section", parser.ns):
            identifier = section_elem.get("identifier", "")
            match = re.search(r"/s(\d+[A-Za-z]*)$", identifier)
            if not match:
                continue

            num_elem = section_elem.find("uslm:num", parser.ns)
            heading_elem = section_elem.find("uslm:heading", parser.ns)
            section_num = parser._clean_section_number(num_elem.text if num_elem is not None and num_elem.text else match.group(1))
            title = parser._extract_heading_text(heading_elem)
            sections.append(
                {
                    "sectionId": f"§ {section_num}",
                    "sectionNumber": section_num,
                    "title": title,
                    "identifier": identifier,
                    "hierarchy": parser._section_hierarchy(identifier),
                    "anchor": self._irc_anchor(section_num),
                }
            )

        self.irc_sections = sorted(sections, key=self._irc_sort_key)
        print(f"Loaded {len(self.irc_sections)} IRC sections from XML")

    def load_treasury_sections(self) -> None:
        if not self.treasreg_json_path.exists():
            raise FileNotFoundError(f"Treasury Regs JSON not found: {self.treasreg_json_path}")

        with open(self.treasreg_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sections = data.get("sections", data) if isinstance(data, dict) else data
        grouped: Dict[str, List[Dict]] = {}

        for section in sections:
            section_id = section.get("sectionId", "")
            irc_section = self._related_irc_section(section_id)
            if not irc_section:
                continue
            grouped.setdefault(irc_section, []).append(section)

        for key, value in grouped.items():
            grouped[key] = sorted(value, key=lambda item: self._treas_sort_key(item.get("sectionId", "")))

        self.treas_by_irc = grouped
        count = sum(len(value) for value in grouped.values())
        print(f"Loaded {count} Treasury Regulation links across {len(grouped)} IRC sections")

    def generate_html(self, output_dir: str) -> None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        available_sections = [section["sectionNumber"] for section in self.irc_sections]
        treasury_sections = sorted(
            {
                re.sub(r"\s+", "", str(reg.get("sectionId", "")).replace("§", "")).strip()
                for regs in self.treas_by_irc.values()
                for reg in regs
                if reg.get("sectionId")
            }
        )
        toc_parts: List[str] = []
        current_subtitle_id = ""
        current_chapter_id = ""
        current_subchapter_id = ""
        list_open = False

        for section in self.irc_sections:
            hierarchy = section["hierarchy"]
            subtitle = next((entry for entry in hierarchy if entry["type"] == "subtitle"), None)
            chapter = next((entry for entry in hierarchy if entry["type"] == "chapter"), None)
            subchapter = next((entry for entry in hierarchy if entry["type"] == "subchapter"), None)

            subtitle_id = subtitle["identifier"] if subtitle else ""
            chapter_id = chapter["identifier"] if chapter else ""
            subchapter_id = subchapter["identifier"] if subchapter else ""

            if subtitle_id != current_subtitle_id:
                if list_open:
                    toc_parts.append("            </ul>")
                    list_open = False
                current_subtitle_id = subtitle_id
                current_chapter_id = ""
                current_subchapter_id = ""
                if subtitle:
                    toc_parts.append(f'            <h2 class="index-subtitle">{html_lib.escape(subtitle["display"])}</h2>')

            if chapter_id != current_chapter_id:
                if list_open:
                    toc_parts.append("            </ul>")
                    list_open = False
                current_chapter_id = chapter_id
                current_subchapter_id = ""
                if chapter:
                    toc_parts.append(f'            <h3 class="index-chapter">{html_lib.escape(chapter["display"])}</h3>')

            if subchapter_id != current_subchapter_id:
                if list_open:
                    toc_parts.append("            </ul>")
                    list_open = False
                current_subchapter_id = subchapter_id
                if subchapter:
                    toc_parts.append(f'            <h4 class="index-subchapter">{html_lib.escape(subchapter["display"])}</h4>')

            if not list_open:
                toc_parts.append('            <ul class="index-list">')
                list_open = True

            regs_html = self._build_reg_links(section["sectionNumber"])
            toc_parts.append(
                f'                <li class="index-list-item" style="list-style:none">'
                f'<a class="index-link" href="{section["anchor"]}.html">'
                f'{section["sectionId"]}. {html_lib.escape(section["title"])}'
                f'</a>{regs_html}</li>'
            )

        if list_open:
            toc_parts.append("            </ul>")

        toc_html = "\n".join(toc_parts)

        html = f"""<!DOCTYPE html>
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
            margin: 0;
            padding: 32px;
            font-family: Arial, sans-serif;
            color: var(--ink);
            background: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
        }}

        .index-shell {{
            max-width: 1320px;
            margin: 0 auto;
        }}

        .index-hero {{
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 28px 30px;
            margin-bottom: 24px;
        }}

        .index-eyebrow {{
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 8px;
        }}

        .index-hero h1 {{
            margin: 0;
            color: var(--kpmg-blue);
            font-size: 34px;
        }}

        .index-toolbar {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            align-items: center;
            margin-top: 20px;
        }}

        .section-search {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .section-search-input {{
            min-width: 220px;
            padding: 12px 14px;
            border-radius: 12px;
            border: 1px solid rgba(0, 61, 165, 0.22);
            font: inherit;
        }}

        .section-search-button {{
            padding: 12px 16px;
            border: 0;
            border-radius: 12px;
            background: var(--kpmg-blue);
            color: #ffffff;
            font: inherit;
            font-weight: bold;
            cursor: pointer;
        }}

        .section-search-hint {{
            font-size: 13px;
            color: var(--muted);
        }}

        .index-list-shell {{
            background: rgba(255, 255, 255, 0.92);
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 24px 30px;
        }}

        .index-list-title {{
            margin: 0 0 18px 0;
            color: var(--kpmg-blue);
            font-size: 22px;
        }}

        .index-subtitle {{
            margin: 26px 0 6px 0;
            color: var(--kpmg-blue);
            font-size: 18px;
            font-weight: bold;
            border-bottom: 2px solid var(--line);
            padding-bottom: 6px;
        }}

        .index-chapter {{
            margin: 16px 0 4px 14px;
            color: var(--ink);
            font-size: 15px;
            font-weight: bold;
        }}

        .index-subchapter {{
            margin: 10px 0 4px 28px;
            color: var(--muted);
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}

        .index-list {{
            margin: 4px 0 10px 0;
            padding-left: 56px;
            list-style: none;
        }}

        .index-list-item + .index-list-item {{
            margin-top: 8px;
        }}

        .index-link {{
            color: var(--kpmg-blue);
            text-decoration: none;
            font-size: 16px;
            line-height: 1.5;
        }}

        .index-link:hover {{
            text-decoration: underline;
        }}

        .index-reg-list {{
            margin-top: 6px;
            margin-left: 28px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .index-reg-link {{
            color: var(--ink);
            text-decoration: none;
            font-size: 14px;
            line-height: 1.45;
        }}

        .index-reg-link:hover {{
            color: var(--kpmg-blue);
            text-decoration: underline;
        }}

        .index-reg-prefix {{
            color: var(--muted);
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}

        .search-error {{
            margin-top: 12px;
            font-size: 13px;
            color: #b42318;
        }}
    </style>
</head>
<body>
    <div class="index-shell">
        <section class="index-hero">
            <div class="index-eyebrow">Internal Revenue Code</div>
            <h1>US Code Title 26</h1>
            <div class="index-toolbar">
                <form class="section-search" data-section-search>
                    <input class="section-search-input" type="text" name="section" placeholder="Go to section or regulation number" aria-label="Go to section or regulation number">
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
        const availableIrcSections = {json.dumps(available_sections)};
        const availableTreasurySections = {json.dumps(treasury_sections)};
        const ircSectionMap = new Map(availableIrcSections.map((value) => [String(value).trim().toLowerCase(), value]));
        const treasurySectionMap = new Map();
        const treasurySuffixMap = new Map();
        const searchForm = document.querySelector('[data-section-search]');
        const searchError = document.querySelector('[data-search-error]');

        const normalizeIrcInput = (value) => value.replace(/[^0-9a-zA-Z]/g, '').trim().toLowerCase();
        const normalizeTreasuryInput = (value) => value
            .replace(/26\s*cfr/ig, '')
            .replace(/treasury\s+regulations?/ig, '')
            .replace(/regulations?/ig, '')
            .replace(/§/g, '')
            .replace(/[–—]/g, '-')
            .replace(/\s+/g, '')
            .trim()
            .toLowerCase();
        const toTreasuryAnchor = (value) => `sec-${{value.replace(/§/g, '').replace(/\s+/g, '').replace(/[().]/g, '-').replace(/--+/g, '-').replace(/^-|-$/g, '').toLowerCase()}}`;

        availableTreasurySections.forEach((value) => {{
            const normalized = normalizeTreasuryInput(String(value));
            treasurySectionMap.set(normalized, value);
            const suffix = normalized.replace(/^\d+\./, '');
            if (suffix && suffix !== normalized) {{
                if (!treasurySuffixMap.has(suffix)) {{
                    treasurySuffixMap.set(suffix, value);
                }} else if (treasurySuffixMap.get(suffix) !== value) {{
                    treasurySuffixMap.set(suffix, null);
                }}
            }}
        }});

        const showSearchError = (message) => {{
            if (!searchError) {{
                return;
            }}
            searchError.hidden = false;
            searchError.textContent = message;
        }};

        const clearSearchError = () => {{
            if (!searchError) {{
                return;
            }}
            searchError.hidden = true;
            searchError.textContent = '';
        }};

        searchForm?.addEventListener('submit', (event) => {{
            event.preventDefault();
            const formData = new FormData(searchForm);
            const rawValue = String(formData.get('section') || '').trim();
            const normalizedIrc = normalizeIrcInput(rawValue);
            const normalizedTreasury = normalizeTreasuryInput(rawValue);
            const looksLikeTreasury = normalizedTreasury.includes('.') || normalizedTreasury.includes('-');

            if (!rawValue) {{
                showSearchError('Enter an IRC section number or Treasury regulation number.');
                return;
            }}

            let treasuryMatch = treasurySectionMap.get(normalizedTreasury) || null;
            if (!treasuryMatch && looksLikeTreasury && !normalizedTreasury.includes('.')) {{
                treasuryMatch = treasurySuffixMap.get(normalizedTreasury) || null;
                if (treasuryMatch === null && treasurySuffixMap.has(normalizedTreasury)) {{
                    showSearchError(`More than one Treasury regulation matches ${{rawValue}}. Enter the full regulation number.`);
                    return;
                }}
            }}

            if (treasuryMatch) {{
                clearSearchError();
                window.location.href = `${{toTreasuryAnchor(treasuryMatch)}}.html`;
                return;
            }}

            const ircMatch = ircSectionMap.get(normalizedIrc);
            if (ircMatch) {{
                clearSearchError();
                window.location.href = `sec-${{ircMatch.toLowerCase()}}.html`;
                return;
            }}

            showSearchError(`No IRC section or Treasury regulation matched ${{rawValue}}.`);
        }});
    </script>
</body>
</html>"""

        output_file = output_path / "index.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Generated unified index: {output_file}")

    def _build_reg_links(self, section_number: str) -> str:
        regs = self.treas_by_irc.get(section_number, [])
        if not regs:
            return ""

        parts = ['<div class="index-reg-list"><div class="index-reg-prefix">Treasury Regulations</div>']
        for reg in regs:
            section_id = reg.get("sectionId", "")
            title = reg.get("title", "")
            parts.append(
                f'<a class="index-reg-link" href="{self._treas_anchor(section_id)}.html">'
                f'{html_lib.escape(section_id)}. {html_lib.escape(title)}</a>'
            )
        parts.append('</div>')
        return ''.join(parts)

    @staticmethod
    def _related_irc_section(section_id: str) -> Optional[str]:
        allowed_parts = {
            "1", "20", "25", "31", "35", "40", "41", "44", "48", "49",
            "53", "54", "55", "56", "57", "58", "60", "301",
        }
        section_id = re.sub(r"\s+", "", section_id.replace("§", "")).strip()
        match = re.match(r"^(\d+)\.(\d+[A-Za-z]*(?:\([^)]+\))*)-(\d+[A-Za-z]*)", section_id)
        if not match:
            return None
        part = match.group(1)
        if part not in allowed_parts:
            return None
        target = match.group(2)
        target_match = re.match(r"(\d+[A-Za-z]*)", target)
        return target_match.group(1) if target_match else None

    @staticmethod
    def _irc_anchor(section_number: str) -> str:
        normalized = section_number.replace("§", "").replace(" ", "")
        normalized = normalized.replace("(", "-").replace(")", "-").replace(".", "")
        normalized = normalized.replace("--", "-").strip("-").lower()
        return f"sec-{normalized}"

    @staticmethod
    def _treas_anchor(section_id: str) -> str:
        normalized = re.sub(r"\s+", "", section_id.replace("§", "")).strip()
        normalized = normalized.replace("(", "-").replace(")", "-").replace(".", "-")
        normalized = normalized.replace("--", "-").strip("-").lower()
        return f"sec-{normalized}"

    @staticmethod
    def _irc_sort_key(section: Dict) -> tuple:
        num = re.sub(r"^\[\s*", "", section["sectionNumber"]).strip()
        match = re.match(r"^(\d+)(.*)", num)
        if match:
            return (int(match.group(1)), match.group(2))
        return (0, num)

    @staticmethod
    def _treas_sort_key(section_id: str) -> tuple:
        section_id = re.sub(r"\s+", "", section_id.replace("§", "")).strip()
        match = re.match(r"^(\d+)\.(\d+[A-Za-z]*)(?:-(\d+[A-Za-z]*))?", section_id)
        if not match:
            return (0, 0, 0, section_id)
        part, code_section, reg_suffix = match.groups()
        code_match = re.match(r"(\d+)([A-Za-z]*)", code_section)
        suffix_match = re.match(r"(\d+)([A-Za-z]*)", reg_suffix or "0")
        return (
            int(part),
            int(code_match.group(1)) if code_match else 0,
            code_match.group(2).lower() if code_match else "",
            int(suffix_match.group(1)) if suffix_match else 0,
            suffix_match.group(2).lower() if suffix_match else "",
            section_id,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate unified IRC + Treasury Regulations index")
    parser.add_argument("--irc-xml", default="IRC/usc26.xml", help="Path to IRC USLM XML")
    parser.add_argument("--treasreg-json", default="output/treasury_regs/treasury_regs.json", help="Path to Treasury Regulations JSON")
    parser.add_argument("-o", "--output", default="output/html", help="Output directory")
    args = parser.parse_args()

    generator = UnifiedIndexGenerator(args.irc_xml, args.treasreg_json)
    generator.load_irc_sections()
    generator.load_treasury_sections()
    generator.generate_html(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
