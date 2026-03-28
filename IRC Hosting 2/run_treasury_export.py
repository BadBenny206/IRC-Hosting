import shutil
import traceback
from pathlib import Path
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser

log = Path("output/treasury_regs/python_render_log.txt")
count_file = Path("output/treasury_regs/python_render_count.txt")

print("Removing old Treasury HTML files from output/html...")
html_dir = Path("output/html")
if html_dir.exists():
    for f in html_dir.glob("sec-*-*-*.html"):
        f.unlink()

print("Creating parser...")
parser = TreasuryRegsXMLParser("Treasury Regulations/CFR-2025-title26-vol*.xml")

try:
    print("Parsing all volumes...")
    parser.parse()
    print(f"Parsed {len(parser.sections)} sections. Starting HTML export...")
    parser.export_html("output/html")
    final_count = len(list(Path("output/html").glob("sec-*-*-*.html")))
    count_file.write_text(str(final_count), encoding="utf-8")
    log.write_text("OK", encoding="utf-8")
    print(f"Done. {final_count} pages written.")
except Exception:
    err = traceback.format_exc()
    log.write_text(err, encoding="utf-8")
    print("ERROR:")
    print(err)
    raise
