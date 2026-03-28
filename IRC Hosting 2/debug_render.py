from pathlib import Path
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
import traceback

parser = TreasuryRegsXMLParser('Treasury Regulations/CFR-2025-title26-vol*.xml')
print('Parsing...')
parser.parse()
print(f'Parsed {len(parser.sections)} sections')

# Try to render a few sections
for i, s in enumerate(parser.sections[:5]):
    try:
        html = parser._render_node(s)
        print(f'[{i}] {s.sectionId} -> OK ({len(html)} chars)')
    except Exception as e:
        print(f'[{i}] {s.sectionId} -> ERROR: {type(e).__name__}: {e}')
        traceback.print_exc()
        break

print()
print("Trying to write HTML for first section...")
try:
    s = parser.sections[0]
    output_path = Path('output/treasury_regs/html')
    parser._create_section_html(s, output_path)
    print(f"Successfully created HTML for {s.sectionId}")
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    traceback.print_exc()
