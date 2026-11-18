"""CleanSheet Design System - Central Theme and Tokens.

Supports dynamic Light and Dark mode styling with strict object-name scoping,
modern typography (Inter / Segoe UI), custom scrollbars, cards, badges, and controls.
"""
from dataclasses import dataclass
import sys
from pathlib import Path
from PySide6.QtGui import QColor, QPixmap, QPainter, QPolygon, QBrush, QGuiApplication
from PySide6.QtCore import Qt, QPoint

_APP_BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
THEME_ASSETS_DIR = _APP_BASE / "assets" / "theme"


def ensure_theme_assets():
    """Ensure crisp, high-contrast arrow PNGs exist on disk for QSpinBox and QComboBox."""
    THEME_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    if QGuiApplication.instance() is None:
        return
    targets = [
        ("light", "#1E293B"),
        ("dark", "#F1F5F9"),
        ("hover", "#FFFFFF"),
    ]
    for mode, color in targets:
        up_path = THEME_ASSETS_DIR / f"arrow_up_{mode}.png"
        pix_up = QPixmap(12, 8)
        pix_up.fill(Qt.transparent)
        p = QPainter(pix_up)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(QPolygon([QPoint(2, 6), QPoint(10, 6), QPoint(6, 2)]))
        p.end()
        pix_up.save(str(up_path))
        
        down_path = THEME_ASSETS_DIR / f"arrow_down_{mode}.png"
        pix_down = QPixmap(12, 8)
        pix_down.fill(Qt.transparent)
        p = QPainter(pix_down)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(color)))
        p.drawPolygon(QPolygon([QPoint(2, 2), QPoint(10, 2), QPoint(6, 6)]))
        p.end()
        pix_down.save(str(down_path))


@dataclass(frozen=True)
class ThemeColors:
    # Surfaces
    bg: str
    surface: str
    surface_alt: str
    border: str
    border_subtle: str
    
    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    
    # Accent & States
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_subtle: str
    accent_light: str
    
    # Semantic
    success: str
    success_bg: str
    warning: str
    warning_bg: str
    danger: str
    danger_bg: str
    info: str
    info_bg: str
    
    # Sidebar
    sidebar_bg_top: str
    sidebar_bg_bottom: str
    sidebar_border: str
    sidebar_item_hover: str
    sidebar_item_active: str
    sidebar_text: str
    sidebar_text_active: str
    sidebar_muted: str
    
    # Tables / Controls
    table_header: str
    table_alt_row: str
    table_grid: str
    table_select: str
    input_bg: str
    input_border: str
    input_focus_border: str
    
    # Shadows
    shadow_color: QColor


LIGHT_THEME = ThemeColors(
    bg="#F6F7FB",
    surface="#FFFFFF",
    surface_alt="#F8FAFC",
    border="#E5E7EB",
    border_subtle="#F1F5F9",
    
    text_primary="#0F172A",
    text_secondary="#334155",
    text_muted="#64748B",
    
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_pressed="#1E40AF",
    accent_subtle="#EFF6FF",
    accent_light="#DBEAFE",
    
    success="#16A34A",
    success_bg="#DCFCE7",
    warning="#D97706",
    warning_bg="#FEF3C7",
    danger="#DC2626",
    danger_bg="#FEE2E2",
    info="#0284C7",
    info_bg="#E0F2FE",
    
    sidebar_bg_top="#0F172A",
    sidebar_bg_bottom="#111C34",
    sidebar_border="#1E293B",
    sidebar_item_hover="#1E293B",
    sidebar_item_active="#1E3A8A",
    sidebar_text="#94A3B8",
    sidebar_text_active="#FFFFFF",
    sidebar_muted="#64748B",
    
    table_header="#F8FAFC",
    table_alt_row="#F8FAFC",
    table_grid="#F1F5F9",
    table_select="#EFF6FF",
    input_bg="#FFFFFF",
    input_border="#D1D5DB",
    input_focus_border="#2563EB",
    
    shadow_color=QColor(15, 23, 42, 18),
)

DARK_THEME = ThemeColors(
    bg="#0B1220",
    surface="#111827",
    surface_alt="#1E293B",
    border="#223049",
    border_subtle="#1A263B",
    
    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    text_muted="#94A3B8",
    
    accent="#3B82F6",
    accent_hover="#2563EB",
    accent_pressed="#1D4ED8",
    accent_subtle="#1E293B",
    accent_light="#1E3A8A",
    
    success="#22C55E",
    success_bg="#14532D",
    warning="#F59E0B",
    warning_bg="#78350F",
    danger="#EF4444",
    danger_bg="#7F1D1D",
    info="#38BDF8",
    info_bg="#0C4A6E",
    
    sidebar_bg_top="#080E1A",
    sidebar_bg_bottom="#0B1324",
    sidebar_border="#1E293B",
    sidebar_item_hover="#131F37",
    sidebar_item_active="#1E3A8A",
    sidebar_text="#94A3B8",
    sidebar_text_active="#FFFFFF",
    sidebar_muted="#475569",
    
    table_header="#1A2333",
    table_alt_row="#131B2A",
    table_grid="#1E293B",
    table_select="#1E3A8A",
    input_bg="#131D2E",
    input_border="#27354D",
    input_focus_border="#3B82F6",
    
    shadow_color=QColor(0, 0, 0, 80),
)


class ThemeManager:
    _instance = None
    
    def __init__(self):
        self._is_dark = False
        self._listeners = []
        
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance
        
    @property
    def is_dark(self) -> bool:
        return self._is_dark
        
    @property
    def colors(self) -> ThemeColors:
        return DARK_THEME if self._is_dark else LIGHT_THEME
        
    def toggle_theme(self):
        self._is_dark = not self._is_dark
        self._notify()
        
    def set_dark(self, dark: bool):
        if self._is_dark != dark:
            self._is_dark = dark
            self._notify()
            
    def subscribe(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)
            
    def unsubscribe(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)
            
    def _notify(self):
        c = self.colors
        for cb in list(self._listeners):
            try:
                cb(c)
            except Exception:
                pass


def generate_stylesheet(c: ThemeColors) -> str:
    """Generate scoped Qt style sheet targeting clean components without leaky bare element selectors."""
    ensure_theme_assets()
    mode = "dark" if c.bg == DARK_THEME.bg else "light"
    up_icon = (THEME_ASSETS_DIR / f"arrow_up_{mode}.png").as_posix()
    down_icon = (THEME_ASSETS_DIR / f"arrow_down_{mode}.png").as_posix()
    hover_up = (THEME_ASSETS_DIR / "arrow_up_hover.png").as_posix()
    hover_down = (THEME_ASSETS_DIR / "arrow_down_hover.png").as_posix()
    return f"""
    /* --- Global resets and application window --- */
    QMainWindow {{
        background-color: {c.bg};
        color: {c.text_primary};
        font-family: 'Inter', 'Segoe UI', -apple-system, sans-serif;
        font-size: 13px;
    }}
    
    QWidget#CentralWidget, QWidget#MainContent, QStackedWidget#PageStack, QWidget#PageWidget {{
        background-color: {c.bg};
    }}

    /* --- Sidebar Container & Elements --- */
    QFrame#Sidebar {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {c.sidebar_bg_top}, stop:1 {c.sidebar_bg_bottom});
        border: none;
        border-right: 1px solid {c.sidebar_border};
    }}
    
    QFrame#Sidebar QLabel {{
        background: transparent;
    }}
    
    QLabel#BrandTitle {{
        color: #FFFFFF;
        font-size: 16px;
        font-weight: 700;
        letter-spacing: -0.3px;
        background: transparent;
    }}
    
    QLabel#BrandSubtitle {{
        color: {c.sidebar_muted};
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        background: transparent;
    }}
    
    /* --- Top Header Bar --- */
    QFrame#HeaderBar {{
        background-color: {c.surface};
        border-bottom: 1px solid {c.border};
    }}
    
    QFrame#HeaderBar QLabel {{
        background: transparent;
    }}
    
    QLabel#PageTitle {{
        font-size: 20px;
        font-weight: 700;
        color: {c.text_primary};
        letter-spacing: -0.4px;
        background: transparent;
    }}
    
    QLabel#PageSubtitle {{
        font-size: 12px;
        color: {c.text_muted};
        font-weight: 400;
        background: transparent;
    }}
    
    /* --- Scoped Card container & transparent inner labels --- */
    QFrame#Card, QFrame#StatCard, QFrame#ActionTile {{
        background-color: {c.surface};
        border: 1px solid {c.border};
        border-radius: 12px;
    }}

    QFrame#ActionTile:hover {{
        background-color: {c.surface_alt};
        border-color: {c.accent};
    }}
    
    QFrame#Card QLabel, QFrame#StatCard QLabel, QFrame#ActionTile QLabel {{
        background: transparent;
        color: {c.text_primary};
    }}
    
    QLabel#CardTitle, QFrame#Card QLabel#CardTitle {{
        font-size: 15px;
        font-weight: 600;
        color: {c.text_primary};
        background: transparent;
    }}
    
    QLabel#CardDesc, QFrame#Card QLabel#CardDesc, QLabel#Muted {{
        font-size: 12px;
        color: {c.text_muted};
        background: transparent;
    }}
    
    QLabel#StatValue {{
        font-size: 26px;
        font-weight: 700;
        color: {c.text_primary};
        letter-spacing: -0.5px;
        background: transparent;
    }}
    
    QLabel#StatLabel {{
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: {c.text_muted};
        background: transparent;
    }}
    
    QLabel#StatHint {{
        font-size: 11px;
        color: {c.text_muted};
        background: transparent;
    }}

    /* --- Form Controls & Inputs --- */
    QLineEdit, QComboBox, QSpinBox, QTextEdit {{
        background-color: {c.input_bg};
        color: {c.text_primary};
        border: 1px solid {c.input_border};
        border-radius: 8px;
        padding: 7px 12px;
        font-size: 13px;
        selection-background-color: {c.accent};
        selection-color: #FFFFFF;
    }}
    
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
        border: 1px solid {c.input_focus_border};
        background-color: {c.surface};
    }}
    
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
        background-color: {c.surface_alt};
        color: {c.text_muted};
        border-color: {c.border};
    }}
    
    /* --- QComboBox styling with custom arrow popup --- */
    QComboBox {{
        padding-right: 28px;
    }}
    
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 26px;
        border-left: none;
    }}

    QComboBox::down-arrow {{
        image: url("{down_icon}");
        width: 10px;
        height: 6px;
    }}
    
    QComboBox QAbstractItemView {{
        background-color: {c.surface};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        selection-background-color: {c.accent_subtle};
        selection-color: {c.accent};
        padding: 4px;
        outline: none;
    }}

    /* --- QSpinBox subcontrols and up/down arrows with prominent borders --- */
    QSpinBox {{
        padding-right: 28px;
    }}

    QSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 24px;
        height: 16px;
        border-left: 1.5px solid {c.input_border};
        border-bottom: 1.5px solid {c.input_border};
        border-top-right-radius: 7px;
        background-color: {c.surface_alt};
    }}

    QSpinBox::up-button:hover {{
        background-color: {c.accent};
        border-color: {c.accent};
    }}

    QSpinBox::up-button:pressed {{
        background-color: {c.accent_pressed};
        border-color: {c.accent_pressed};
    }}

    QSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 24px;
        height: 16px;
        border-left: 1.5px solid {c.input_border};
        border-top: 1.5px solid {c.input_border};
        border-bottom-right-radius: 7px;
        background-color: {c.surface_alt};
    }}

    QSpinBox::down-button:hover {{
        background-color: {c.accent};
        border-color: {c.accent};
    }}

    QSpinBox::down-button:pressed {{
        background-color: {c.accent_pressed};
        border-color: {c.accent_pressed};
    }}

    QSpinBox::up-arrow {{
        image: url("{up_icon}");
        width: 10px;
        height: 6px;
    }}

    QSpinBox::up-arrow:hover {{
        image: url("{hover_up}");
    }}

    QSpinBox::down-arrow {{
        image: url("{down_icon}");
        width: 10px;
        height: 6px;
    }}

    QSpinBox::down-arrow:hover {{
        image: url("{hover_down}");
    }}

    /* --- Buttons --- */
    QPushButton {{
        background-color: {c.surface};
        color: {c.text_primary};
        border: 1px solid {c.border};
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
    }}
    
    QPushButton:hover {{
        background-color: {c.surface_alt};
        border-color: {c.input_border};
    }}
    
    QPushButton:pressed {{
        background-color: {c.border};
    }}
    
    QPushButton:disabled {{
        background-color: {c.surface_alt};
        color: {c.text_muted};
        border-color: {c.border_subtle};
    }}
    
    QPushButton#PrimaryButton, QPushButton[variant="primary"] {{
        background-color: {c.accent};
        color: #FFFFFF;
        border: 1px solid {c.accent};
    }}
    
    QPushButton#PrimaryButton:hover, QPushButton[variant="primary"]:hover {{
        background-color: {c.accent_hover};
        border-color: {c.accent_hover};
    }}
    
    QPushButton#PrimaryButton:pressed, QPushButton[variant="primary"]:pressed {{
        background-color: {c.accent_pressed};
        border-color: {c.accent_pressed};
    }}
    
    QPushButton#GhostButton, QPushButton[variant="ghost"] {{
        background-color: transparent;
        color: {c.text_secondary};
        border: none;
    }}
    
    QPushButton#GhostButton:hover, QPushButton[variant="ghost"]:hover {{
        background-color: {c.accent_subtle};
        color: {c.accent};
    }}
    
    QPushButton#DangerButton, QPushButton[variant="danger"] {{
        background-color: {c.danger_bg};
        color: {c.danger};
        border: 1px solid {c.danger};
    }}
    
    QPushButton#DangerButton:hover, QPushButton[variant="danger"]:hover {{
        background-color: {c.danger};
        color: #FFFFFF;
    }}

    /* --- Custom Checkboxes (no background box, custom indicator) --- */
    QCheckBox {{
        spacing: 10px;
        color: {c.text_primary};
        font-size: 13px;
        background: transparent;
    }}
    
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 5px;
        border: 1.5px solid {c.input_border};
        background-color: {c.surface};
    }}
    
    QCheckBox::indicator:hover {{
        border-color: {c.accent};
    }}
    
    QCheckBox::indicator:checked {{
        background-color: {c.accent};
        border-color: {c.accent};
        image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' width='16' height='16' fill='none' stroke='white' stroke-width='3.5' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'></polyline></svg>");
    }}
    
    QCheckBox::indicator:disabled {{
        border-color: {c.border};
        background-color: {c.surface_alt};
    }}

    /* --- Group Boxes --- */
    QGroupBox {{
        background-color: {c.surface};
        border: 1px solid {c.border};
        border-radius: 12px;
        margin-top: 14px;
        padding: 16px;
        font-weight: 600;
        font-size: 13px;
        color: {c.text_primary};
    }}
    
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 6px;
        background-color: {c.surface};
        color: {c.text_primary};
    }}

    /* --- Tables --- */
    QTableWidget, QTableView {{
        background-color: {c.surface};
        alternate-background-color: {c.table_alt_row};
        border: 1px solid {c.border};
        border-radius: 8px;
        gridline-color: {c.table_grid};
        color: {c.text_primary};
        selection-background-color: {c.table_select};
        selection-color: {c.text_primary};
        outline: none;
    }}
    
    QTableWidget::item, QTableView::item {{
        padding: 6px 12px;
    }}
    
    QHeaderView::section {{
        background-color: {c.table_header};
        color: {c.text_secondary};
        border: none;
        border-bottom: 1px solid {c.border};
        border-right: 1px solid {c.table_grid};
        padding: 8px 12px;
        font-weight: 600;
        font-size: 12px;
    }}
    
    QTableCornerButton::section {{
        background-color: {c.table_header};
        border: none;
        border-bottom: 1px solid {c.border};
    }}

    /* --- High-Contrast Clearly Visible Scrollbars --- */
    QScrollBar:vertical {{
        background: {c.border_subtle};
        width: 12px;
        margin: 0;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical {{
        background: {c.input_border};
        min-height: 30px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background: {c.text_secondary};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
        border: none;
    }}
    
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
    }}
    
    QScrollBar:horizontal {{
        background: {c.border_subtle};
        height: 12px;
        margin: 0;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal {{
        background: {c.input_border};
        min-width: 30px;
        border-radius: 6px;
    }}
    
    QScrollBar::handle:horizontal:hover {{
        background: {c.text_secondary};
    }}
    
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
        border: none;
    }}
    
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        background: transparent;
    }}

    /* --- Status Bar --- */
    QStatusBar {{
        background-color: {c.surface};
        border-top: 1px solid {c.border};
        color: {c.text_muted};
        font-size: 12px;
        padding: 4px 16px;
    }}
    
    QStatusBar QLabel {{
        background: transparent;
        color: {c.text_muted};
    }}

    /* --- Progress Bar --- */
    QProgressBar {{
        border: none;
        background-color: {c.border_subtle};
        border-radius: 4px;
        height: 6px;
        text-align: center;
    }}
    
    QProgressBar::chunk {{
        background-color: {c.accent};
        border-radius: 4px;
    }}

    /* --- List Widgets --- */
    QListWidget {{
        background-color: {c.surface};
        border: 1px solid {c.border};
        border-radius: 8px;
        color: {c.text_primary};
        padding: 4px;
        outline: none;
    }}
    
    QListWidget::item {{
        padding: 8px 12px;
        border-radius: 6px;
        color: {c.text_primary};
    }}
    
    QListWidget::item:hover {{
        background-color: {c.surface_alt};
    }}
    
    QListWidget::item:selected {{
        background-color: {c.accent_subtle};
        color: {c.accent};
        font-weight: 600;
    }}

    /* --- Tooltips --- */
    QToolTip {{
        background-color: {c.sidebar_bg_top};
        color: #FFFFFF;
        border: 1px solid {c.sidebar_border};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}
    """
