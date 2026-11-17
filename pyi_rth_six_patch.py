# Early runtime patch for Python 3.12 + PySide6 / Shiboken6 + six compatibility
try:
    import six
    if hasattr(six, "_importer") and not hasattr(six._importer, "_path"):
        six._importer._path = None
except Exception:
    pass

