#!/usr/bin/env python3
"""
IRC XML Parser - Extracts sections from USLM XML instead of PDF.
Uses the XML hierarchy directly so legal indentation follows the source
structure rather than text heuristics.
"""

import argparse
import html as html_lib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Sequence


STRUCTURAL_TAGS = (
    "subsection",
    "paragraph",
    "subparagraph",
    "clause",
    "subclause",
    "item",
    "subitem",
)

DEFAULT_RENDER_SECTIONS = ["1", "2", "11", "21", "41", "61", "121", "151", "162", "170"]


class SectionNode:
    """Hierarchical IRC section node."""

    def __init__(
        self,
        section_id: str,
        title: str = "",
        level: int = 0,
        content: str = "",
        identifier: str = "",
        tag_name: str = "",
    ):
        self.sectionId = section_id
        self.title = title
        self.level = level
        self.content = content
        self.continuation = ""  # text that follows child clauses (USLM <continuation>)
        self.identifier = identifier
        self.tagName = tag_name
        self.subsections: List["SectionNode"] = []
        self.footnotes: List[Dict] = []
        self.crossReferences: List[Dict] = []
        self.page = 0
        self.indentation = 0
        self.source = "IRC"
        self.hierarchy: List[Dict] = []  # parent chain: subtitle, chapter, subchapter, part

    @property
    def sectionNumber(self) -> str:
        """Numeric portion of sectionId, e.g. '§ 170' -> '170'."""
        return self.sectionId.replace("§", "").strip()

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "sectionId": self.sectionId,
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "identifier": self.identifier,
            "tagName": self.tagName,
            "page": self.page,
            "indentation": self.indentation,
            "source": self.source,
            "footnotes": self.footnotes,
            "crossReferences": self.crossReferences,
            "subsections": [s.to_dict() for s in self.subsections],
        }

    def get_anchor_id(self) -> str:
        """Generate a stable HTML anchor ID."""
        if self.identifier:
            parts = [part for part in self.identifier.strip("/").split("/") if part]
            for index, part in enumerate(parts):
                if re.fullmatch(r"s\d+[A-Za-z]*", part):
                    normalized = [part[1:].lower()] + [item.lower() for item in parts[index + 1 :]]
                    return "sec-" + "-".join(filter(None, normalized))

        normalized = self.sectionId
        normalized = normalized.replace("§", "").replace(" ", "")
        normalized = normalized.replace("(", "-").replace(")", "-").replace(".", "")
        normalized = normalized.replace("--", "-").strip("-").lower()
        return f"sec-{normalized}"


class IRCXMLParser:
    """Parse IRC from USLM XML format."""

    def __init__(self, xml_path: str):
        self.xml_path = Path(xml_path)
        self.sections: List[SectionNode] = []
        self.ns = {
            "uslm": "http://xml.house.gov/schemas/uslm/1.0",
            "xhtml": "http://www.w3.org/1999/xhtml",
        }
        self._heading_map: Dict[str, Dict] = {}
        self._section_parent_map: Dict[str, List[Dict]] = {}
        self._section_elem_map: Dict[str, ET.Element] = {}

    def load_xml(self) -> ET.Element:
        """Load and parse XML file."""
        if not self.xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {self.xml_path}")

        tree = ET.parse(str(self.xml_path))
        return tree.getroot()

    def _build_heading_map(self, root: ET.Element) -> Dict[str, Dict]:
        """Build identifier -> heading info for structural elements (subtitle/chapter/subchapter/part)."""
        heading_map: Dict[str, Dict] = {}
        for elem in root.iter():
            local = self._local_name(elem)
            if local in ("subtitle", "chapter", "subchapter", "part"):
                identifier = elem.get("identifier", "")
                if identifier:
                    num_elem = elem.find("uslm:num", self.ns)
                    heading_elem = elem.find("uslm:heading", self.ns)
                    num_text = (num_elem.text or "").strip() if num_elem is not None else ""
                    heading_text = self._extract_heading_text(heading_elem)
                    heading_map[identifier] = {
                        "type": local,
                        "num": num_text,
                        "heading": heading_text,
                        "identifier": identifier,
                        "display": f"{num_text.rstrip(chr(8212)).strip()} \u2014 {heading_text.lstrip(chr(8212)).strip()}" if num_text and heading_text else (num_text or heading_text),
                    }
        return heading_map

    def _build_section_parent_map(self, root: ET.Element) -> Dict[str, List[Dict]]:
        """Map each section identifier to its ordered list of structural ancestors."""
        parent_map: Dict[str, List[Dict]] = {}

        def _walk(elem: ET.Element, ancestors: List[Dict]):
            local = self._local_name(elem)
            if local in ("subtitle", "chapter", "subchapter", "part"):
                identifier = elem.get("identifier", "")
                entry = self._heading_map.get(identifier)
                if entry:
                    ancestors = ancestors + [entry]
            if local == "section":
                identifier = elem.get("identifier", "")
                if identifier:
                    parent_map[identifier] = list(ancestors)
            for child in elem:
                _walk(child, ancestors)

        _walk(root, [])
        return parent_map

    def _section_hierarchy(self, identifier: str) -> List[Dict]:
        """Return ordered list of parent structural nodes for a given section identifier."""
        return self._section_parent_map.get(identifier, [])

    @staticmethod
    def _load_treasury_section_numbers() -> List[str]:
        treasury_json = Path("output/treasury_regs/treasury_regs.json")
        if not treasury_json.exists():
            return []

        with open(treasury_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        sections = data.get("sections", data) if isinstance(data, dict) else data
        
        # Handle case where sections is not iterable
        if not isinstance(sections, (list, tuple)):
            if isinstance(sections, dict):
                sections = [sections]
            else:
                return []
        
        numbers = []
        for section in sections:
            try:
                # Skip non-dict sections
                if not isinstance(section, dict):
                    continue
                section_id = str(section.get("sectionId", ""))
                if not section_id or section_id == "":
                    continue
                normalized = re.sub(r"\s+", "", section_id.replace("§", "")).strip()
                if normalized:
                    numbers.append(normalized)
            except (AttributeError, TypeError, ValueError):
                # Skip sections with parsing errors
                continue
        return sorted(set(numbers))

    @staticmethod
    def _build_unified_search_script(irc_numbers: List[str], treasury_numbers: List[str], irc_prefix: str, treasury_prefix: str) -> str:
        return f"""
        const availableIrcSections = {json.dumps(irc_numbers)};
        const availableTreasurySections = {json.dumps(treasury_numbers)};
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

        const searchInput = searchForm?.querySelector('[name="section"]');
        searchInput?.addEventListener('focus', (event) => {{
            event.preventDefault();
            window.scrollTo({{ top: window.scrollY, left: 0, behavior: 'auto' }});
        }});

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
                window.location.href = `{treasury_prefix}${{toTreasuryAnchor(treasuryMatch)}}.html`;
                return;
            }}

            const ircMatch = ircSectionMap.get(normalizedIrc);
            if (ircMatch) {{
                clearSearchError();
                window.location.href = `{irc_prefix}sec-${{ircMatch.toLowerCase()}}.html`;
                return;
            }}

            showSearchError(`No IRC section or Treasury regulation matched ${{rawValue}}.`);
        }});
"""

    def discover_all_section_numbers(self, root: ET.Element) -> List[str]:
        """Return sorted list of all top-level section numbers in the XML."""
        seen: set = set()
        numbers: List[str] = []
        for section in root.findall(".//uslm:section", self.ns):
            identifier = section.get("identifier", "")
            match = re.search(r"/s(\d+[A-Za-z]*)$", identifier)
            if match:
                num = match.group(1)
                if num not in seen:
                    seen.add(num)
                    numbers.append(num)

        def _sort_key(n: str):
            m = re.match(r"(\d+)", n)
            return (int(m.group(1)) if m else 0, n)

        return sorted(numbers, key=_sort_key)

    def _local_name(self, elem: ET.Element) -> str:
        return elem.tag.split("}")[-1]

    def _clean_section_number(self, raw_number: str) -> str:
        return (raw_number or "").replace("§", "").strip().rstrip(".")

    def _extract_heading_text(self, elem: Optional[ET.Element]) -> str:
        if elem is None:
            return ""
        return self.extract_text_from_element(elem).strip()

    def extract_text_from_element(self, elem: ET.Element, skip_tables: bool = False) -> str:
        """Extract all text content from an element and its children."""
        text_parts: List[str] = []

        def recurse(el: ET.Element):
            if skip_tables and self._local_name(el) == "table":
                return
            if el.text:
                text_parts.append(el.text)
            for child in el:
                recurse(child)
                if child.tail:
                    text_parts.append(child.tail)

        recurse(elem)
        result = " ".join(text_parts).strip()
        result = re.sub(r"\n\s*\n", "\n", result)
        result = re.sub(r"  +", " ", result)
        return result

    def extract_table_content(self, table_elem: ET.Element) -> str:
        """Convert HTML table to readable text."""
        rows = []
        for tr in table_elem.findall(".//xhtml:tr", self.ns):
            row_data = []
            for td in tr.findall("./xhtml:td", self.ns) + tr.findall("./xhtml:th", self.ns):
                row_data.append(self.extract_text_from_element(td).strip())
            if row_data:
                rows.append(" | ".join(row_data))
        return "\n".join(rows)

    def _extract_direct_content(self, node: ET.Element) -> str:
        """Extract only the node's own text (chapeau/content), excluding continuation and nested legal children."""
        content_parts: List[str] = []

        for child in node:
            child_name = self._local_name(child)
            if child_name in STRUCTURAL_TAGS or child_name in {"num", "heading", "continuation", "notes", "note", "sourceCredit"}:
                continue

            if child_name == "content":
                text = self.extract_text_from_element(child)
                if text:
                    content_parts.append(text)
                continue

            text = self.extract_text_from_element(child)
            if text:
                content_parts.append(text)

        return " ".join(part.strip() for part in content_parts if part.strip()).strip()

    def _extract_continuation_content(self, node: ET.Element) -> str:
        """Extract text from <continuation> elements — these render AFTER child clauses."""
        parts: List[str] = []
        for child in node:
            if self._local_name(child) != "continuation":
                continue
            cont_text = self.extract_text_from_element(child, skip_tables=True)
            if cont_text:
                parts.append(cont_text)
            table = child.find(".//xhtml:table", self.ns)
            if table is not None:
                table_text = self.extract_table_content(table)
                if table_text:
                    parts.append("\n[TABLE]\n" + table_text + "\n[END TABLE]")
        return " ".join(p.strip() for p in parts if p.strip()).strip()

    def _parse_structural_children(self, parent_elem: ET.Element, level: int) -> List[SectionNode]:
        children: List[SectionNode] = []
        for child in parent_elem:
            child_name = self._local_name(child)
            if child_name not in STRUCTURAL_TAGS:
                continue
            children.append(self._parse_structural_node(child, level))
        return children

    def _parse_structural_node(self, elem: ET.Element, level: int) -> SectionNode:
        num_elem = elem.find("uslm:num", self.ns)
        heading_elem = elem.find("uslm:heading", self.ns)
        class_name = elem.get("class", "")
        indent_match = re.search(r"indent(\d+)", class_name)

        section_id = self._extract_heading_text(num_elem)
        title = self._extract_heading_text(heading_elem)
        node = SectionNode(
            section_id=section_id,
            title=title,
            level=level,
            content=self._extract_direct_content(elem),
            identifier=elem.get("identifier", ""),
            tag_name=self._local_name(elem),
        )
        node.continuation = self._extract_continuation_content(elem)
        if indent_match:
            node.indentation = int(indent_match.group(1))

        node.subsections = self._parse_structural_children(elem, level + 1)
        return node

    def _build_section_element_map(self, root: ET.Element) -> Dict[str, ET.Element]:
        """Build a single-pass map of cleaned section number -> section element."""
        result: Dict[str, ET.Element] = {}
        for section in root.findall(".//uslm:section", self.ns):
            identifier = section.get("identifier") or ""
            # identifier like /us/usc/t26/s170 or /us/usc/t26/s4978a
            last = identifier.rsplit("/", 1)[-1]
            if last.startswith("s"):
                num = self._clean_section_number(last[1:])
                if num:
                    result[num] = section
        return result

    def _find_section_element(self, root: ET.Element, section_number: str) -> Optional[ET.Element]:
        """Find a section element by section number (uses pre-built map if available)."""
        cleaned_number = self._clean_section_number(section_number)
        if self._section_elem_map:
            return self._section_elem_map.get(cleaned_number)
        # Fallback: single scan
        target_identifier = f"/s{cleaned_number}"
        for section in root.findall(".//uslm:section", self.ns):
            identifier = section.get("identifier") or ""
            if identifier.endswith(target_identifier):
                return section
        return None

    def _build_section_node(self, section_elem: ET.Element) -> SectionNode:
        """Build a section node from a section element."""
        num_elem = section_elem.find("uslm:num", self.ns)
        heading_elem = section_elem.find("uslm:heading", self.ns)

        section_num = self._clean_section_number(num_elem.text if num_elem is not None and num_elem.text else "")
        section_title = self._extract_heading_text(heading_elem)

        section_node = SectionNode(
            section_id=f"§ {section_num}",
            title=section_title,
            level=0,
            content=self._extract_direct_content(section_elem),
            identifier=section_elem.get("identifier", ""),
            tag_name="section",
        )
        section_node.continuation = self._extract_continuation_content(section_elem)
        section_node.subsections = self._parse_structural_children(section_elem, 1)
        return section_node

    def parse_sections(self, root: ET.Element, section_numbers: Sequence[str]):
        """Extract one or more sections and their nested hierarchies."""
        self.sections = []
        self._heading_map = self._build_heading_map(root)
        self._section_parent_map = self._build_section_parent_map(root)
        self._section_elem_map = self._build_section_element_map(root)

        for section_number in section_numbers:
            section_elem = self._find_section_element(root, section_number)
            if section_elem is None:
                print(f"WARNING: § {section_number} not found in XML")
                continue

            section_node = self._build_section_node(section_elem)
            section_node.hierarchy = self._section_hierarchy(section_node.identifier)
            self.sections.append(section_node)
            print(f"[OK] Found {section_node.sectionId} with {len(section_node.subsections)} top-level subsections")

    def parse_section_1(self, root: ET.Element):
        """Extract § 1. Tax imposed and its nested hierarchy."""
        self.parse_sections(root, ["1"])
        if not self.sections:
            print("ERROR: § 1 not found in XML")
            return

    def save_json(self, output_dir: Path):
        """Save sections to JSON files."""
        output_dir = Path(output_dir)
        json_dir = output_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)

        for section in self.sections:
            filename = section.get_anchor_id() + ".json"
            filepath = json_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(section.to_dict(), f, indent=2, ensure_ascii=False)

            print(f"  Saved: {filename}")

    def generate_html(self, output_dir: Path):
        """Generate HTML files from sections."""
        output_dir = Path(output_dir)
        html_dir = output_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)

        for section in self.sections:
            filename = section.get_anchor_id() + ".html"
            filepath = html_dir / filename
            html_content = self._build_html(section)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"  Generated: {filename}")

        self.generate_index_html(html_dir)

    def generate_index_html(self, html_dir: Path):
        """Generate a simple index page for the rendered section set."""
        def _section_sort_key(section):
            # Strip leading bracket (reserved/repealed sections like "[ 1000") before parsing
            import re as _re
            num = _re.sub(r'^\[\s*', '', section.sectionNumber).strip()
            m = _re.match(r'^(\d+)(.*)', num)
            if m:
                return (int(m.group(1)), m.group(2))
            return (0, num)

        sorted_sections = sorted(self.sections, key=_section_sort_key)
        available_sections = [section.sectionNumber for section in sorted_sections]

        # Build hierarchical TOC HTML grouped by subtitle / chapter / subchapter
        toc_parts: List[str] = []
        current_subtitle_id = ""
        current_chapter_id = ""
        current_subchapter_id = ""
        list_open = False

        for section in sorted_sections:
            h = section.hierarchy
            subtitle = next((e for e in h if e["type"] == "subtitle"), None)
            chapter = next((e for e in h if e["type"] == "chapter"), None)
            subchapter = next((e for e in h if e["type"] == "subchapter"), None)

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
            toc_parts.append(
                f'                <li class="index-list-item" style="list-style:none">'
                f'<a class="index-link" href="{section.get_anchor_id()}.html">'
                f"{section.sectionId}. {html_lib.escape(section.title)}</a></li>"
            )

        if list_open:
            toc_parts.append("            </ul>")

        toc_html = "\n".join(toc_parts)
        treasury_sections = self._load_treasury_section_numbers()

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

        .index-hero p {{
            margin: 10px 0 0 0;
            color: var(--muted);
            line-height: 1.6;
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
{self._build_unified_search_script(available_sections, treasury_sections, '', '')}
    </script>
</body>
</html>"""

        index_path = html_dir / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"  Generated: {index_path.name}")

    def _render_content_block(self, content: str, indent_px: int) -> str:
        if not content:
            return ""

        wrapper_style = f'style="margin-left: {indent_px}px;"' if indent_px else ""

        if "[TABLE]" in content:
            parts = content.split("[TABLE]")
            before_table = parts[0].strip()
            html = ""
            if before_table:
                html += f'                        <div class="subsection-content" {wrapper_style}>{self._format_legal_text(before_table)}</div>\n'

            if len(parts) > 1:
                table_part = parts[1].split("[END TABLE]")[0].strip()
                html += f'                        <div class="table-wrapper" {wrapper_style}>\n'
                html += "                            <table>\n"
                rows = [row for row in table_part.split("\n") if row.strip()]
                is_header = True
                for row in rows:
                    cells = row.split(" | ")
                    if is_header:
                        html += "                                <thead><tr>" + "".join(
                            f"<th>{cell.strip()}</th>" for cell in cells
                        ) + "</tr></thead>\n"
                        is_header = False
                    else:
                        html += "                                <tr>" + "".join(
                            f"<td>{cell.strip()}</td>" for cell in cells
                        ) + "</tr>\n"
                html += "                            </table>\n"
                html += "                        </div>\n"
            return html

        if "If taxable income is:" in content and "The tax is:" in content:
            table_header_idx = content.find("If taxable income is:")
            preamble = content[:table_header_idx].strip()
            table_content = content[table_header_idx:].strip()
            html = ""

            if preamble:
                html += f'                        <div class="subsection-content" {wrapper_style}>{self._format_legal_text(preamble)}</div>\n'

            html += f'                        <div class="table-wrapper" {wrapper_style}>\n'
            html += "                            <table>\n"
            html += "                                <thead><tr><th>If taxable income is:</th><th>The tax is:</th></tr></thead>\n"
            lines = table_content.split("\n")
            for line in lines[1:]:
                line = line.strip()
                if not line or not (line.startswith("Not over") or line.startswith("Over")):
                    continue
                match = re.match(r"((?:Not over|Over)\s+\$[\d,]+(?:\s+but not over\s+\$[\d,]+)?)\s+(.+)", line)
                if match:
                    col1, col2 = match.groups()
                    html += f"                                <tr><td>{col1.strip()}</td><td>{col2.strip()}</td></tr>\n"
            html += "                            </table>\n"
            html += "                        </div>\n"
            return html

        return f'                        <div class="subsection-content" {wrapper_style}>{self._format_legal_text(content)}</div>\n'

    def _render_node(self, node: SectionNode, base_anchor: str) -> str:
        depth = max(node.level - 1, 0)
        indent_px = depth * 28
        raw_anchor = node.get_anchor_id() if node.identifier else f"{base_anchor}-{node.sectionId.strip('()').strip().lower()}"
        # Extract just the final identifier part (e.g., "e" from "sec-351-e" or "g-2-c" from "sec-351-g-2-c")
        if raw_anchor.startswith("sec-"):
            parts = raw_anchor[4:].split("-")  # Remove "sec-" prefix and split
            # Find the first non-numeric part to start the anchor
            anchor_parts = []
            for part in parts:
                if not part.isdigit() or anchor_parts:  # Start collecting after first letter, then include everything
                    anchor_parts.append(part)
            anchor_id = "-".join(anchor_parts) if anchor_parts else raw_anchor
        else:
            anchor_id = raw_anchor
        title_suffix = f". {node.title}" if node.title else ""

        html = f'                    <div class="subsection-wrapper level-{min(node.level, 6)}">\n'
        html += (
            f'                        <div class="subsection-heading level-{min(node.level, 6)}" '
            f'id="{anchor_id}" style="margin-left: {indent_px}px;">{node.sectionId}{title_suffix}</div>\n'
        )
        html += self._render_content_block(node.content, indent_px + 24)
        for child in node.subsections:
            html += self._render_node(child, base_anchor)
        if node.continuation:
            html += self._render_content_block(node.continuation, indent_px + 24)
        html += "                    </div>\n"
        return html

    def _build_html(self, section: SectionNode) -> str:
        """Build HTML for a section using the XML hierarchy directly."""
        anchor = section.get_anchor_id()
        kpmg_blue = "#003DA5"
        toc_items = []
        for sub in section.subsections:
            raw_sub_anchor = sub.get_anchor_id()
            sub_anchor = raw_sub_anchor[len(anchor) + 1:] if raw_sub_anchor.startswith(anchor + '-') else raw_sub_anchor
            toc_title = f"{sub.sectionId} {sub.title}".strip()
            toc_items.append(
                f'                <a class="toc-link" href="#{sub_anchor}" data-target="{sub_anchor}">'
                f'<span class="toc-marker">{sub.sectionId}</span><span class="toc-text">{html_lib.escape(sub.title) if sub.title else toc_title}</span></a>'
            )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{section.sectionId} - {section.title}</title>
    <style>
        :root {{
            --kpmg-blue: {kpmg_blue};
            --kpmg-blue-dark: #002d77;
            --ink: #333;
            --muted: #68768a;
            --line: #d8e1ee;
            --paper: #ffffff;
            --shadow: 0 12px 28px rgba(0, 34, 85, 0.08);
            --topbar-offset: 16px;
            --sticky-gap: 20px;
            --content-offset: 156px;
        }}

        * {{ box-sizing: border-box; }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 32px;
            color: var(--ink);
            background: linear-gradient(180deg, #eef4fb 0%, #f9fbfd 180px, #ffffff 181px);
        }}

        body::before {{
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 120px;
            background: #eef4fb;
            z-index: 999;
            pointer-events: none;
        }}

        .reader-shell {{
            max-width: 1320px;
            margin: 0 auto;
        }}

        .reader-topbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 24px;
            padding: 18px 22px;
            position: fixed;
            top: var(--topbar-offset);
            left: 50%;
            transform: translateX(-50%);
            width: min(calc(100vw - 64px), 1320px);
            z-index: 1000;
            background: rgba(255, 255, 255, 0.97);
            border: 1px solid rgba(0, 61, 165, 0.12);
            border-radius: 18px;
            box-shadow: var(--shadow);
            will-change: transform;
        }}

        .reader-eyebrow {{
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 6px;
        }}

        .reader-heading {{
            font-size: 28px;
            font-weight: bold;
            color: var(--kpmg-blue);
            margin: 0;
        }}

        .reader-subheading {{
            margin: 6px 0 0 0;
            font-size: 13px;
            color: var(--muted);
        }}

        .section-nav {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 12px;
            flex: 0 0 320px;
        }}

        .section-nav-chip {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            min-height: 40px;
            padding: 10px 14px;
            border-radius: 999px;
            border: 1px solid rgba(0, 61, 165, 0.18);
            background: var(--paper);
            color: var(--muted);
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            text-decoration: none;
        }}

        .section-nav-chip strong {{
            color: var(--kpmg-blue);
            font-size: 13px;
            letter-spacing: normal;
            text-transform: none;
        }}

        .section-nav-home {{
            width: 100%;
            display: flex;
            justify-content: flex-end;
        }}

        .reader-layout {{
            display: grid;
            grid-template-columns: 280px minmax(0, 1fr);
            gap: 28px;
            align-items: start;
        }}

        .reader-sidebar {{
            position: sticky;
            top: var(--content-offset);
            height: calc(100vh - var(--content-offset) - 40px);
            display: flex;
            flex-direction: column;
        }}

        .sidebar-card {{
            background: var(--paper);
            border: 1px solid rgba(0, 61, 165, 0.12);
            border-radius: 18px;
            box-shadow: var(--shadow);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            min-height: 0;
            flex: 1;
        }}

        .sidebar-card-header {{
            padding: 18px 18px 14px 18px;
            background: linear-gradient(180deg, rgba(0, 61, 165, 0.08) 0%, rgba(0, 61, 165, 0.02) 100%);
            border-bottom: 1px solid var(--line);
            flex-shrink: 0;
        }}

        .sidebar-card-title {{
            margin: 0;
            font-size: 13px;
            font-weight: bold;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--muted);
        }}

        .sidebar-card-body {{
            padding: 8px;
            flex: 1 1 0;
            min-height: 0;
            overflow-y: auto;
        }}

        .toc-link {{
            display: grid;
            grid-template-columns: 56px minmax(0, 1fr);
            gap: 10px;
            align-items: start;
            padding: 10px 12px;
            border-radius: 12px;
            color: var(--ink);
            text-decoration: none;
            transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
        }}

        .toc-link:hover {{
            background: rgba(0, 61, 165, 0.06);
            color: var(--kpmg-blue);
        }}

        .toc-link.is-active {{
            background: rgba(0, 61, 165, 0.1);
            color: var(--kpmg-blue-dark);
            transform: translateX(2px);
        }}

        .toc-marker {{
            font-weight: bold;
            color: var(--kpmg-blue);
        }}

        .toc-text {{
            font-size: 13px;
            line-height: 1.45;
        }}

        .sidebar-card-footer {{
            padding: 12px 18px 16px 18px;
            border-top: 1px solid var(--line);
        }}

        .back-to-top {{
            color: var(--kpmg-blue);
            text-decoration: none;
            font-size: 13px;
            font-weight: bold;
        }}

        .reader-main {{ min-width: 0; }}

        .section-card {{
            background: var(--paper);
            border: 1px solid rgba(0, 61, 165, 0.12);
            border-radius: 22px;
            box-shadow: var(--shadow);
            padding: 30px 34px 36px 34px;
        }}

        .section-title {{
            font-size: 32px;
            font-weight: bold;
            color: var(--kpmg-blue);
            border-bottom: 4px solid var(--kpmg-blue);
            padding-bottom: 12px;
            margin-bottom: 14px;
        }}

        .section-search {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
            justify-content: flex-end;
            width: 100%;
        }}

        .section-search-input {{
            flex: 1 1 300px;
            min-width: 0;
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid rgba(0, 61, 165, 0.22);
            font: inherit;
        }}

        .section-search-button {{
            padding: 10px 14px;
            border: 0;
            border-radius: 12px;
            background: var(--kpmg-blue);
            color: #ffffff;
            font: inherit;
            font-weight: bold;
            cursor: pointer;
        }}

        .search-error {{
            width: 100%;
            font-size: 13px;
            color: #b42318;
        }}

        .subsection-wrapper {{
            margin-bottom: 8px;
            scroll-margin-top: calc(var(--content-offset) - 8px);
            position: relative;
            z-index: 1;
        }}

        .subsection-heading {{
            color: var(--kpmg-blue);
            font-weight: bold;
            margin-top: 16px;
            margin-bottom: 8px;
            padding-left: 14px;
            border-left: 4px solid var(--kpmg-blue);
            position: relative;
            z-index: 1;
        }}

        .subsection-heading.level-1 {{ font-size: 16px; }}
        .subsection-heading.level-2 {{ font-size: 15px; }}
        .subsection-heading.level-3 {{ font-size: 14px; }}
        .subsection-heading.level-4,
        .subsection-heading.level-5,
        .subsection-heading.level-6 {{ font-size: 13px; }}

        .subsection-content {{
            line-height: 1.8;
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 13px;
            margin-bottom: 10px;
        }}

        .table-wrapper {{
            margin: 14px 0 18px 0;
            border: 2px solid var(--kpmg-blue);
            border-radius: 14px;
            overflow: hidden;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}

        table th {{
            background-color: var(--kpmg-blue);
            color: white;
            padding: 10px;
            text-align: left;
            font-weight: bold;
            border: 1px solid var(--kpmg-blue);
        }}

        table td {{
            padding: 8px 10px;
            border: 1px solid #ddd;
            vertical-align: top;
        }}

        table tbody tr:nth-child(odd) {{ background-color: #f9f9f9; }}
        table tbody tr:hover {{ background-color: #f0f0f0; }}

        @media (max-width: 980px) {{
            :root {{ --topbar-offset: 12px; }}

            body {{ padding: 18px; }}

            .reader-topbar {{
                flex-direction: column;
                align-items: stretch;
            }}

            .section-nav {{
                flex: 1 1 auto;
                align-items: stretch;
            }}

            .section-nav-home {{ justify-content: flex-start; }}
            .section-search {{ justify-content: flex-start; }}
            .reader-layout {{ grid-template-columns: 1fr; }}
            .reader-sidebar {{
                position: static;
                order: -1;
            }}

            .section-card {{ padding: 22px 20px 28px 20px; }}
        }}
    </style>
</head>
<body id="top">
    <div class="reader-shell">
        <div class="reader-topbar">
            <div>
                <div class="reader-eyebrow">Internal Revenue Code</div>
                <h1 class="reader-heading">{section.sectionId}. {section.title}</h1>
                <p class="reader-subheading">US Code Title 26</p>
            </div>
            <div class="section-nav">
                <div class="section-nav-home">
                    <a class="section-nav-chip" href="index.html">Home</a>
                </div>
                <form class="section-search" data-section-search>
                    <input class="section-search-input" type="text" name="section" placeholder="Go to section or regulation number" aria-label="Go to section or regulation number">
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
{chr(10).join(toc_items)}
                    </div>
                    <div class="sidebar-card-footer">
                        <a class="back-to-top" href="#top">Back to top</a>
                    </div>
                </div>
            </aside>

            <main class="reader-main">
                <div class="section-card">
                    <div class="section-title">{section.sectionId}. {section.title}</div>
"""
        if section.content and not section.subsections:
            html += self._render_content_block(section.content, 0)

        for sub in section.subsections:
            html += self._render_node(sub, anchor)

        if section.continuation and not section.subsections:
            html += self._render_content_block(section.continuation, 0)

        _sec_nums_json = json.dumps(sorted(
            [s.sectionNumber for s in self.sections],
            key=lambda n: (int(re.match(r"(\d+)", n).group(1)) if re.match(r"^\d", n) else 0, n),
        ))
        _treasury_nums_json = json.dumps(self._load_treasury_section_numbers())

        html += """
                </div>
            </main>
        </div>
    </div>
    <script>
        const root = document.documentElement;
        const topbar = document.querySelector('.reader-topbar');
        const tocLinks = Array.from(document.querySelectorAll('.toc-link'));
        const sections = tocLinks
            .map((link) => document.getElementById(link.getAttribute('data-target')))
            .filter(Boolean);
""" + self._build_unified_search_script(json.loads(_sec_nums_json), json.loads(_treasury_nums_json), "", "") + """

        const syncOffsets = () => {
            if (!topbar) { return; }
            const stickyGap = parseFloat(getComputedStyle(root).getPropertyValue('--sticky-gap')) || 20;
            const topbarRect = topbar.getBoundingClientRect();
            const contentOffset = Math.ceil(topbarRect.bottom + stickyGap);
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

        if ('IntersectionObserver' in window && tocLinks.length > 0 && sections.length > 0) {
            const linkById = new Map(tocLinks.map((link) => [link.getAttribute('data-target'), link]));
            const observer = new IntersectionObserver((entries) => {
                const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];

                if (!visible) {
                    return;
                }

                tocLinks.forEach((link) => link.classList.remove('is-active'));
                const activeLink = linkById.get(visible.target.id);
                if (activeLink) {
                    activeLink.classList.add('is-active');
                }
            }, {
                rootMargin: '-20% 0px -60% 0px',
                threshold: [0.1, 0.35, 0.6]
            });

            sections.forEach((sectionNode) => observer.observe(sectionNode));
            tocLinks[0]?.classList.add('is-active');
        }
    </script>
</body>
</html>"""
        return html

    def _format_legal_text(self, text: str) -> str:
        """Escape text for HTML while preserving structural line breaks."""
        return html_lib.escape(text)


def main():
    """Main entry point."""
    cli = argparse.ArgumentParser(description="Render IRC sections from Title 26 USLM XML.")
    cli.add_argument(
        "--sections",
        nargs="+",
        default=DEFAULT_RENDER_SECTIONS,
        help="Section numbers to render. Defaults to a 10-page validation set.",
    )
    cli.add_argument(
        "--all",
        action="store_true",
        help="Discover and render ALL sections found in the XML (may be many thousands).",
    )
    cli.add_argument(
        "--index-only",
        action="store_true",
        help="Deprecated. Per-source IRC index generation is disabled; use the unified index instead.",
    )
    args = cli.parse_args()

    xml_file = Path(__file__).parent / "IRC" / "usc26.xml"

    print("=" * 70)
    print("IRC XML Parser - USLM Format")
    print("=" * 70)

    try:
        parser = IRCXMLParser(str(xml_file))
        root = parser.load_xml()
        print(f"[OK] XML loaded: {xml_file.name}")

        index_only = getattr(args, 'index_only', False)

        if args.all or index_only:
            section_nums = parser.discover_all_section_numbers(root)
            print(f"\nDiscovered {len(section_nums)} sections in XML.")
        else:
            section_nums = args.sections

        print(f"\nExtracting {len(section_nums)} section(s) from XML...")
        parser.parse_sections(root, section_nums)

        output_dir = Path(__file__).parent / "output"
        html_dir = output_dir / "html"

        if index_only:
            print("\nPer-source IRC index generation is disabled. Use output/unified_index/index.html.")
        else:
            print(f"\nSaving output to {output_dir}...")
            parser.save_json(output_dir)
            parser.generate_html(output_dir)

        print("\n" + "=" * 70)
        print("Parser complete!")
        print("=" * 70)

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
