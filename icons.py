"""CleanSheet Icon Helper using qtawesome with graceful SVG/fallback rendering."""
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter
from PySide6.QtCore import Qt
try:
    import qtawesome as qta
    HAVE_QTAWESOME = True
except ImportError:
    HAVE_QTAWESOME = False


# Canonical Icon Mapping
ICON_MAP = {
    # Navigation
    "overview": "ph.chart-polar",
    "import": "ph.file-arrow-up",
    "workflow": "ph.git-merge",
    "profiles": "ph.sliders-horizontal",
    "issues": "ph.warning-circle",
    "automation": "ph.arrows-clockwise",
    "compare": "ph.git-diff",
    "history": "ph.clock-counter-clockwise",
    "reports": "ph.file-text",
    
    # Common actions
    "plus": "ph.plus",
    "search": "ph.magnifying-glass",
    "moon": "ph.moon",
    "sun": "ph.sun",
    "check": "ph.check",
    "x": "ph.x",
    "copy": "ph.copy",
    "eye": "ph.eye",
    "eye-slash": "ph.eye-slash",
    "folder": "ph.folder",
    "folder-open": "ph.folder-open",
    "play": "ph.play",
    "stop": "ph.stop",
    "refresh": "ph.arrow-counter-clockwise",
    "download": "ph.download-simple",
    "sparkles": "ph.sparkle",
    "lock": "ph.shield-check",
    "database": "ph.database",
    "table": "ph.table",
    "rows": "ph.rows",
    "columns": "ph.columns",
    "warning": "ph.warning",
    "info": "ph.info",
    "sidebar-collapse": "ph.sidebar-simple",
    "settings": "ph.gear-six",
    "help": "ph.question",
    "magic": "ph.magic-wand",
    "trend-up": "ph.trend-up",
    "shield": "ph.shield",
    "code": "ph.code",
    "dots-three": "ph.dots-three-vertical",
}

# Fallback FontAwesome icons if Phosphor is unavailable
FALLBACK_MAP = {
    "overview": "fa5s.chart-pie",
    "import": "fa5s.file-upload",
    "workflow": "fa5s.project-diagram",
    "profiles": "fa5s.sliders-h",
    "issues": "fa5s.exclamation-circle",
    "automation": "fa5s.sync",
    "compare": "fa5s.exchange-alt",
    "history": "fa5s.history",
    "reports": "fa5s.file-alt",
    "plus": "fa5s.plus",
    "search": "fa5s.search",
    "moon": "fa5s.moon",
    "sun": "fa5s.sun",
    "check": "fa5s.check",
    "x": "fa5s.times",
    "copy": "fa5s.copy",
    "eye": "fa5s.eye",
    "eye-slash": "fa5s.eye-slash",
    "folder": "fa5s.folder",
    "folder-open": "fa5s.folder-open",
    "play": "fa5s.play",
    "stop": "fa5s.stop",
    "refresh": "fa5s.redo",
    "download": "fa5s.download",
    "sparkles": "fa5s.star",
    "lock": "fa5s.lock",
    "database": "fa5s.database",
    "table": "fa5s.table",
    "rows": "fa5s.bars",
    "columns": "fa5s.columns",
    "warning": "fa5s.exclamation-triangle",
    "info": "fa5s.info-circle",
    "sidebar-collapse": "fa5s.bars",
    "settings": "fa5s.cog",
    "help": "fa5s.question-circle",
    "magic": "fa5s.magic",
    "trend-up": "fa5s.chart-line",
    "shield": "fa5s.shield-alt",
    "code": "fa5s.code",
    "dots-three": "fa5s.ellipsis-v",
}


def get_icon(name: str, color: str = "#2563EB", size: int = 16) -> QIcon:
    """Retrieve recolored icon from qtawesome or fallback blank."""
    if not HAVE_QTAWESOME:
        return QIcon()
        
    icon_key = ICON_MAP.get(name, name)
    try:
        return qta.icon(icon_key, color=color)
    except Exception:
        # Try fallback mapping
        fallback_key = FALLBACK_MAP.get(name, "fa5s.circle")
        try:
            return qta.icon(fallback_key, color=color)
        except Exception:
            return QIcon()
