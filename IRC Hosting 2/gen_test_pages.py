#!/usr/bin/env python3
from IRC_Parser_XML import IRCXMLParser
from pathlib import Path
import shutil

out = Path('test_pages')
if out.exists():
    shutil.rmtree(out)
out.mkdir()

try:
    parser = IRCXMLParser('USCODE-2024-title26.xml')
    print('✓ Parser created')
    parser.parse()
    print(f'✓ {len(parser.sections)} sections parsed')
    
    for i, sec in enumerate(parser.sections[:5]):
        fn = sec.get_anchor_id() + '.html'
        html = parser._build_html(sec)
        (out / fn).write_text(html, encoding='utf-8')
        print(f'✓ {i+1}. {fn}')
    
    parser.generate_index_html(out)
    print('✓ index.html generated')
    
    files = len(list(out.glob('*.html')))
    print(f'\n✅ {files} files created in test_pages/')
    
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
