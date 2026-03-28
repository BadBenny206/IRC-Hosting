#!/usr/bin/env python3
"""
IRC Hosting Platform - Python PDF Parser
Simplified alternative to Java/Maven build
Extracts IRC text, builds hierarchy, generates JSON and HTML
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Optional
import sys

# Try to import pdfplumber first (better for column layouts)
try:
    import pdfplumber
    PDF_LIBRARY = "pdfplumber"
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_LIBRARY = "PyPDF2"
    except ImportError:
        PDF_LIBRARY = None
        print("⚠️  PDF libraries not available. Please run:")
        print("   pip install pdfplumber")
        sys.exit(1)


class SectionNode:
    """Hierarchical IRC section node"""
    def __init__(self, section_id: str, title: str = "", level: int = 0, content: str = "", page: int = 0):
        self.sectionId = section_id
        self.title = title
        self.level = level
        self.content = content
        self.subsections: List[SectionNode] = []
        self.footnotes: List[Dict] = []
        self.crossReferences: List[Dict] = []
        self.page = page
        self.indentation = 0
        self.source = "IRC"

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict"""
        return {
            "sectionId": self.sectionId,
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "page": self.page,
            "indentation": self.indentation,
            "source": self.source,
            "footnotes": self.footnotes,
            "crossReferences": self.crossReferences,
            "subsections": [s.to_dict() for s in self.subsections]
        }

    def get_anchor_id(self) -> str:
        """Generate HTML anchor ID from section number"""
        # § 351(a)(1) -> sec-351-a-1
        normalized = self.sectionId
        normalized = re.sub(r'[§\s]', '', normalized)
        normalized = re.sub(r'[()]', '-', normalized)
        normalized = re.sub(r'-+', '-', normalized)
        normalized = normalized.strip('-').lower()
        # Remove any non-alphanumeric characters except hyphens
        normalized = re.sub(r'[^a-z0-9\-]', '', normalized)
        return f"sec-{normalized}"


class IRCParser:
    """Parse IRC PDF and extract sections"""
    
    def __init__(self, pdf_path: str, start_page: int = 25, max_pages: int = 50):
        self.pdf_path = Path(pdf_path)
        self.start_page = start_page - 1  # Convert to 0-indexed
        self.max_pages = max_pages
        self.sections: List[SectionNode] = []
        
        # Regex patterns for IRC sections - MORE LENIENT for 2-column extraction
        # Match: § 1 - Tax imposed, § 351(a) - etc.
        self.section_pattern = re.compile(r'^§?\s*(\d{1,4})\s*(?:\([^)]*\))?\s*[–-]\s*(.+)$', re.MULTILINE)
        self.subsection_pattern = re.compile(r'^\s*\(([a-z0-9]+)\)\s+(.*)$')
        self.footnote_pattern = re.compile(r'[\*†‡§¶]|\b\d{1,2}\b')
        self.crossref_pattern = re.compile(r'(?:see|see also|cf\.|compare|refer|refs)\s+(?:§|section)\s+(\d{3,4})')

    def extract_text(self) -> str:
        """Extract text from PDF with better column handling"""
        print(f"  Extracting text from {self.pdf_path}...")
        text = ""
        
        if not self.pdf_path.exists():
            print(f"  [X] PDF not found: {self.pdf_path}")
            return text

        try:
            if PDF_LIBRARY == "pdfplumber":
                import pdfplumber
                with pdfplumber.open(str(self.pdf_path)) as pdf:
                    end_page = min(self.start_page + self.max_pages, len(pdf.pages))
                    print(f"  Processing pages {self.start_page + 1} to {end_page}...")
                    for i in range(self.start_page, end_page):
                        print(f"    Page {i+1}/{end_page}...", end='\r')
                        # Use standard extraction (not layout mode) for cleaner text
                        # Layout mode preserves spacing but creates jumbled output with 2-column
                        page_text = pdf.pages[i].extract_text()
                        
                        if page_text:
                            text += f"\n[PAGE {i+1}]\n"
                            text += page_text
            else:  # PyPDF2
                reader = PdfReader(str(self.pdf_path))
                end_page = min(self.start_page + self.max_pages, len(reader.pages))
                print(f"  Processing pages {self.start_page + 1} to {end_page}...")
                for i in range(self.start_page, end_page):
                    print(f"    Page {i+1}/{end_page}...", end='\r')
                    text += f"\n[PAGE {i+1}]\n"
                    text += reader.pages[i].extract_text()
            
            print(f"\n  [OK] Extracted {len(text):,} characters")
            return text
        except Exception as e:
            print(f"  [X] Error: {e}")
            return text

    def parse_sections(self, text: str) -> List[SectionNode]:
        """Parse extracted text into section hierarchy with full body content"""
        print("  Building section hierarchy...")
        lines = text.split('\n')
        
        # Clean up PDF artifacts: remove lines that are clearly page headers/footers
        cleaned_lines = []
        for line in lines:
            # Skip overly short lines that are likely page numbers or headers
            if len(line.strip()) < 3:
                continue
            # Skip lines that look like page headers: "Page XXX" or footer patterns
            if re.match(r'^\s*page\s+\d+', line, re.IGNORECASE):
                continue
            # Skip lines with heavy repetition of dashes/equals (separator lines)
            if re.match(r'^\s*[-=]{10,}\s*$', line):
                continue
            cleaned_lines.append(line)
        
        # Find where § 1 starts and where Editorial Notes begins
        section_1_start = None
        editorial_notes_start = None
        
        for i, line in enumerate(cleaned_lines):
            # Look for § 1 with "Tax imposed" - more specific match
            if section_1_start is None and re.search(r'§\s*1\s*[–-].*[Tt]ax\s+imposed', line, re.IGNORECASE):
                section_1_start = i
                print(f"  [FOUND] § 1 - Tax imposed at line {i}")
            
            if editorial_notes_start is None and 'EDITORIAL NOTES' in line.upper():
                editorial_notes_start = i
                print(f"  Found Editorial Notes at line {i}")
        
        # Filter lines: only use content from § 1 to Editorial Notes
        if section_1_start is not None:
            if editorial_notes_start is not None:
                cleaned_lines = cleaned_lines[section_1_start:editorial_notes_start]
                print(f"  Extracting {len(cleaned_lines)} lines of actual content (§ 1 to Editorial Notes)")
            else:
                cleaned_lines = cleaned_lines[section_1_start:]
                print(f"  Extracting from line {section_1_start} to end ({len(cleaned_lines)} lines)")
        else:
            print(f"  ⚠️  § 1 - Tax imposed not found in expected format")
            print(f"  Showing first 20 lines to debug 2-column extraction:")
            for i, line in enumerate(cleaned_lines[:20]):
                if line.strip():
                    print(f"    L{i}: {line[:80]}")
        
        sections = []
        current_section: Optional[SectionNode] = None
        current_subsection: Optional[SectionNode] = None
        section_content: List[str] = []
        subsection_content: List[str] = []
        page_counter = 0

        for i, line in enumerate(cleaned_lines):
            # Track page markers
            if '[PAGE' in line:
                match = re.search(r'\[PAGE (\d+)\]', line)
                if match:
                    page_counter = int(match.group(1))
                continue

            stripped = line.strip()
            
            # Skip empty lines and section/part headings
            if not stripped:
                continue
            
            # Skip all-caps headings like "PART I—TAX ON INDIVIDUALS" or "Subtitle A—Income Taxes"
            if self._is_section_heading(stripped):
                continue

            # Check for main section header: § 1 - Tax imposed, § 351 - Transfer to Corporation, etc.
            main_match = self.section_pattern.match(stripped)
            if main_match:
                # Save previous section's accumulated content
                if current_section and section_content:
                    current_section.content = ' '.join(section_content).strip()
                    section_content = []

                section_num, title = main_match.groups()
                section_id = f"§ {section_num}"
                current_section = SectionNode(
                    section_id=section_id,
                    title=title.strip(),
                    level=0,
                    page=page_counter
                )
                sections.append(current_section)
                current_subsection = None
                print(f"    Found: {section_id}")
                continue

            # Check for subsection: (a), (1), (i), etc.
            sub_match = self.subsection_pattern.match(stripped)
            if sub_match and current_section:
                # Save previous subsection's content
                if current_subsection and subsection_content:
                    current_subsection.content = ' '.join(subsection_content).strip()
                    subsection_content = []

                marker, content = sub_match.groups()
                # Determine level based on marker type
                level = self._get_subsection_level(marker)
                current_subsection = SectionNode(
                    section_id=f"{current_section.sectionId}({marker})",
                    title=marker,
                    level=level,
                    content=content,
                    page=page_counter
                )
                current_subsection.indentation = len(line) - len(stripped)
                current_section.subsections.append(current_subsection)
                subsection_content = [content]  # Start accumulating content
                continue

            # Accumulate body content for current section or subsection
            if stripped and current_section:
                if current_subsection:
                    # We're in a subsection, accumulate to subsection
                    subsection_content.append(stripped)
                else:
                    # Section-level content
                    section_content.append(stripped)

        # Save final section/subsection content
        if current_section and section_content:
            current_section.content = ' '.join(section_content).strip()
        if current_subsection and subsection_content:
            current_subsection.content = ' '.join(subsection_content).strip()

        return sections

    def _get_subsection_level(self, marker: str) -> int:
        """Determine hierarchy level from subsection marker"""
        if marker.isalpha():  # (a), (b), ... -> level 1
            return 1
        elif marker.isdigit():  # (1), (2), ... -> level 2
            return 2
        else:  # (i), (ii), ... or (A), (B), ... -> level 3
            return 3

    def _is_section_heading(self, line: str) -> bool:
        """Check if line is a section/part heading that should be skipped"""
        if not line:
            return True
        
        # Skip all-caps headings (PART, Subtitle, etc.)
        if line.isupper() and len(line) > 5:
            # But allow single digits (these might be section titles like "TAX")
            if not any(c.isdigit() for c in line):
                return True
        
        # Skip lines that are part/subtitle structure
        if re.search(r'^(PART|SUBTITLE|CHAPTER|SUBCHAPTER|DIVISION|SUBPART|SECTION)\s+', line, re.IGNORECASE):
            return True
        
        # Skip lines with em-dash that look like structure (PART I—TAX ON INDIVIDUALS)
        if '—' in line and (line.isupper() or re.search(r'^[A-Z]{2,}', line)):
            return True
        
        return False

    def extract_metadata(self, section: SectionNode):
        """Extract footnotes and cross-references"""
        text = section.content + section.title
        
        # Find footnotes
        for match in self.footnote_pattern.finditer(text):
            section.footnotes.append({
                "marker": match.group(),
                "text": ""
            })
        
        # Find cross-references
        for match in self.crossref_pattern.finditer(text):
            section.crossReferences.append({
                "type": "section",
                "target": f"§ {match.group(1)}",
                "text": match.group(0)
            })

    def save_json(self, output_dir: Path):
        """Save sections to JSON files"""
        output_dir = Path(output_dir)
        json_dir = output_dir / "json"
        json_dir.mkdir(parents=True, exist_ok=True)

        for section in self.sections:
            self.extract_metadata(section)
            
            filename = section.get_anchor_id() + ".json"
            filepath = json_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(section.to_dict(), f, indent=2)
            
            print(f"  Saved: {filename}")

    def generate_html(self, output_dir: Path):
        """Generate HTML files from sections"""
        output_dir = Path(output_dir)
        html_dir = output_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)

        for section in self.sections:
            anchor_id = section.get_anchor_id()
            html_content = self._build_html(section)
            
            filename = anchor_id + ".html"
            filepath = html_dir / filename
            
            # Write with UTF-8 encoding to handle special characters
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"  Generated: {filename}")

    def _build_html(self, section: SectionNode) -> str:
        """Build HTML for a section with full body content"""
        anchor = section.get_anchor_id()
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{section.sectionId} - {section.title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #f5f5f5;
        }}
        header {{
            background: #1e40af;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 30px;
        }}
        h1 {{
            margin: 0;
            font-size: 28px;
        }}
        main {{
            background: white;
            padding: 30px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section-content {{
            margin-bottom: 20px;
        }}
        .section-body {{
            background: #f9f9f9;
            padding: 15px;
            border-left: 4px solid #1e40af;
            margin: 15px 0;
            border-radius: 3px;
        }}
        .subsection {{
            margin-left: 20px;
            margin-top: 20px;
            padding: 15px;
            background: #f0f8ff;
            border-radius: 3px;
        }}
        .subsection h3 {{
            margin-top: 0;
            color: #1e40af;
        }}
        .subsection-body {{
            background: white;
            padding: 10px;
            margin-top: 10px;
            border-left: 3px solid #0ea5e9;
            border-radius: 2px;
        }}
        .cross-references {{
            margin-top: 30px;
            padding: 20px;
            background: #fffbeb;
            border-radius: 5px;
        }}
        .cross-references h3 {{
            color: #92400e;
            margin-top: 0;
        }}
        .cross-references ul {{
            list-style: none;
            padding: 0;
        }}
        .cross-references li {{
            padding: 8px 0;
            border-bottom: 1px solid #fcd34d;
        }}
        .cross-references li:last-child {{
            border-bottom: none;
        }}
        .cross-references a {{
            color: #1e40af;
            text-decoration: none;
        }}
        .cross-references a:hover {{
            text-decoration: underline;
        }}
        footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
        }}
        footer a {{
            color: #1e40af;
            text-decoration: none;
        }}
        footer a:hover {{
            text-decoration: underline;
        }}
        .metadata {{
            font-size: 0.9em;
            color: #666;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <header id="{anchor}">
        <h1>{section.sectionId}: {section.title}</h1>
    </header>
    
    <main>
        <article class="section-content">
"""
        
        # Add main section content
        if section.content:
            html += f'            <div class="section-body">\n'
            html += f'                <p>{section.content}</p>\n'
            html += f'            </div>\n'
        
        # Add subsections
        if section.subsections:
            html += '            <div class="subsections">\n'
            for sub in section.subsections:
                sub_anchor = sub.get_anchor_id()
                html += f'                <section id="{sub_anchor}" class="subsection level-{sub.level}">\n'
                html += f'                    <h3>({sub.title})</h3>\n'
                if sub.content:
                    html += f'                    <div class="subsection-body">\n'
                    html += f'                        <p>{sub.content}</p>\n'
                    html += f'                    </div>\n'
                html += f'                </section>\n'
            html += '            </div>\n'
        
        # Cross-references
        if section.crossReferences:
            html += '            <div class="cross-references">\n'
            html += '                <h3>Related Sections</h3>\n'
            html += '                <ul>\n'
            for ref in section.crossReferences:
                # Safely create anchor from target
                target_num = re.sub(r'[§\s]', '', ref['target'])
                ref_anchor = f"sec-{re.sub(r'[^a-z0-9\-]', '', target_num.lower())}"
                html += f'                    <li><a href="{ref_anchor}.html#{ref_anchor}">{ref["target"]}</a></li>\n'
            html += '                </ul>\n'
            html += '            </div>\n'
        
        # Add metadata
        html += f'            <div class="metadata">\n'
        html += f'                <p><strong>Source:</strong> {section.source} | <strong>Page:</strong> {section.page}</p>\n'
        html += f'            </div>\n'
        
        html += '        </article>\n'
        html += '    </main>\n'
        html += '    \n'
        html += '    <footer>\n'
        html += '        <p><a href="index.html">← Back to Index</a></p>\n'
        html += '    </footer>\n'
        html += '</body>\n'
        html += '</html>\n'
        return html


def main():
    print("=" * 70)
    print("IRC Hosting Platform - Python PDF Parser")
    print("=" * 70)
    
    # File paths
    irc_pdf = Path("IRC/USCODE-2024-title26.pdf")
    output_dir = Path("output")
    
    if not irc_pdf.exists():
        print(f"[X] PDF not found: {irc_pdf}")
        print(f"    Expected at: {irc_pdf.absolute()}")
        return 1
    
    print(f"\n[PDF] Parsing {irc_pdf.name}...")
    
    # § 1 - Tax imposed is on page 25 with 2-column layout
    # Extract multiple pages to capture full § 1 through Editorial Notes (which starts page 32)
    # This means we need pages 25-31 (~ 7 pages)
    parser = IRCParser(str(irc_pdf), start_page=25, max_pages=8)
    
    # Extract and parse
    text = parser.extract_text()
    if not text:
        print("[X] Failed to extract text")
        return 1
    
    sections = parser.parse_sections(text)
    print(f"[OK] Found {len(sections)} main sections")
    
    if not sections:
        print("[!] No sections found. The 2-column extraction may need refinement.")
        return 1
    
    # Save outputs
    print(f"\n[SAVE] Saving output...")
    output_dir.mkdir(exist_ok=True)
    
    parser.sections = sections
    parser.save_json(output_dir)
    parser.generate_html(output_dir)
    
    print(f"\n[DONE] Complete!")
    print(f"  JSON: {(output_dir / 'json').absolute()}")
    print(f"  HTML: {(output_dir / 'html').absolute()}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
