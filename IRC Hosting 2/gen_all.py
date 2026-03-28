#!/usr/bin/env python3
import shutil
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
from IRC_Parser_XML import IRCXMLParser

OUTPUT_DIR = Path("output/html")

print("=" * 70)
print("COMPLETE GENERATION")
print("=" * 70)

print("\n[1/3] Cleaning...")
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print("✓ Ready")

print("\n[2/3] Treasury Regulations...")
treas_parser = TreasuryRegsXMLParser("Treasury Regulations/CFR-2025-title26-vol*.xml")
treas_parser.parse()
treas_parser.export_html(str(OUTPUT_DIR))
treas_count = len(list(OUTPUT_DIR.glob("sec-*-*-*.html")))
print(f"✓ {treas_count} Treasury pages")

print("\n[3/3] IRC Sections...")
irc_parser = IRCXMLParser("USCODE-2024-title26.xml")
irc_parser.parse()
irc_parser.generate_html(str(OUTPUT_DIR))
irc_count = len(list(OUTPUT_DIR.glob("sec-[0-9]*.html")))
print(f"✓ {irc_count} IRC pages")

# Create minimal index
index_html = """<!DOCTYPE html>
<html><head><title>IRC & Treasury</title>
<style>body{font-family:Arial;max-width:900px;margin:0 auto;padding:20px;background:#f5f5f5}
h1{color:#003DA5}a{color:#003DA5;text-decoration:none}a:hover{text-decoration:underline}</style>
</head><body><h1>IRC & Treasury Regulations Viewer</h1>
<p>Consolidated local viewer with ~8000 pages. Use search in your browser or navigate directly.</p>
<p><a href="sec-1.html">Start with IRC § 1</a> | <a href="sec-1-61-1.html">Start with Treasury Reg § 1.61-1</a></p>
</body></html>"""
(OUTPUT_DIR / "index.html").write_text(index_html)

print("\n" + "=" * 70)
total = len(list(OUTPUT_DIR.glob("*.html")))
print(f"✓ COMPLETE: {total} total HTML files")
print(f"✓ Location: {OUTPUT_DIR.absolute()}")
print("=" * 70)
