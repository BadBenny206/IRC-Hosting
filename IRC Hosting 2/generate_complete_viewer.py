#!/usr/bin/env python3
"""
Complete generation pipeline: Treasury + IRC -> unified output with index.
"""

import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
from IRC_Parser_XML import IRCXMLParser
from UnifiedIndex import UnifiedIndexGenerator

OUTPUT_DIR = Path("output/html")

print("=" * 70)
print("COMPLETE HTML GENERATION PIPELINE")
print("=" * 70)

# Step 1: Clean
print("\n[1/5] Cleaning old output...")
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print("✓ Output folder ready")

# Step 2: Treasury Regs
print("\n[2/5] Generating Treasury Regulations...")
try:
    treas_parser = TreasuryRegsXMLParser("Treasury Regulations/CFR-2025-title26-vol*.xml")
    treas_parser.parse()
    treas_parser.export_html(str(OUTPUT_DIR))
    treas_count = len(list(OUTPUT_DIR.glob("sec-*-*-*.html")))
    print(f"✓ Generated {treas_count} Treasury pages")
except Exception as e:
    print(f"✗ ERROR in Treasury Regs: {e}")
    raise

# Step 3: IRC
print("\n[3/5] Generating IRC sections...")
try:
    irc_parser = IRCXMLParser("USCODE-2024-title26.xml")
    irc_parser.parse()
    irc_parser.generate_html(str(OUTPUT_DIR))
    irc_count = len(list(OUTPUT_DIR.glob("sec-*.html"))) - treas_count
    print(f"✓ Generated ~{irc_count} IRC pages")
except Exception as e:
    print(f"✗ ERROR in IRC: {e}")
    raise

# Step 4: Index
print("\n[4/5] Creating unified index...")
try:
    builder = UnifiedIndexBuilder(treas_parser.sections, irc_parser.sections)
    index_html = builder.build_html()
    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    print(f"✓ Index written to {index_path.name}")
except Exception as e:
    print(f"✗ ERROR creating index: {e}")
    raise

# Step 5: Verify
print("\n[5/5] Verifying output...")
total_files = len(list(OUTPUT_DIR.glob("*.html")))
print(f"✓ Total HTML files: {total_files}")
print(f"  - index.html: {(OUTPUT_DIR / 'index.html').exists()}")
print(f"  - IRC pages (sec-*.html): {len(list(OUTPUT_DIR.glob('sec-[0-9]*.html')))}")
print(f"  - Treasury pages (sec-*-*-*.html): {len(list(OUTPUT_DIR.glob('sec-*-*-*.html')))}")

print("\n" + "=" * 70)
print("✓ GENERATION COMPLETE")
print("=" * 70)
