#!/usr/bin/env python3
"""Simple wrapper to run export_static_html.py"""
import sys
import subprocess

try:
    result = subprocess.run([sys.executable, "export_static_html.py"], 
                          capture_output=False, text=True, timeout=600)
    sys.exit(result.returncode)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
