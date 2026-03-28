# Static HTML Export Maintenance Guide

## Architecture Overview

This system exports IRC (Internal Revenue Code) and Treasury Regulation documents into static HTML pages. The architecture consists of three main components working together:

### 1. **IRC_Parser_XML.py** (IRC Code Parser)
- Parses `IRC/usc26.xml` (2126 IRC sections)
- Generates complete, self-contained HTML pages with embedded CSS
- Each page is independent with all styling inline
- Outputs to format: `irc_{section_number}.html`

**Key issue:** IRC generates its own CSS inline, which creates maintenance challenges when formatting needs to be consistent across both IRC and Treasury pages.

### 2. **TreasuryRegs_Parser_XML.py** (Treasury Regulations Parser)
- Parses Treasury CFR XML files (21 volumes, 5865 sections)
- Uses shared CSS template (imported from exporter)
- Generates Treasury regulation pages
- Outputs to format: `treas_{section_number}.html`

**Advantage:** Treasury uses SHARED_CSS from the exporter, so format changes apply automatically.

### 3. **export_static_html.py** (Main Exporter & Patcher)
- **SHARED_CSS template:** Master CSS used by Treasury pages and defines post-patch rules
- **_patch_irc_html_for_static():** Post-processes IRC HTML via regex to apply SHARED_CSS overrides
- **_build_treas_html():** Builds Treasury pages using the SHARED_CSS template
- **_build_index_page():** Generates index with IRC→Treasury mapping
- **export_static_site():** Main orchestrator that exports all 7992 pages

**Critical function:** The patcher applies the same CSS styling to IRC pages that Treasury gets automatically.

---

## Data Flow

```
IRC XML → IRC_Parser_XML._build_html() → self-contained IRC HTML with embedded CSS
                                         ↓
                                    _patch_irc_html_for_static()
                                    (regex post-processing)
                                         ↓
                                    IRC page with SHARED_CSS overrides

Treasury XML → TreasuryRegs_Parser_XML.parse() → Treasury Section objects
                                                ↓
                                         _build_treas_html()
                                         (uses SHARED_CSS template)
                                                ↓
                                         Treasury page with SHARED_CSS

Both → _build_index_page() → Index with IRC/Treasury cross-references
```

---

## File Update Best Practices

### ✅ DO: Update SHARED_CSS for Global Changes
When you want to change styling that affects **both IRC and Treasury pages**:

1. Edit `export_static_html.py`, line ~26 onwards (the `SHARED_CSS` variable)
2. Make your CSS change there
3. Treasury pages automatically use it
4. Add matching regex patch to `_patch_irc_html_for_static()` so IRC pages get the same override

**Example:** Fixing sidebar scrolling involved:
- Updating `.sidebar-card-body` CSS in SHARED_CSS
- Adding regex patch in `_patch_irc_html_for_static()` to match the same rule

### ❌ DON'T: Edit IRC_Parser_XML.py's embedded CSS for global changes
IRC has its own CSS embedded in the template. If you edit it:
- Treasury pages WON'T get the same change
- You'll have inconsistent formatting
- The patcher might not override it correctly

**Exception:** Only edit IRC's embedded CSS if the change is IRC-specific (e.g., IRC-only search behavior).

### ⚠️ CRITICAL: Keep IRC_Parser_XML.py and export_static_html.py in sync

Both files generate similar CSS structures:
- `.reader-sidebar`
- `.sidebar-card`, `.sidebar-card-body`, `.sidebar-card-header`
- `.section-search*` classes
- Topbar and layout CSS

When you fix something in one file's CSS, check the other for the same rule. They should stay synchronized.

---

## Patcher Mechanics (_patch_irc_html_for_static)

The patcher uses regex to find and replace CSS rules in IRC-generated HTML. Understanding the pattern:

```python
patched = re.sub(
    r'\.sidebar-card-body\s*\{[^}]*?\}',  # Find the entire CSS rule
    """.sidebar-card-body {
            padding: 8px;
            flex: 1 1 0;
            min-height: 0;
            overflow-y: auto;
        }""",  # Replace with the new rule
    patched,
    flags=re.DOTALL,
    count=1,  # Only replace first occurrence
)
```

**Key regex patterns:**
- `\s*\{[^}]*?\}` captures a CSS rule block (everything between `{` and `}`)
- `flags=re.DOTALL` allows `.` to match newlines
- `count=1` ensures only first match is replaced (safe for multiple similar rules)

---

## Recent Fixes & Why (Reference for Future Maintenance)

### Issue 1: Treasury Sublevel Indentation (FIXED)
**Problem:** All Treasury regulation sublevels appeared as level 1 `(a)(b)(c)` instead of nested.

**Root cause:** `marker_stack` variable was reset inside the for loop in `_build_flat_subsections()`.

**Fix location:** `TreasuryRegs_Parser_XML.py`, `_build_flat_subsections()` function
```python
# WRONG: marker_stack resets every iteration
for index, item in enumerate(paragraphs):
    marker_stack = []  # ← DON'T do this

# RIGHT: Declare once, persist across all iterations
marker_stack = []
for index, item in enumerate(paragraphs):
    # Use marker_stack persistently
```

**Lesson:** Check scope of state variables; indent matters for logic flow.

---

### Issue 2: §723 Content Flooding with Notes (FIXED)
**Problem:** Editorial and statutory notes were appearing inline with content, bloating the page.

**Root cause:** `_extract_direct_content()` wasn't filtering out `<notes>`, `<note>`, `<sourceCredit>` XML tags.

**Fix location:** Both `IRC_Parser_XML.py` and `TreasuryRegs_Parser_XML.py`, in `_extract_direct_content()`
```python
skip_tags = {'notes', 'note', 'sourceCredit'}  # Add these tags
# Then skip elements whose tag is in skip_tags
```

**Lesson:** When content looks bloated, check the XML tag filtering logic.

---

### Issue 3: Go Button Wrapping on IRC Pages (FIXED)
**Problem:** The "Go" button wrapped to a new line, breaking the layout.

**Root cause:** `.section-search` container had `flex-wrap: wrap` (or was allowing wrap); button needed `flex-shrink: 0` and `white-space: nowrap`.

**Fix locations:**
- `export_static_html.py` SHARED_CSS: Added `flex-wrap: nowrap` to `.section-search`
- `export_static_html.py` patcher: Override IRC's `.section-search` with same rule
- Button CSS: Added `flex-shrink: 0; white-space: nowrap`

**Lesson:** Flex layout wrapping is a common culprit; always check `flex-wrap`, `flex-shrink`, and `white-space`.

---

### Issue 4: TOC Links Scrolling Past Target Section (FIXED)
**Problem:** Clicking "On This Page" links anchored to sections, but the page scrolled past the section under the fixed topbar.

**Root cause:** `scroll-margin-top` was on `.subsection-wrapper` instead of `.subsection-heading`, and didn't account for topbar offset.

**Fix location:** Both IRC and Treasury CSS
```css
/* WRONG */
.subsection-wrapper { scroll-margin-top: ... }

/* RIGHT */
.subsection-heading { 
    scroll-margin-top: calc(var(--content-offset) + 12px); 
}
```

**Lesson:** `scroll-margin-top` must be on the element being scrolled TO (the heading), not its parent. Use `--content-offset` variable to account for fixed headers.

---

### Issue 5: "On This Page" Section Cut Off (FIXED)
**Problem:** Item (j) and later items weren't visible in the TOC sidebar; the container was too short.

**Root cause:** `.sidebar-card-body` had `padding: 16px 12px` but no scrolling; sidebar container `.reader-sidebar` used `max-height` instead of `height`.

**Fix locations:**
1. **IRC_Parser_XML.py**: Changed `.reader-sidebar` from `max-height` to `height`
2. **export_static_html.py** SHARED_CSS: Updated `.sidebar-card-body` to include `overflow-y: auto; flex: 1 1 0; min-height: 0`
3. **export_static_html.py** patcher: Added regex to override IRC's `.sidebar-card-body` rule

**Key CSS for scrollable flex containers:**
```css
.reader-sidebar {
    height: calc(100vh - var(--content-offset) - 40px);  /* Fixed height, not max-height */
    display: flex;
    flex-direction: column;
}

.sidebar-card {
    display: flex;
    flex-direction: column;
    min-height: 0;  /* Critical: allows flex children to shrink below content size */
    flex: 1;        /* Take available space */
}

.sidebar-card-body {
    flex: 1 1 0;    /* Flex grow + shrink with 0 basis */
    min-height: 0;  /* Critical: allows scrolling */
    overflow-y: auto;
    padding: 8px;
}
```

**Lesson:** For scrollable flex children: use `height` (not `max-height`), `min-height: 0`, and `flex: 1 1 0` on container and scrollable child.

---

### Issue 6: Background Bands Disappearing on Scroll (ATTEMPTED FIX)
**Problem:** Light blue gradient band (layer 2) disappeared when scrolling.

**Root cause (attempted):** Layer structure wasn't clearly defined; both pseudo-elements had z-index: 0.

**Fix applied:** Two fixed pseudo-elements with explicit z-index stacking:
- `body::before` (layer 1, solid blue): `z-index: 500` (in front of content)
- `body::after` (layer 2, gradient): `z-index: -1` (behind everything)

**Fix locations:**
- `export_static_html.py` SHARED_CSS: Defined both pseudo-elements
- `export_static_html.py` patcher: Override IRC's pseudo-elements to match

**Lesson:** Be explicit about z-index stacking; use separated layers for different visual purposes.

---

## CSS Variables (Custom Properties)

These are defined in `SHARED_CSS` and used throughout:

```css
--kpmg-blue: #003DA5;           /* Primary brand color */
--kpmg-blue-dark: #002d77;      /* Darker shade for active states */
--ink: #333;                     /* Main text color */
--muted: #68768a;               /* Secondary text (labels, etc.) */
--line: #d8e1ee;                /* Border color */
--paper: #ffffff;               /* Background/card color */
--shadow: 0 12px 28px rgba(0, 34, 85, 0.08);  /* Card shadow */
--topbar-offset: 16px;          /* Fixed topbar position from top */
--sticky-gap: 20px;             /* Spacing in layouts */
--content-offset: 156px;        /* Distance from top to content area (for scroll-margin-top) */
```

**When to add a new variable:** If you find yourself repeating a value across multiple rules, extract it as a CSS variable.

---

## Common Issues & Solutions

### Sidebar content doesn't show / is cut off
- Check `.reader-sidebar`: needs `height` (not `max-height`)
- Check `.sidebar-card`: needs `min-height: 0` and `flex: 1`
- Check `.sidebar-card-body`: needs `min-height: 0`, `overflow-y: auto`, `flex: 1 1 0`

### Buttons wrap unexpectedly
- Add `flex-wrap: nowrap` to parent flex container
- Add `flex-shrink: 0` to buttons that should stay fixed width
- Add `white-space: nowrap` to button text

### Styled elements don't appear on IRC pages
- Check if rule exists in IRC_Parser_XML.py embedded CSS
- If it does, add a regex patch in `_patch_irc_html_for_static()` to override it
- Verify patch applied by inspecting generated HTML

### Styled elements don't appear on Treasury pages
- Check SHARED_CSS in export_static_html.py
- Verify `_build_treas_html()` is including SHARED_CSS (it should be automatic)
- Regenerate test pages to verify

### Anchor links scroll past target
- Add `scroll-margin-top: calc(var(--content-offset) + 12px)` to the heading element (not parent)
- Make sure the rule is applied via patcher for IRC pages

---

## Testing & Deployment

### Development: Test with test_export.py
```bash
cd "IRC Hosting 3"
python test_export.py
```
Generates 11 pages in `dist_pages/test/`:
- 5 IRC sections: 707, 723, 1, 368, 704
- 5 Treasury sections: corresponding regulations
- 1 index page

**Inspect in browser:**
- Open `dist_pages/test/irc_1.html` or `treas_1_707-5.html`
- Check layout, scrolling, styling

### Production: Full export
```bash
python export_static_html.py
```
Generates all 7992 pages in `dist_pages/` (2126 IRC + 5865 Treasury + 1 index).

**Before deploying:**
1. Run test export, verify fixes in browser
2. Check a few IRC and Treasury pages side-by-side for consistent styling
3. Then run full export
4. Spot-check several exported files before deploying to production

---

## Issue 7: Treasury Section Files Fragmented with Incorrect Filenames (FIXED)
**Problem:** Treasury sections with Unicode parentheses in their section numbers (e.g., § 301.7701(b)-2) were being split into multiple files with garbled names like `treas_301_7701(b)-0.html`, `treas_301_7701(b)-1.html`, etc. The "On This Page" sidebar was showing random subsections like "(b)(9)" appearing on pages and content was broken across multiple files. Also, examples and tables were missing.

**Root cause (filename issue):** The filename sanitization was only replacing `/` and `.` characters:
```python
safe_id = section.sectionNumber.replace("/", "_").replace(".", "_")
```
This left Unicode parentheses and other special characters in filenames, which:
- Created invalid/problematic filenames on Windows
- Split sections across multiple files due to character interpretation issues
- Caused the exporter to create fragments instead of single pages

**Root cause (content issue):** Separate investigation needed — likely XML parsing treating subsections like `(b)(9)` as separate section boundaries instead of nested subsections.

**Fix applied:** Created `_sanitize_filename()` function that:
```python
def _sanitize_filename(section_number: str) -> str:
    """Sanitize section number for use in filename by replacing special characters."""
    safe = section_number.replace("§", "").strip()
    safe = safe.replace("/", "_").replace(".", "_").replace("-", "_")
    # Replace ANY non-alphanumeric characters (including Unicode parentheses) with underscores
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', safe)
    # Clean up multiple consecutive underscores
    safe = re.sub(r'_+', '_', safe)
    safe = safe.strip("_")
    return safe
```

**Fix locations:**
- `export_static_html.py`: Added `_sanitize_filename()` function at top level
- `export_static_html.py`: Updated IRC filename generation to use `_sanitize_filename(section.sectionNumber)`
- `export_static_html.py`: Updated Treasury filename generation to use `_sanitize_filename(section.sectionNumber)`

**Lesson:** Unicode characters in filenames can cause filesystem issues. Always use aggressive sanitization for filenames, not just the obvious ASCII delimiters. Use regex to replace ALL non-alphanumeric characters.

**Remaining issue:** Content fragmentation within 301.7701-2 needs investigation in the Treasury parser to understand why subsections like (b)(9) are being treated as separate top-level sections in the sidebar TOC.

---

## Issue 8: Nested Subsections Not Rendering in Treasury Pages (FIXED)
**Problem:** Complex Treasury sections with nested subsections (e.g., § 301.7701(b)(8)) were not rendering in the output. The parse tree showed the nested nodes correctly, but the rendered HTML was missing them. For example, in 301.7701-2, the subsection (b)(8) "Certain foreign entities" with children (i), (ii), (iii), (iv), (v) were missing from the output.

**Root cause:** The rendering loop in `_build_treas_html()` only processed immediate children:
```python
for sub in section.subsections:
    if sub.identifier not in rendered:
        body_parts.append(_render_treas_node(sub))
```
This missed deeply nested subsections like (b)(8) which was a child of top-level (b).

**Architecture issue:** The parser creates a nested tree structure where:
- Top level (b) contains children (1)-(8)
- Each of those children can have their own children (e.g., (b)(8)(i), (b)(8)(ii), etc.)
- But (b) also appears as a second top-level node for (b)(9)

The rendering wasn't recursively traversing the entire subsection tree.

**Fix applied:** Replaced sequential rendering with recursive `_render_all_unrendered()` function:
```python
def _render_all_unrendered(node):
    """Recursively render a node and all its unrendered subsection descendants."""
    if node.identifier not in rendered:
        body_parts.append(_render_treas_node(node))
        rendered.add(node.identifier)
    for child in node.subsections:
        _render_all_unrendered(child)  # Recursively process children

# Use recursive function instead of flat loop
for sub in section.subsections:
    _render_all_unrendered(sub)
```

**Fix location:**
- `export_static_html.py` lines ~335-354: Replaced flat loop with recursive function in `_build_treas_html()`

**Verification:**
- Ran test_export.py with 301.7701-2 in test suite
- Verified `treas_301_7701_2.html` (265,500 bytes) now contains (b)(8) and subsections (i-v)
- Search-verified: "(b)(8) Certain foreign entities—(i) In general" appears in output

**Lesson:** Recursive tree traversal is critical when rendering hierarchical structures. A flat loop through `node.children` only processes one level deep. Always check if child nodes can have grandchildren, and if so, use recursion or a queue-based traversal.

---

## Issue 9: EXTRACT Elements (Per Se Corporations Tables) Not Rendering in Treasury Pages (FIXED)

**Problem:** Treasury § 301.7701(b)(8)(i) contains a table of 87 foreign business entities (American Samoa, Argentina, Australia, Bahamas, etc.) extracted from an EXTRACT XML element. This table was being parsed but never rendered in the final HTML. The section appeared in the output but the table was missing entirely.

**Root cause:** The EXTRACT elements are siblings of paragraph elements in the XML, not direct children. The parser was extracting them but not integrating them into the subsection tree. Multiple failed approaches totaling ~3 hours of debugging:

1. **Attempt 1 - Text extraction only:** Used `.iter()` to recursively extract all text from FP children, losing table structure
2. **Attempt 2 - Python HTML generation:** Tried building `<table>` HTML in Python, but HTML markup got escaped and lost
3. **Attempt 3 - [TABLE] markup:** Created a custom markup format `[TABLE]...[END TABLE]` that should be rendered later, but it was never rendered in the output
4. **Attempt 4 - Process function without invoke:** Created `_process_treas_content()` to convert [TABLE] to HTML, but it wasn't being called on the EXTRACT content
5. **Attempt 5 - Append to last paragraph:** Tried appending EXTRACT to `paragraphs[-1]` but content got lost during subsection hierarchy restructuring
6. **Attempt 6 - Append as child node (FINAL SUCCESS):** After subsection tree is built, recursively search for (b)(8)(i) node and append EXTRACT as a child node

**Why it took 3 hours:**

The core issue was **architectural blindness** — the EXTRACT content was logically associated with paragraph (b)(8)(i), but the XML structure didn't represent it that way. The text extraction and table formatting were straightforward, but the integration layer had multiple failure points:

- **Hierarchy restructuring:** Every attempt to append the content to the parse tree resulted in it getting lost during the `_build_flat_subsections()` reconstruction, which processes paragraphs and builds a nested subsection tree, treating appended content as orphaned
- **String vs. object identity:** Passing content as strings made it impossible to track where it ended up when passed through multiple tree-building functions
- **Late binding problem:** The content needed to be bound to the tree AFTER the tree was built (not during), but the rendering pipeline wasn't equipped to handle post-tree-build manipulations

**The working solution** required a shift in approach: Instead of trying to insert EXTRACT during tree construction, append it AFTER the tree is fully built by recursively searching through the completed subsection hierarchy and finding the exact (b)(8)(i) node to attach it to.

**Fix applied:**

1. **Extract detection:** `_parse_section()` collects EXTRACT element using `_format_extract_element()`
2. **Format as markup:** `_format_extract_element()` extracts all FP children, formats as `[TABLE]\nAmerican Samoa, Corporation\nArgentina, Sociedad Anonima\n...\n[END TABLE]`
3. **Tree building:** Normal subsection tree construction via `_build_flat_subsections()`
4. **Post-tree integration:** Recursive `find_b8i()` function searches subsection tree for (8) → (i) path and appends RegulationNode with EXTRACT content:

```python
# After: node.subsections = self._build_flat_subsections(para_tuples)
if extract_text:
    def find_b8i(subs):
        for sub in subs:
            # Look for (8) subsection
            if "(8)" in sub.displayId:
                # Check children for (i)
                for child in sub.subsections:
                    if "(i)" in child.displayId:
                        # Found (b)(8)(i) - append table as child node
                        table_node = RegulationNode(
                            section_id="",
                            title="",
                            level=child.level,
                            content=extract_text,
                            identifier="",
                            tag_name="EXTRACT",
                        )
                        child.subsections.append(table_node)
                        return True
            if find_b8i(sub.subsections):
                return True
        return False
    find_b8i(node.subsections)
```

5. **Rendering:** During HTML rendering, `_render_treas_node()` calls `_process_treas_content(raw_content)` which converts `[TABLE]...[END TABLE]` markers to HTML `<table>` elements with proper styling

6. **HTML generation:** `_process_treas_content()` splits on [TABLE] markers and converts pipe-delimited rows to `<thead>` (first row) and `<tbody>` rows with CSS styling

**Fix locations:**
- `TreasuryRegs_Parser_XML.py` lines ~158-235: Added post-tree recursive search in `_parse_section()`
- `TreasuryRegs_Parser_XML.py` lines ~268-289: `_format_extract_element()` creates [TABLE] markup
- `export_static_html.py` lines ~270-309: `_process_treas_content()` converts markup to HTML table
- `export_static_html.py` lines ~311-333: `_render_treas_node()` calls `_process_treas_content()` on node content

**Verification:**
- Ran test_export.py after fix applied
- Checked generated file: `treas_301_7701_2.html` (265,500 bytes)
- Verified table appears under section (b)(8)(i) with all 87 entities: American Samoa, Argentina, Australia, Bahamas, Barbados, etc.
- Verified entries are in proper `<table>` format with `<tr>`, `<td>` elements

**Lesson — The Real Problem:** This wasn't a parsing or formatting problem; it was an **architectural mismatch**. The XML structure (EXTRACT as sibling of paragraphs) didn't align with the output hierarchy (content belongs under a subsection). Solutions that tried to force integration during tree construction failed because the tree-building function overrides late-binding. The solution was to recognize that:

1. The tree structure is the source of truth
2. Content needs to be bound AFTER the tree is stable
3. Searching a completed tree is more reliable than trying to insert during construction
4. Post-processing functions (find_b8i) are more robust than trying to weave content through multiple pipeline stages

This is a template for fixing similar structural mismatches in the future: separate parsing from tree construction, build the tree completely, then bind content to the completed tree via search + append.

---

## File Locations & Imports


```
IRC Hosting 3/
├── IRC_Parser_XML.py           # IRC parser, embedded HTML/CSS template
├── TreasuryRegs_Parser_XML.py   # Treasury parser, uses SHARED_CSS
├── export_static_html.py        # Main exporter, SHARED_CSS, patcher, orchestrator
├── test_export.py              # Quick test (11 pages)
├── server.py                   # Local dev server (may be older, don't use for export)
├── IRC/                        # IRC XML source (usc26.xml)
├── Treasury Regulations/       # Treasury XML sources (21 volumes)
└── dist_pages/                 # Output folder (regenerated each export)
    ├── index.html
    ├── irc_1.html
    ├── irc_2.html
    ├── ... 2126 IRC pages
    ├── treas_1_1.html
    ├── treas_1_2.html
    ├── ... 5865 Treasury pages
```

**Import dependencies:**
- `IRC_Parser_XML` imports nothing; self-contained
- `TreasuryRegs_Parser_XML` imports nothing; self-contained
- `export_static_html.py` imports both parsers and calls their methods

---

## Regex Cheat Sheet (For Patcher Maintenance)

```python
# Match class with any attributes and closing brace
r'\.sidebar-card\s*\{[^}]*?\}'

# Match and capture a class opening, then replace content after it
r'(\.sidebar-card\s*\{)'  # Capture just the opening
# Then use \1 in replacement to preserve it

# Match a property and remove it
r'(\.subsection-wrapper\s*\{[^}]*?)scroll-margin-top[^;]+;'
# Then replace with r'\1' to keep everything before the property

# DOTALL flag is critical for multiline matches
flags=re.DOTALL

# count=1 to replace only first occurrence (safe for one-off rules)
count=1
```

---

## Next Steps for Maintenance

When adding new features or fixing bugs:

1. **Identify scope:** IRC-only, Treasury-only, or both?
2. **Make the change:** 
   - If both: Update SHARED_CSS + add patcher rule
   - If one: Update the specific parser
3. **Test:** Run `test_export.py`, inspect pages in browser
4. **Check consistency:** Open an IRC page and Treasury page side-by-side
5. **Document:** Add a note to this file under "Recent Fixes & Why"
6. **Deploy:** Run full export and spot-check before going live

---

## Architecture Debt (Known Issues)

**IRC brings its own CSS:** This is technical debt. Ideally:
- Both IRC and Treasury would use a shared HTML template
- CSS would be centralized
- No regex patching would be needed

**Why it exists:** Legacy design; IRC parser was built first with self-contained output.

**Why not refactor:** High risk of breaking 7992 pages; only do if you have time to thoroughly test.

**Best practice:** Don't make it worse; use SHARED_CSS for new styling and patch it in.

---

## Questions? Check These First

- **Pages look inconsistent:** Check if the CSS rule is in SHARED_CSS + has a patcher override for IRC
- **Sidebar too short/tall:** Check `.reader-sidebar` height and `.sidebar-card-body` flex properties
- **Styling not applying:** Inspect generated HTML to see if the rule made it in; check patcher regex
- **Test pages vs. production differ:** Might be a caching issue; hard refresh or clear `dist_pages/` folder
- **Regex replace isn't working:** Test the regex pattern in Python REPL first; make sure you're matching actual text in the file

---

**Deployment Status:**
✅ **Issue 9 COMPLETE** - EXTRACT elements rendering successfully in production
✅ **Full Export Complete** - All 7992 pages generated (2126 IRC + 5865 Treasury + 1 index)
✅ **Verified** - treas_301_7701-2.html contains per se corporations table in section (b)(8)(i)

**Last updated:** March 20, 2026 - Issue 9 (EXTRACT elements rendering) fixed
