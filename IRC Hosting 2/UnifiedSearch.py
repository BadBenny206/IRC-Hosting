#!/usr/bin/env python3
"""
Unified Search and Index System for IRC + Treasury Regulations
Combines IRC sections and Treasury Regulations for integrated searching and indexing.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re


class UnifiedIndex:
    """
    Manages indexed search across both IRC sections and Treasury Regulations.
    Supports filtering by source (IRC/TREASREG) and full-text search.
    """

    def __init__(self):
        self.irc_sections: Dict[str, Dict] = {}
        self.treas_sections: Dict[str, Dict] = {}
        self.combined_index: List[Dict] = []
        self.search_index: Dict[str, List[str]] = {}  # word -> [section_ids]

    def load_irc_json(self, json_path: str) -> int:
        """Load IRC sections from JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for section in data.get("sections", []):
                section_id = section["sectionId"]
                self.irc_sections[section_id] = section
                self.combined_index.append(section)
        return len(self.irc_sections)

    def load_treasury_regs_json(self, json_path: str) -> int:
        """Load Treasury Regulations from JSON file."""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for section in data.get("sections", []):
                section_id = section["sectionId"]
                self.treas_sections[section_id] = section
                self.combined_index.append(section)
        return len(self.treas_sections)

    def build_search_index(self) -> None:
        """Build inverted word index for fast searching."""
        self.search_index.clear()

        for section in self.combined_index:
            section_id = section["sectionId"]
            # Index title and content
            text = (section.get("title", "") + " " + section.get("content", "")).lower()
            words = re.findall(r"\b\w+\b", text)

            for word in set(words):  # Use set to avoid duplicates
                if word not in self.search_index:
                    self.search_index[word] = []
                self.search_index[word].append(section_id)

    def search(
        self,
        query: str,
        source: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """
        Search across sections.
        
        Args:
            query: Search term(s)
            source: Filter by source ("IRC", "TREASREG", or None for all)
            limit: Maximum results to return
        
        Returns:
            List of matching sections
        """
        if not self.search_index:
            self.build_search_index()

        query_lower = query.lower()
        keywords = re.findall(r"\b\w+\b", query_lower)

        # Find sections containing all keywords
        matching_ids = set()
        for keyword in keywords:
            if keyword in self.search_index:
                if not matching_ids:
                    matching_ids = set(self.search_index[keyword])
                else:
                    matching_ids &= set(self.search_index[keyword])

        # Also try partial matches in section IDs and titles
        if not keywords or not matching_ids:
            for section in self.combined_index:
                section_id = section["sectionId"].lower()
                title = section.get("title", "").lower()
                if query_lower in section_id or query_lower in title:
                    matching_ids.add(section["sectionId"])

        # Filter by source if specified
        results = []
        for section in self.combined_index:
            if section["sectionId"] in matching_ids:
                if source is None or section.get("sourceCode") == source:
                    results.append(section)

        # Sort by relevance (title matches first, then content)
        def relevance_score(section):
            query_lower = query.lower()
            title = section.get("title", "").lower()
            content = section.get("content", "").lower()

            score = 0
            if query_lower in title:
                score += 100
            for keyword in keywords:
                if keyword in title:
                    score += 50
                if keyword in content:
                    score += 10

            return -score  # Negative for sorting

        results.sort(key=relevance_score)
        return results[:limit]

    def search_by_section_id(self, section_id: str) -> Optional[Dict]:
        """Get a specific section by ID."""
        for section in self.combined_index:
            if section["sectionId"] == section_id:
                return section
        return None

    def list_irc_sections(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all IRC sections."""
        sections = [s for s in self.combined_index if s.get("sourceCode") == "IRC"]
        if limit:
            sections = sections[:limit]
        return sorted(sections, key=lambda s: s.get("sectionId", ""))

    def list_treasury_regs(self, limit: Optional[int] = None) -> List[Dict]:
        """Get all Treasury Regulation sections."""
        sections = [s for s in self.combined_index if s.get("sourceCode") == "TREASREG"]
        if limit:
            sections = sections[:limit]
        return sorted(sections, key=lambda s: s.get("sectionId", ""))

    def get_related_sections(self, section_id: str, max_results: int = 5) -> List[Dict]:
        """
        Get related sections based on cross-references and content similarity.
        """
        section = self.search_by_section_id(section_id)
        if not section:
            return []

        related = []
        content = section.get("content", "").lower()

        # Extract section references (§ 1.61-1, § 162, etc.)
        section_refs = re.findall(r"§\s*(\d+\.?\d*(?:-\d+)?)", content)

        for ref in section_refs:
            # Try to find matching section
            target_id = f"§ {ref}"
            match = self.search_by_section_id(target_id)
            if match and match["sectionId"] != section_id:
                related.append(match)

        return related[:max_results]

    def export_combined_index_html(self, output_dir: str) -> None:
        """Create a master index HTML page with toggle between sources."""
        output_path = Path(output_dir) / "index.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        irc_count = len(self.irc_sections)
        treas_count = len(self.treas_sections)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IRC + Treasury Regulations - Unified Search</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Georgia', 'Garamond', serif; 
            line-height: 1.6; 
            color: #333; 
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #003366 0%, #004d80 100%);
            color: white;
            padding: 30px 20px;
            text-align: center;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .header p {{ font-size: 1.1em; opacity: 0.9; }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .search-section {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        .search-box {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}
        
        .search-box input {{
            flex: 1;
            padding: 12px 15px;
            font-size: 1em;
            border: 2px solid #ddd;
            border-radius: 4px;
            font-family: inherit;
        }}
        
        .search-box input:focus {{
            outline: none;
            border-color: #003366;
        }}
        
        .search-box button {{
            padding: 12px 25px;
            background: #003366;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            font-weight: bold;
        }}
        
        .search-box button:hover {{
            background: #004d80;
        }}
        
        .filter-tabs {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}
        
        .filter-btn {{
            padding: 10px 20px;
            background: #f0f0f0;
            border: 2px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1em;
            font-family: inherit;
            transition: all 0.3s;
        }}
        
        .filter-btn.active {{
            background: #003366;
            color: white;
            border-color: #003366;
        }}
        
        .filter-btn:hover {{
            border-color: #003366;
        }}
        
        .results {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        
        .result-card {{
            background: white;
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-left: 5px solid #003366;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .result-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        .result-card.irc {{
            border-left-color: #006600;
        }}
        
        .result-card.treasreg {{
            border-left-color: #b30000;
        }}
        
        .result-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 10px;
        }}
        
        .result-section-id {{
            font-weight: bold;
            color: #003366;
            font-size: 1.1em;
        }}
        
        .result-source {{
            display: inline-block;
            font-size: 0.8em;
            padding: 4px 8px;
            border-radius: 3px;
            font-weight: bold;
        }}
        
        .result-source.irc {{
            background: #e6f2cc;
            color: #006600;
        }}
        
        .result-source.treasreg {{
            background: #ffe6e6;
            color: #b30000;
        }}
        
        .result-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }}
        
        .result-excerpt {{
            font-size: 0.95em;
            color: #666;
            line-height: 1.5;
            max-height: 100px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .stats {{
            background: white;
            padding: 20px;
            border-radius: 6px;
            margin-bottom: 30px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .stat-box {{
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #003366;
        }}
        
        .stat-label {{
            color: #666;
            margin-top: 5px;
        }}
        
        .no-results {{
            text-align: center;
            padding: 40px;
            color: #999;
        }}
        
        footer {{
            text-align: center;
            padding: 20px;
            color: #999;
            font-size: 0.9em;
        }}
    </style>
    <script>
        let allResults = [];
        let currentFilter = 'all';
        
        function search() {{
            const query = document.getElementById('searchInput').value;
            if (!query.trim()) return;
            
            // This would call the backend search API in a full implementation
            // For now, this is a placeholder for client-side search
            console.log('Searching for:', query);
        }}
        
        function filterResults(source) {{
            currentFilter = source;
            
            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            event.target.classList.add('active');
            
            // Re-render results (placeholder)
            console.log('Filtering by source:', source);
        }}
        
        document.addEventListener('DOMContentLoaded', function() {{
            document.getElementById('searchInput')?.addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') search();
            }});
        }});
    </script>
</head>
<body>
    <div class="header">
        <h1>IRC + Treasury Regulations</h1>
        <p>Unified Search and Reference Platform</p>
    </div>
    
    <div class="container">
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{irc_count}</div>
                <div class="stat-label">IRC Sections</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{treas_count}</div>
                <div class="stat-label">Treasury Regulations</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{irc_count + treas_count}</div>
                <div class="stat-label">Total Sections</div>
            </div>
        </div>
        
        <div class="search-section">
            <div class="search-box">
                <input 
                    type="text" 
                    id="searchInput" 
                    placeholder="Search by section number (e.g., 162, 1.162-1) or keywords..."
                    style="font-size: 1.1em; padding: 14px;"
                >
                <button onclick="search()">Search</button>
            </div>
            
            <div class="filter-tabs">
                <button class="filter-btn active" onclick="filterResults('all')">All Sources</button>
                <button class="filter-btn" onclick="filterResults('IRC')">IRC Only</button>
                <button class="filter-btn" onclick="filterResults('TREASREG')">Treasury Regs Only</button>
            </div>
        </div>
        
        <div id="resultsContainer" class="results">
            <div class="no-results" style="grid-column: 1/-1;">
                <p>Enter a search term above to begin.</p>
                <p style="margin-top: 20px; font-size: 0.9em; color: #ccc;">
                    Try searching for a section number like "162" or a keyword like "income"
                </p>
            </div>
        </div>
        
        <footer>
            <p>Internal Revenue Code (IRC) + Treasury Regulations (26 CFR) Reference Platform</p>
            <p>Unified search index for integrated legal research and reference</p>
        </footer>
    </div>
</body>
</html>
"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"Created unified index: {output_path}")

    def export_search_index_json(self, output_path: str) -> None:
        """Export searchable index as JSON for frontend use."""
        if not self.search_index:
            self.build_search_index()

        output = {
            "metadata": {
                "total_irc_sections": len(self.irc_sections),
                "total_treasury_sections": len(self.treas_sections),
                "total_sections": len(self.combined_index),
            },
            "sections": [
                {
                    "id": s["sectionId"],
                    "title": s.get("title", ""),
                    "source": s.get("sourceCode", ""),
                    "source_name": s.get("source", ""),
                }
                for s in self.combined_index
            ],
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"Exported search index: {output_file}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Build unified search index for IRC + Treasury Regulations"
    )
    parser.add_argument(
        "--irc-json",
        default="output/irc/irc.json",
        help="Path to IRC JSON file",
    )
    parser.add_argument(
        "--treas-json",
        default="output/treasury_regs/treasury_regs.json",
        help="Path to Treasury Regulations JSON file",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/unified_index",
        help="Output directory for index files",
    )

    args = parser.parse_args()

    index = UnifiedIndex()

    # Load IRC
    if Path(args.irc_json).exists():
        count = index.load_irc_json(args.irc_json)
        print(f"✓ Loaded {count} IRC sections")
    else:
        print(f"⚠ IRC JSON not found: {args.irc_json}")

    # Load Treasury Regs
    if Path(args.treas_json).exists():
        count = index.load_treasury_regs_json(args.treas_json)
        print(f"✓ Loaded {count} Treasury Regulation sections")
    else:
        print(f"⚠ Treasury Regulations JSON not found: {args.treas_json}")

    # Build search index
    index.build_search_index()
    print(f"✓ Built search index with {len(index.search_index)} keywords")

    # Export
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    index.export_combined_index_html(str(output_dir))
    index.export_search_index_json(str(output_dir / "search_index.json"))

    print("\n✓ Unified index complete!")
    print(f"  Total IRC sections: {len(index.irc_sections)}")
    print(f"  Total Treasury sections: {len(index.treas_sections)}")
    print(f"  Total combined: {len(index.combined_index)}")


if __name__ == "__main__":
    main()
