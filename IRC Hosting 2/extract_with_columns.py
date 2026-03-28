#!/usr/bin/env python3
"""
Quick utility to extract page 25 with column-aware extraction using pdfplumber
Tests different extraction methods to handle 2-column layout
"""

from pathlib import Path
import pdfplumber

pdf_path = Path("IRC/USCODE-2024-title26.pdf")

if not pdf_path.exists():
    print(f"PDF not found: {pdf_path}")
    exit(1)

print("Testing different extraction methods for page 25...\n")

with pdfplumber.open(str(pdf_path)) as pdf:
    page = pdf.pages[24]  # Page 25 (0-indexed)
    
    # Method 1: Standard extraction
    print("=" * 70)
    print("METHOD 1: Standard text extraction")
    print("=" * 70)
    text = page.extract_text()
    lines = text.split('\n')[:30]
    for i, line in enumerate(lines):
        if line.strip():
            print(f"Line {i}: {line[:80]}")
    
    # Method 2: Extract with layout
    print("\n" + "=" * 70)
    print("METHOD 2: Layout mode extraction")
    print("=" * 70)
    try:
        text_layout = page.extract_text(layout=True)
        lines_layout = text_layout.split('\n')[:40]
        for i,  line in enumerate(lines_layout[:40]):
            if line.strip():
                print(f"Line {i}: {line[:80]}")
    except Exception as e:
        print(f"Layout mode failed: {e}")
    
    # Method 3: Analyze table detection
    print("\n" + "=" * 70)
    print("METHOD 3: Table detection")
    print("=" * 70)
    
    tables = page.extract_tables()
    print(f"Tables found on page 25: {len(tables)}")
    for i, table in enumerate(tables[:2]):
        print(f"\nTable {i} (first 5 rows):")
        for row in table[:5]:
            print(f"  {row}")
    
    # Method 4: Crop and extract columns separately
    print("\n" + "=" * 70)
    print("METHOD 4: Manual column separation")
    print("=" * 70)
    
    width = page.width
    mid_point = width / 2
    
    # Left column
    left_bbox = (0, 0, mid_point, page.height)
    left_crop = page.within_bbox(left_bbox)
    left_text = left_crop.extract_text()
    
    # Right column
    right_bbox = (mid_point, 0, width, page.height)
    right_crop = page.within_bbox(right_bbox)
    right_text = right_crop.extract_text()
    
    print("LEFT COLUMN (first 10 lines):")
    for line in left_text.split('\n')[:10]:
        if line.strip():
            print(f"  {line[:70]}")
    
    print("\nRIGHT COLUMN (first 10 lines):")
    for line in right_text.split('\n')[:10]:
        if line.strip():
            print(f"  {line[:70]}")
