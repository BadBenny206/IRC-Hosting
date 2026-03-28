import sys
sys.stdout.reconfigure(encoding='utf-8')
from TreasuryRegs_Parser_XML import TreasuryRegsXMLParser
p = TreasuryRegsXMLParser('Treasury Regulations/CFR-2025-title26-vol2.xml')
secs = p.parse(requested_sections=['1.61-1'])
if secs:
    s = secs[0]
    sys.stdout.write('sectionId: ' + repr(s.sectionId) + '\n')
    sys.stdout.write('sectionId bytes: ' + str(list(s.sectionId.encode('utf-8'))) + '\n')
else:
    sys.stdout.write('No sections found\n')
