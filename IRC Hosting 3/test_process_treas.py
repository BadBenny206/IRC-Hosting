import sys
sys.path.insert(0, r'C:\Users\jcargalbley\Documents\playwright\IRC Hosting 3')

# Test _process_treas_content directly
test_content = """Some intro text
[TABLE]
American Samoa, Corporation
Argentina, Sociedad Anonima  
Australia, Public Limited Company
[END TABLE]
Some more text"""

import html as html_lib

def _process_treas_content(content: str) -> str:
    """Process Treasury content, converting [TABLE] markers to HTML tables."""
    if not content or "[TABLE]" not in content:
        return html_lib.escape(content)
    
    parts = content.split("[TABLE]")
    before_table = parts[0].strip()
    html_out = ""
    if before_table:
        html_out += html_lib.escape(before_table)
    
    if len(parts) > 1:
        table_part = parts[1].split("[END TABLE]")[0].strip()
        html_out += '<div class="table-wrapper" style="margin: 12px 0;"><table style="border-collapse:collapse;width:100%;">'
        rows = [row for row in table_part.split("\n") if row.strip()]
        is_header = True
        for row in rows:
            cells = row.split(" | ")
            if is_header:
                html_out += "<thead><tr>" + "".join(f"<th style='border:1px solid #ccc;padding:8px;text-align:left;'>{html_lib.escape(cell.strip())}</th>" for cell in cells) + "</tr></thead>"
                is_header = False
            else:
                html_out += "<tr>" + "".join(f"<td style='border:1px solid #ccc;padding:8px;'>{html_lib.escape(cell.strip())}</td>" for cell in cells) + "</tr>"
        html_out += "</table></div>"
    
    return html_out

result = _process_treas_content(test_content)
print(f"Input length: {len(test_content)}")
print(f"Output length: {len(result)}")
print(f"\nOutput:")
print(result)
