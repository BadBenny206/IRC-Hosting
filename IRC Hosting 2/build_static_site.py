from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import unquote

import server


OUTPUT_DIR = server.HOSTING_DIR / "dist_pages"


def _treasury_filename_from_section_number(section_number: str) -> str:
    normalized = re.sub(r"\s+", "", section_number.replace("§", "")).strip()
    normalized = normalized.replace("(", "-").replace(")", "-").replace(".", "-")
    normalized = re.sub(r"-+", "-", normalized).strip("-").lower()
    return f"sec-{normalized}.html"


def _rewrite_static_links(content: str) -> str:
    content = content.replace('href="/"', 'href="index.html"')
    content = content.replace('href="/index.html"', 'href="index.html"')

    content = re.sub(
        r'href="/irc\.html\?s=([^"]+)"',
        lambda match: f'href="sec-{unquote(match.group(1)).strip().lower()}.html"',
        content,
    )
    content = re.sub(
        r'href="/treas\.html\?s=([^"]+)"',
        lambda match: f'href="{_treasury_filename_from_section_number(unquote(match.group(1)))}"',
        content,
    )

    content = content.replace(
        'window.location.href = `/treas.html?s=${encodeURIComponent(treasMatch)}`;',
        'window.location.href = `sec-${String(treasMatch).replace(/§/g, "").replace(/\\s+/g, "").replace(/[().]/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "").toLowerCase()}.html`;',
    )
    content = content.replace(
        'window.location.href = `/irc.html?s=${ircMatch}`;',
        'window.location.href = `sec-${String(ircMatch).trim().toLowerCase()}.html`;',
    )

    return content


def _write_output(filename: str, content: str) -> None:
    output_path = OUTPUT_DIR / filename
    output_path.write_text(_rewrite_static_links(content), encoding="utf-8")


def main() -> None:
    print(f"Building static site into {OUTPUT_DIR}...")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading current live app data...")
    server.load_data()

    print("Writing index.html...")
    _write_output("index.html", server.build_index_html())

    print(f"Writing {len(server.irc_nums)} IRC section pages...")
    for index, section_num in enumerate(server.irc_nums, start=1):
        html = server.build_irc_html(section_num)
        if html is None:
            continue
        _write_output(f"sec-{section_num.lower()}.html", html)
        if index % 250 == 0:
            print(f"  IRC: {index}/{len(server.irc_nums)}")

    print(f"Writing {len(server.treas_ordered)} Treasury regulation pages...")
    for index, section in enumerate(server.treas_ordered, start=1):
        _write_output(f"{section.get_anchor_id()}.html", server.build_treas_html(section))
        if index % 250 == 0:
            print(f"  Treasury: {index}/{len(server.treas_ordered)}")

    total_html = len(list(OUTPUT_DIR.glob("*.html")))
    print(f"Done. Wrote {total_html} HTML files to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()