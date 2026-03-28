#!/usr/bin/env python3
import re, shutil
from pathlib import Path
import server

OUTPUT_DIR = Path('test_pages')
if OUTPUT_DIR.exists():
    shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir()

def rewrite_urls(html):
    """Rewrite server URLs to static file paths"""
    html = re.sub(r'/irc\.html\?s=([^"\']+)', lambda m: f'irc_{m.group(1)}.html', html)
    html = re.sub(r'/treas\.html\?s=([^"\']+)', lambda m: f'treas_{m.group(1)}.html', html)
    html = re.sub(r'href="/"', 'href="index.html"', html)
    return html

print("Loading data...")
server.load_data()

print("Generating index.html...")
html = server.build_index_html()
html = rewrite_urls(html)
(OUTPUT_DIR / 'index.html').write_text(html, encoding='utf-8')
print('✓ index.html')

print("Generating 5 IRC sections...")
for num in server.irc_nums[:5]:
    html = server.build_irc_html(num)
    html = rewrite_urls(html)
    (OUTPUT_DIR / f'irc_{num}.html').write_text(html, encoding='utf-8')
    print(f'✓ irc_{num}.html')

print("Generating 5 Treasury sections...")
for section in server.treas_ordered[:5]:
    html = server.build_treas_html(section)
    html = rewrite_urls(html)
    fname = str(section.identifier).replace('/', '-')
    (OUTPUT_DIR / f'treas_{fname}.html').write_text(html, encoding='utf-8')
    print(f'✓ treas_{fname}.html')

files = len(list(OUTPUT_DIR.glob('*.html')))
print(f'\n✅ {files} HTML files generated in test_pages/')
