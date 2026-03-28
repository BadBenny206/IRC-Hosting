#!/usr/bin/env python3
"""
Treasury Regulations (26 CFR) XML Parser.
Parses one or many GovInfo CFR XML volumes and renders output using the same
visual structure as the IRC renderer.
"""

import argparse
import html as html_lib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional


DEFAULT_XML_GLOB = "Treasury Regulations/CFR-2025-title26-vol*.xml"
DEFAULT_RENDER_SECTIONS = [
    "1.61-1",
    "1.162-1",
    "1.170-1",
    "1.183-1",
    "1.213-1",
    "1.280A-1",
]


class RegulationNode:
    """Treasury Regulation section node."""

    def __init__(
        self,
        section_id: str,
        title: str = "",
        level: int = 0,
        content: str = "",
        identifier: str = "",
        tag_name: str = "",
        display_id: str = "",
    ):
        self.sectionId = section_id
        self.displayId = display_id or section_id
        self.title = title
        self.level = level
        self.content = content
        self.identifier = identifier
        self.tagName = tag_name
        self.subsections: List["RegulationNode"] = []
        self.footnotes: List[Dict] = []
        self.crossReferences: List[Dict] = []
        self.page = 0
        self.indentation = 0
        self.source = "Treasury Regulations (26 CFR)"
        self.sourceCode = "TREASREG"
        self.hierarchy: List[Dict] = []
        self.citation: Optional[str] = None
        self.effective_date: Optional[str] = None
        self.volume: Optional[str] = None

    @property
    def sectionNumber(self) -> str:
        return re.sub(r"\s+", "", self.sectionId.replace("§", "")).strip()

    def to_dict(self) -> Dict:
        return {
            "sectionId": self.sectionId,
            "displayId": self.displayId,
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "identifier": self.identifier,
            "tagName": self.tagName,
            "page": self.page,
            "indentation": self.indentation,
            "source": self.source,
            "sourceCode": self.sourceCode,
            "citation": self.citation,
            "effective_date": self.effective_date,
            "volume": self.volume,
            "footnotes": self.footnotes,
            "crossReferences": self.crossReferences,
            "subsections": [s.to_dict() for s in self.subsections],
        }

    def get_anchor_id(self) -> str:
        normalized = re.sub(r"\s+", "", self.sectionId.replace("§", "")).strip()
        normalized = normalized.replace("(", "-").replace(")", "-").replace(".", "-")
        normalized = normalized.replace("--", "-").strip("-").lower()
        return f"sec-{normalized}"


class TreasuryRegsXMLParser:
    """Parse Treasury Regulations from GovInfo CFR XML volumes."""

    def __init__(self, xml_source: str):
        self.xml_source = xml_source
        self.sections: List[RegulationNode] = []
        self._rendered_section_numbers: List[str] = []

    def _resolve_xml_files(self) -> List[Path]:
        candidate = Path(self.xml_source)
        has_wildcard = any(char in self.xml_source for char in "*?[]")

        if has_wildcard:
            # Handle both absolute and relative glob patterns
            if Path(self.xml_source).is_absolute():
                # Absolute path with wildcard - split into directory and pattern
                parent = candidate.parent
                pattern = candidate.name
                files = sorted(parent.glob(pattern))
            else:
                # Relative path with wildcard - glob from current directory
                files = sorted(Path.cwd().glob(self.xml_source))
        elif candidate.is_dir():
            files = sorted(candidate.glob("CFR-*-title26-vol*.xml"))
        elif candidate.exists():
            files = [candidate]
        else:
            # Try as relative first, then absolute
            if Path.cwd().joinpath(self.xml_source).exists():
                files = sorted(Path.cwd().glob(self.xml_source))
            else:
                files = []

        if not files:
            raise FileNotFoundError(f"No Treasury Regulation XML files found for: {self.xml_source}")

        return files

    @staticmethod
    def _normalize_requested_section(value: str) -> str:
        value = value.strip()
        return value[2:].strip() if value.startswith("§") else value

    def parse(self, requested_sections: Optional[List[str]] = None) -> List[RegulationNode]:
        requested = {self._normalize_requested_section(value) for value in (requested_sections or [])}
        xml_files = self._resolve_xml_files()
        deduped: Dict[str, RegulationNode] = {}

        for xml_file in xml_files:
            tree = ET.parse(xml_file)
            root = tree.getroot()
            section_elems = root.findall(".//SECTION")
            print(f"Found {len(section_elems)} regulation sections in {xml_file.name}")

            for section_elem in section_elems:
                section_node = self._parse_section(section_elem, xml_file.name)
                if not section_node:
                    continue
                if requested and section_node.sectionNumber not in requested:
                    continue
                deduped[section_node.sectionId] = section_node

        self.sections = sorted(deduped.values(), key=lambda item: self._section_sort_key(item.sectionNumber))
        print(f"Loaded {len(self.sections)} distinct Treasury Regulation sections from {len(xml_files)} XML files")
        return self.sections

    def _parse_section(self, section_elem: ET.Element, source_name: str) -> Optional[RegulationNode]:
        sectno = (section_elem.findtext("SECTNO", "") or "").strip()
        if not sectno:
            return None

        sectno = re.sub(r"^§", "", sectno).strip()
        sectno = re.sub(r"\s+", "", sectno)
        sectno = f"§ {sectno}"

        subject = (section_elem.findtext("SUBJECT", "") or "").strip()
        paragraphs = []
        for p_elem in section_elem.findall("P"):
            p_text = self._extract_text(p_elem)
            if p_text:
                paragraphs.append(p_text)

        node = RegulationNode(
            section_id=sectno,
            title=subject,
            level=0,
            content="\n\n".join(paragraphs),
            identifier=sectno,
            tag_name="SECTION",
        )
        node.citation = (section_elem.findtext("CITA", "") or "").strip() or None
        node.effective_date = (section_elem.findtext("EFFDNOT", "") or "").strip() or None
        node.volume = source_name
        para_tuples = [(text, self._p_has_italic_marker(p_elem)) for p_elem, text in zip(section_elem.findall("P"), paragraphs)]
        node.subsections = self._build_flat_subsections(para_tuples)
        return node

    @staticmethod
    def _p_has_italic_marker(p_elem: ET.Element) -> bool:
        """Return True if this P element's leading marker is italic (content inside an <E> child)."""
        raw_text = (p_elem.text or "").strip()
        # Plain marker: p.text contains a complete '(x)' pattern
        if re.match(r"^\([^)]+\)", raw_text):
            return False
        # Italic marker: p.text is just '(' or empty, with marker content in a child E element
        if raw_text in ("(", "") or raw_text.startswith("(") and ")" not in raw_text:
            first_child = next(iter(p_elem), None)
            if first_child is not None and first_child.tag in ("E", "I", "em"):
                return True
        return False

    def _build_flat_subsections(self, paragraphs) -> List[RegulationNode]:
        subsections: List[RegulationNode] = []
        marker_stack: List[Dict[str, object]] = []

        for index, item in enumerate(paragraphs, start=1):
            if isinstance(item, tuple):
                paragraph, is_italic = item
            else:
                paragraph, is_italic = item, False
            marker_match = re.match(r"^\(([^)]+)\)\s*(.*)", paragraph)
            if not marker_match:
                continue

            current_marker, current_remainder = marker_match.groups()
            current_is_italic = is_italic
            segment_index = 0

            while current_marker:
                content, nested = self._split_inline_nested_marker(current_remainder)
                force_child = segment_index > 0
                level = self._push_marker_level(
                    current_marker,
                    marker_stack,
                    current_is_italic or force_child,
                    force_child=force_child,
                )
                identifier = f"p{index}" if segment_index == 0 else f"p{index}.{segment_index}"
                display_marker = f"({current_marker.strip()})"
                full_marker = "".join(str(item["marker"]) for item in marker_stack)
                child = RegulationNode(
                    section_id=full_marker,
                    title=self._summarize_subsection(content),
                    level=level,
                    content=content,
                    identifier=identifier,
                    tag_name="P",
                    display_id=display_marker,
                )
                child.indentation = max(0, (level - 1) * 28)
                subsections.append(child)

                if not nested:
                    break

                current_marker, current_remainder = nested
                current_is_italic = True
                segment_index += 1

        return self._nest_subsections(subsections)

    @staticmethod
    def _nest_subsections(subsections: List[RegulationNode]) -> List[RegulationNode]:
        roots: List[RegulationNode] = []
        stack: List[RegulationNode] = []

        for node in subsections:
            while stack and stack[-1].level >= node.level:
                stack.pop()

            if stack:
                stack[-1].subsections.append(node)
            else:
                roots.append(node)

            stack.append(node)

        return roots

    @staticmethod
    def _looks_like_marker_token(marker: str) -> bool:
        compact = re.sub(r"\s+", "", marker)
        return bool(re.fullmatch(r"\d+|[A-Za-z]{1,8}", compact))

    def _split_inline_nested_marker(self, content: str) -> tuple[str, Optional[tuple[str, str]]]:
        match = re.match(r"^(.*?)(?:\s*[—-]\s*)\(([^)]+)\)\s*(.*)$", content)
        if not match:
            return content.strip(), None

        leading, nested_marker, nested_remainder = match.groups()
        if not leading.strip() or not self._looks_like_marker_token(nested_marker):
            return content.strip(), None

        return leading.strip(), (nested_marker, nested_remainder)

    def _push_marker_level(
        self,
        marker: str,
        marker_stack: List[Dict[str, object]],
        is_italic: bool = False,
        force_child: bool = False,
    ) -> int:
        kind = self._marker_kind(marker, marker_stack, is_italic)
        rank = self._marker_rank(kind)
        marker_display = f"({marker.strip()})"

        if force_child and marker_stack:
            level = int(marker_stack[-1]["level"]) + 1
            marker_stack.append({"kind": kind, "rank": rank, "level": level, "marker": marker_display})
            return level

        while marker_stack and int(marker_stack[-1]["rank"]) > rank:
            marker_stack.pop()

        if marker_stack and int(marker_stack[-1]["rank"]) == rank:
            level = int(marker_stack[-1]["level"])
            marker_stack.pop()
        elif marker_stack and int(marker_stack[-1]["rank"]) < rank:
            level = int(marker_stack[-1]["level"]) + 1
        else:
            level = 1

        marker_stack.append({"kind": kind, "rank": rank, "level": level, "marker": marker_display})
        return level

    @staticmethod
    def _marker_kind(marker: str, marker_stack: List[Dict[str, object]], is_italic: bool = False) -> str:
        token = marker.strip()
        roman_lower = set("ivxlcdm")
        roman_upper = set("IVXLCDM")

        if re.fullmatch(r"\d+", token):
            base = "digit"
        elif re.fullmatch(r"[A-Z]+", token):
            if len(token) > 1 and all(char in roman_upper for char in token):
                base = "roman-upper"
            else:
                base = "alpha-upper"
        elif re.fullmatch(r"[a-z]+", token):
            if len(token) > 1 and all(char in roman_lower for char in token):
                base = "roman-lower"
            elif len(token) == 1 and token in roman_lower:
                base = TreasuryRegsXMLParser._single_lowercase_marker_kind(token, marker_stack)
            else:
                base = "alpha-lower"
        else:
            base = "other"

        return base + ("-italic" if is_italic else "")

    @staticmethod
    def _single_lowercase_marker_kind(token: str, marker_stack: List[Dict[str, object]]) -> str:
        previous_alpha = TreasuryRegsXMLParser._nearest_marker_token(marker_stack, "alpha-lower")
        if previous_alpha and len(previous_alpha) == 1 and ord(token) == ord(previous_alpha) + 1:
            return "alpha-lower"

        previous_roman = TreasuryRegsXMLParser._nearest_marker_token(marker_stack, "roman-lower")
        if previous_roman:
            current_value = TreasuryRegsXMLParser._roman_to_int(token)
            previous_value = TreasuryRegsXMLParser._roman_to_int(previous_roman)
            if current_value is not None and previous_value is not None and current_value == previous_value + 1:
                return "roman-lower"

        parent_kind = TreasuryRegsXMLParser._nearest_base_kind(marker_stack)
        if token == "i" and parent_kind in {"digit", "alpha-upper", "roman-lower"}:
            return "roman-lower"

        if token in {"v", "x", "l"}:
            return "roman-lower"

        return "alpha-lower"

    @staticmethod
    def _nearest_marker_token(marker_stack: List[Dict[str, object]], kind: str) -> Optional[str]:
        for item in reversed(marker_stack):
            item_kind = str(item.get("kind", "")).replace("-italic", "")
            if item_kind != kind:
                continue

            marker = str(item.get("marker", "")).strip()
            match = re.fullmatch(r"\(([^)]+)\)", marker)
            if match:
                return match.group(1).strip().lower()
        return None

    @staticmethod
    def _nearest_base_kind(marker_stack: List[Dict[str, object]]) -> str:
        for item in reversed(marker_stack):
            kind = str(item.get("kind", "")).replace("-italic", "")
            if kind:
                return kind
        return ""

    @staticmethod
    def _roman_to_int(value: str) -> Optional[int]:
        if not value or not re.fullmatch(r"[ivxlcdm]+", value):
            return None

        numerals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
        total = 0
        previous = 0
        for char in reversed(value):
            current = numerals[char]
            if current < previous:
                total -= current
            else:
                total += current
                previous = current
        return total

    @staticmethod
    def _marker_rank(kind: str) -> int:
        ranks = {
            # Plain markers (levels 1-5)
            "alpha-lower": 1,
            "digit": 2,
            "roman-lower": 3,
            "alpha-upper": 4,
            "roman-upper": 5,
            # Italic markers (levels 6-10) — these appear nested inside plain markers
            "alpha-lower-italic": 6,
            "digit-italic": 7,
            "roman-lower-italic": 8,
            "alpha-upper-italic": 9,
            "roman-upper-italic": 10,
            "other": 1,
            "other-italic": 6,
        }
        return ranks.get(kind, 1)

    @staticmethod
    def _summarize_subsection(content: str) -> str:
        cleaned = content.strip()
        if not cleaned:
            return ""

        summary = re.split(r"\s+[—-]\s+\(?[0-9A-Za-zivxlcdmIVXLCDM]+\)?|\.(?:\s|$)|;(?:\s|$)|:(?:\s|$)", cleaned, maxsplit=1)[0].strip()
        return summary[:120]

    @staticmethod
    def _irc_sort_key(section_num: str) -> tuple:
        match = re.match(r"^(\d+)([A-Za-z]*)$", section_num)
        if not match:
            return (0, "", section_num)
        return (int(match.group(1)), match.group(2).lower(), section_num)

    def _load_irc_section_numbers(self) -> List[str]:
        json_dir = Path("output/json")
        if not json_dir.exists():
            return []

        numbers = []
        for file_path in json_dir.glob("sec-*.json"):
            suffix = file_path.stem[4:]
            if suffix:
                numbers.append(suffix.upper())

        return sorted(set(numbers), key=self._irc_sort_key)

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
            .replace(/26\\s*cfr/ig, '')
            .replace(/treasury\\s+regulations?/ig, '')
            .replace(/regulations?/ig, '')
            .replace(/§/g, '')
            .replace(/[–—]/g, '-')
            .replace(/\\s+/g, '')
            .trim()
            .toLowerCase();
        const toTreasuryAnchor = (value) => `sec-${{value.replace(/§/g, '').replace(/\\s+/g, '').replace(/[().]/g, '-').replace(/--+/g, '-').replace(/^-|-$/g, '').toLowerCase()}}`;

        availableTreasurySections.forEach((value) => {{
            const normalized = normalizeTreasuryInput(String(value));
            treasurySectionMap.set(normalized, value);
            const suffix = normalized.replace(/^\\d+\\./, '');
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

    def _extract_text(self, elem: ET.Element) -> str:
        text_parts: List[str] = []
        if elem.text:
            text_parts.append(elem.text.strip())

        for child in elem:
            child_text = self._extract_text(child)
            if child_text:
                text_parts.append(child_text)
            if child.tail:
                text_parts.append(child.tail.strip())

        text = " ".join(part for part in text_parts if part)
        if not text:
            return ""
        return re.sub(r"\s+", " ", str(text)).strip()

    def export_json(self, output_path: str) -> None:
        output = {
            "metadata": {
                "source": "26 CFR (Treasury Regulations)",
                "source_code": "TREASREG",
                "total_sections": len(self.sections),
                "xml_source": self.xml_source,
            },
            "sections": [section.to_dict() for section in self.sections],
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"Exported {len(self.sections)} sections to {output_file}")

    def export_html(self, output_dir: str) -> None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self._rendered_section_numbers = [section.sectionNumber for section in self.sections]

        for section in self.sections:
            self._create_section_html(section, output_path)

        self._create_index_html(output_path)

        print(f"Exported {len(self.sections)} sections to {output_path}")

    def _create_index_html(self, output_dir: Path) -> None:
        available_sections = [section.sectionNumber for section in self.sections]
        irc_numbers = self._load_irc_section_numbers()
        toc_items = []
        for section in self.sections:
            toc_items.append(
                f'                <li class="index-list-item" style="list-style:none">'
                f'<a class="index-link" href="{section.get_anchor_id()}.html">'
                f"{section.sectionId}. {html_lib.escape(section.title)}</a></li>"
            )

        toc_html = "\n".join(toc_items)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Treasury Regulations</title>
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
            <div class="index-eyebrow">Treasury Regulations</div>
            <h1>26 CFR</h1>
            <p>Rendered Treasury regulations using the same browse shell as the IRC index.</p>
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
            <ul class="index-list">
{toc_html}
            </ul>
        </section>
    </div>
    <script>
{self._build_unified_search_script(irc_numbers, available_sections, '', '')}
    </script>
</body>
</html>"""

        index_path = output_dir / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Created index: {index_path}")

    def _split_paragraphs(self, content: str) -> List[str]:
        return [paragraph.strip() for paragraph in content.split("\n\n") if paragraph.strip()]

    @staticmethod
    def _marker_display_kind(display_id: str) -> str:
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

    def _sidebar_nodes(self, section: RegulationNode) -> List[RegulationNode]:
        roots = [sub for sub in section.subsections if sub.level == 1]
        if not roots:
            return []

        preferred_order = ["alpha-lower", "digit", "alpha-upper", "roman-lower", "roman-upper", "other"]
        kinds_present = {self._marker_display_kind(sub.displayId) for sub in roots}
        preferred_kind = next((kind for kind in preferred_order if kind in kinds_present), None)
        if preferred_kind is None:
            return roots

        filtered = [sub for sub in roots if self._marker_display_kind(sub.displayId) == preferred_kind]
        return filtered or roots

    def _render_node(self, node: RegulationNode) -> str:
        # Extract just the designator part from sectionId (e.g., "(a)(1)" from "1.61-1(a)(1)")
        # For leaf nodes that have parentheses, use only the parenthetical part as the anchor
        sectionId_str = node.sectionId
        if "(" in sectionId_str:
            # Extract everything from the first "(" onwards as the anchor
            paren_idx = sectionId_str.index("(")
            anchor_id = sectionId_str[paren_idx:].replace(")", "").replace("(", "-").strip("-").lower().replace(" ", "")
            if not anchor_id:
                anchor_id = re.sub(r"\s+", "", sectionId_str.replace("§", "")).strip()
                anchor_id = anchor_id.replace("(", "-").replace(")", "-").replace(".", "-")
                anchor_id = anchor_id.replace("--", "-").strip("-").lower()
        else:
            # No parens, use a normalized version
            anchor_id = re.sub(r"\s+", "", sectionId_str.replace("§", "")).strip()
            anchor_id = anchor_id.replace("(", "-").replace(")", "-").replace(".", "-")
            anchor_id = anchor_id.replace("--", "-").strip("-").lower()
        
        heading_margin = max(0, node.indentation)
        content_margin = heading_margin + 24
        # Decode HTML entities from XML, then properly escape for HTML output
        section_id = html_lib.unescape(node.displayId) if node.displayId else ''
        content = html_lib.unescape(node.content) if node.content else ''
        return (
            '                    <div class="subsection-wrapper">\n'
            f'                        <div class="subsection-heading level-{node.level}" id="{anchor_id}" style="margin-left: {heading_margin}px;">{html_lib.escape(section_id)}</div>\n'
            f'                        <div class="subsection-content level-{node.level}" style="margin-left: {content_margin}px;">{html_lib.escape(content)}</div>\n'
            f'{"".join(self._render_node(child) for child in node.subsections)}'
            '                    </div>\n'
        )

    def _create_section_html(self, section: RegulationNode, output_dir: Path) -> None:
        title = html_lib.escape(section.title)
        filename = f"{section.get_anchor_id()}.html"
        irc_numbers = self._load_irc_section_numbers()

        toc_items = []
        for subsection in self._sidebar_nodes(section):
            # Compute anchor_id the same way as _render_node so href matches the element id
            sid = subsection.sectionId
            if "(" in sid:
                pi = sid.index("(")
                sub_anchor = sid[pi:].replace(")", "").replace("(", "-").strip("-").lower().replace(" ", "")
                if not sub_anchor:
                    sub_anchor = re.sub(r"\s+", "", sid.replace("§", "")).strip()
                    sub_anchor = sub_anchor.replace("(", "-").replace(")", "-").replace(".", "-")
                    sub_anchor = sub_anchor.replace("--", "-").strip("-").lower()
            else:
                sub_anchor = re.sub(r"\s+", "", sid.replace("§", "")).strip()
                sub_anchor = sub_anchor.replace("(", "-").replace(")", "-").replace(".", "-")
                sub_anchor = sub_anchor.replace("--", "-").strip("-").lower()
            toc_label = subsection.displayId
            if subsection.title:
                toc_label = f"{toc_label} {subsection.title}"
            toc_items.append(
                f'                <a class="toc-link" href="#{sub_anchor}" data-target="{sub_anchor}">'
                f'<span class="toc-text">{html_lib.escape(toc_label)}</span></a>'
            )

        body_blocks: List[str] = []
        subsection_roots_by_paragraph: Dict[str, RegulationNode] = {}

        def _register_subsection_paragraphs(node: RegulationNode, root: RegulationNode) -> None:
            match = re.match(r"^(p\d+)(?:\.\d+)?$", node.identifier)
            if match:
                subsection_roots_by_paragraph.setdefault(match.group(1), root)
            for child in node.subsections:
                _register_subsection_paragraphs(child, root)

        for sub in section.subsections:
            _register_subsection_paragraphs(sub, sub)

        rendered_roots = set()
        for index, paragraph in enumerate(self._split_paragraphs(section.content), start=1):
            subsection = subsection_roots_by_paragraph.get(f"p{index}")
            if subsection:
                if subsection.identifier not in rendered_roots:
                    body_blocks.append(self._render_node(subsection))
                    rendered_roots.add(subsection.identifier)
            else:
                body_blocks.append(f'                    <div class="subsection-content">{html_lib.escape(paragraph)}</div>\n')

        metadata_lines = [
            '                    <div class="subsection-wrapper">',
            '                        <div class="subsection-heading level-1" style="margin-left: 0;">Source details</div>',
            '                        <div class="subsection-content" style="margin-left: 24px;">Source: Treasury Regulations (26 CFR)</div>',
        ]
        if section.citation:
            metadata_lines.append(f'                        <div class="subsection-content" style="margin-left: 24px;">Citation: {html_lib.escape(section.citation)}</div>')
        if section.effective_date:
            metadata_lines.append(f'                        <div class="subsection-content" style="margin-left: 24px;">Effective date: {html_lib.escape(section.effective_date)}</div>')
        if section.volume:
            metadata_lines.append(f'                        <div class="subsection-content" style="margin-left: 24px;">Volume: {html_lib.escape(section.volume)}</div>')
        metadata_lines.append('                    </div>')
        body_blocks.append("\n".join(metadata_lines))

        reg_numbers = self._rendered_section_numbers
        toc_html = "\n".join(toc_items) if toc_items else '                <div class="toc-text" style="padding: 10px 12px; color: var(--muted);">Full section text</div>'

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{section.sectionId} - {title}</title>
    <style>
        :root {{
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
            max-height: calc(100vh - var(--content-offset) - 40px);
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
            padding: 16px 12px;
        }}

        .toc-link {{
            display: block;
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

        .toc-text {{
            font-size: 13px;
            line-height: 1.45;
            color: var(--kpmg-blue);
            font-weight: bold;
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
            flex: 1 1 220px;
            min-width: 0;
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid rgba(0, 61, 165, 0.22);
            font: inherit;
            scroll-behavior: auto;
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
            scroll-margin-top: var(--content-offset);
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
        .subsection-heading.level-2 {{ font-size: 15px; border-left-width: 3px; }}
        .subsection-heading.level-3 {{ font-size: 14px; border-left-width: 2px; }}
        .subsection-heading.level-4 {{ font-size: 13px; border-left-width: 2px; }}

        .subsection-content {{
            line-height: 1.8;
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 13px;
            margin-bottom: 10px;
        }}

        @media (max-width: 980px) {{
            :root {{ --topbar-offset: 12px; }}
            body {{ padding: 18px; }}
            .reader-topbar {{ flex-direction: column; align-items: stretch; }}
            .section-nav {{ flex: 1 1 auto; align-items: stretch; }}
            .section-nav-home {{ justify-content: flex-start; }}
            .section-search {{ justify-content: flex-start; }}
            .reader-layout {{ grid-template-columns: 1fr; }}
            .reader-sidebar {{ position: static; order: -1; }}
            .section-card {{ padding: 22px 20px 28px 20px; }}
        }}
    </style>
</head>
<body id="top">
    <div class="reader-shell">
        <div class="reader-topbar">
            <div>
                <div class="reader-eyebrow">Treasury Regulations</div>
                <h1 class="reader-heading">{section.sectionId}. {title}</h1>
                <p class="reader-subheading">26 CFR</p>
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
{toc_html}
                    </div>
                    <div class="sidebar-card-footer">
                        <a class="back-to-top" href="#top">Back to top</a>
                    </div>
                </div>
            </aside>

            <main class="reader-main">
                <div class="section-card">
                    <div class="section-title">{section.sectionId}. {title}</div>
{''.join(body_blocks)}
                </div>
            </main>
        </div>
    </div>
    <script>
        const root = document.documentElement;
        const topbar = document.querySelector('.reader-topbar');
        const tocLinks = Array.from(document.querySelectorAll('.toc-link'));
        const sections = tocLinks.map((link) => document.getElementById(link.getAttribute('data-target'))).filter(Boolean);
{self._build_unified_search_script(irc_numbers, reg_numbers, '', '')}

        const syncOffsets = () => {{
            if (!topbar) {{ return; }}
            const stickyGap = parseFloat(getComputedStyle(root).getPropertyValue('--sticky-gap')) || 20;
            const topbarRect = topbar.getBoundingClientRect();
            const contentOffset = Math.ceil(topbarRect.bottom + stickyGap);
            root.style.setProperty('--content-offset', `${{contentOffset}}px`);
            document.body.style.paddingTop = `${{contentOffset}}px`;
        }};

        syncOffsets();
        window.addEventListener('load', syncOffsets);

        if ('ResizeObserver' in window && topbar) {{
            new ResizeObserver(syncOffsets).observe(topbar);
        }} else {{
            window.addEventListener('resize', syncOffsets);
        }}

        if ('IntersectionObserver' in window && tocLinks.length > 0 && sections.length > 0) {{
            const linkById = new Map(tocLinks.map((link) => [link.dataset.target, link]));
            const observer = new IntersectionObserver((entries) => {{
                const visible = entries.filter((entry) => entry.isIntersecting).sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
                if (!visible) {{
                    return;
                }}
                tocLinks.forEach((link) => link.classList.remove('is-active'));
                const activeLink = linkById.get(visible.target.id);
                if (activeLink) {{
                    activeLink.classList.add('is-active');
                }}
            }}, {{ rootMargin: '-20% 0px -60% 0px', threshold: [0.1, 0.35, 0.6] }});

            sections.forEach((sectionNode) => observer.observe(sectionNode));
            tocLinks[0]?.classList.add('is-active');
        }}
    </script>
</body>
</html>"""

        output_file = output_dir / filename
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

    @staticmethod
    def _section_sort_key(section_num: str) -> tuple:
        match = re.match(r"^(\d+)\.(\d+[A-Za-z]*)(?:-(\d+[A-Za-z]*))?", section_num)
        if not match:
            return (0, 0, 0, section_num)

        part, code_section, reg_suffix = match.groups()
        code_match = re.match(r"(\d+)([A-Za-z]*)", code_section)
        suffix_match = re.match(r"(\d+)([A-Za-z]*)", reg_suffix or "0")
        return (
            int(part),
            int(code_match.group(1)) if code_match else 0,
            code_match.group(2).lower() if code_match else "",
            int(suffix_match.group(1)) if suffix_match else 0,
            suffix_match.group(2).lower() if suffix_match else "",
            section_num,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse Treasury Regulations (26 CFR) from GovInfo XML")
    parser.add_argument(
        "xml_source",
        nargs="?",
        default=DEFAULT_XML_GLOB,
        help="Path, directory, or glob for Treasury CFR XML files",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/treasury_regs",
        help="Output directory for JSON and HTML",
    )
    parser.add_argument(
        "--format",
        choices=["json", "html", "both"],
        default="both",
        help="Output format",
    )
    parser.add_argument(
        "-s",
        "--sections",
        nargs="*",
        default=None,
        help="Specific Treasury regulation numbers to render",
    )

    args = parser.parse_args()

    try:
        treas_parser = TreasuryRegsXMLParser(args.xml_source)
        sections = treas_parser.parse(args.sections)
        if not sections:
            print("No Treasury regulations found.")
            return 1

        print(f"\n[OK] Parsed {len(sections)} Treasury Regulation sections")

        if args.format in ["json", "both"]:
            treas_parser.export_json(str(Path(args.output) / "treasury_regs.json"))

        if args.format in ["html", "both"]:
            treas_parser.export_html(str(Path(args.output) / "html"))

        print("\n[OK] Export complete")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
