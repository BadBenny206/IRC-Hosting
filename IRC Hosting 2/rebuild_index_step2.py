"""Rebuild only the unified index.html using the already-exported treasury JSON."""
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from UnifiedIndex import UnifiedIndexGenerator

print("Building unified index.html...")
gen = UnifiedIndexGenerator("IRC/usc26.xml", "output/treasury_regs.json")
gen.load_irc_sections()
gen.load_treasury_sections()
gen.generate_html("output/html")
print("Done. Written to output/html/index.html")
