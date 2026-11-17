"""CleanSheet application entry point.

Run from this folder with: python main.py
"""
import sys

# Critical fix for Python 3.12 + PySide6 / Shiboken6 + six._SixMetaPathImporter
try:
    import six
    if hasattr(six, "_importer") and not hasattr(six._importer, "_path"):
        six._importer._path = None
except Exception:
    pass

from ui import main

if __name__ == "__main__":
    main()
