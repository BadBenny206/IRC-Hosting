"""Rebuild only the unified index.html — does NOT regenerate section HTML files."""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
from UnifiedIndex import UnifiedIndexGenerator

print("Step 1: Parsing Treasury XML (JSON export only, no HTML)...")
treas = TreasuryRegsXMLParser("Treasury Regulations/CFR-2025-title26-vol*.xml")
treas.parse()
treas.export_json("output/treasury_regs.json")
print(f"  -> Saved {len(treas.sections)} sections to output/treasury_regs.json")

print("Step 2: Building unified index.html...")
gen = UnifiedIndexGenerator("USCODE-2024-title26.xml", "output/treasury_regs.json")
gen.load_irc_sections()
gen.load_treasury_sections()
gen.generate_html("output/html")
print("Done. Unified index.html written to output/html/index.html")
