"""CleanSheet Modern Sidebar navigation component with animated collapse/expand."""
from typing import List, Tuple
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QCursor
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpacerItem,
    QSizePolicy, QWidget, QGraphicsDropShadowEffect
)
from theme import ThemeManager, ThemeColors
from icons import get_icon


class SidebarItem(QPushButton):
    """Refined sidebar navigation item with accent indicator on active state."""
    def __init__(self, text: str, icon_name: str, index: int, parent=None):
        super().__init__(parent)
        self.item_text = text
        self.icon_name = icon_name
        self.index = index
        self._is_active = False
        self._collapsed = False
        
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(text)
        self.setText(f"  {self.item_text}")
        self._update_appearance()
        ThemeManager.instance().subscribe(lambda _: self._update_appearance())

    def set_active(self, active: bool):
        self._is_active = active
        self._update_appearance()

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self.setText("" if collapsed else f"  {self.item_text}")
        self._update_appearance()

    def _update_appearance(self):
        c = ThemeManager.instance().colors
        self.setText("" if self._collapsed else f"  {self.item_text}")
        ico_col = c.sidebar_text_active if self._is_active else c.sidebar_text
        self.setIcon(get_icon(self.icon_name, ico_col, 18))
        self.setIconSize(QSize(18, 18))
        
        bg = c.sidebar_item_active if self._is_active else "transparent"
        fg = c.sidebar_text_active if self._is_active else c.sidebar_text
        font_weight = "600" if self._is_active else "500"
        
        border_left = f"3px solid {c.accent};" if self._is_active else "3px solid transparent;"
        
        self.setObjectName("SidebarItem")
        self.setStyleSheet(f"""
            QPushButton#SidebarItem {{
                background-color: {bg};
                color: {fg};
                border: none;
                border-left: {border_left};
                border-radius: 8px;
                padding-left: 12px;
                text-align: left;
                font-size: 13px;
                font-weight: {font_weight};
            }}
            QPushButton#SidebarItem:hover {{
                background-color: {c.sidebar_item_hover};
                color: #FFFFFF;
            }}
        """)


class ModernSidebar(QFrame):
    """Dark navy gradient sidebar with collapsible width, brand header, and bottom info."""
    nav_changed = Signal(int)
    collapse_toggled = Signal(bool)

    NAV_ITEMS: List[Tuple[str, str]] = [
        ("Overview", "overview"),
        ("Uploaded Data", "table"),
        ("Clean Data", "workflow"),
        ("Issue Review", "issues"),
        ("Compare", "compare"),
        ("History", "history"),
        ("Automation", "automation"),
        ("Reports & Export", "reports"),
    ]

    def set_item_visible(self, index: int, visible: bool):
        """Show or hide a sidebar item by its index."""
        if 0 <= index < len(self.items):
            self.items[index].setVisible(visible)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._width = 240
        self.setFixedWidth(self._width)
        self._collapsed = False
        self.items: List[SidebarItem] = []
        
        self.anim = QPropertyAnimation(self, b"sidebar_width")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 20, 14, 16)
        self.layout.setSpacing(6)
        
        # 1. Brand Header
        self._setup_brand()
        
        # 2. Navigation List
        self._setup_nav()
        
        # 3. Bottom spacer
        self.layout.addStretch(1)
        
        # 4. Bottom Workspace Info / Settings
        self._setup_bottom()
        
        self.select_index(0)

    def _get_sidebar_width(self) -> int:
        return self._width

    def _set_sidebar_width(self, w: int):
        self._width = int(w)
        self.setFixedWidth(self._width)

    sidebar_width = Property(int, _get_sidebar_width, _set_sidebar_width)

    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.anim.stop()
        self.anim.setStartValue(self._width)
        target = 72 if self._collapsed else 240
        self.anim.setEndValue(target)
        self.anim.start()
        
        # Update children
        self.brand_text_box.setVisible(not self._collapsed)
        self.bottom_card.setVisible(not self._collapsed)
        for it in self.items:
            it.set_collapsed(self._collapsed)
        self.collapse_toggled.emit(self._collapsed)

    def _setup_brand(self):
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        
        # Brand icon badge (gradient rounded square with custom app icon)
        self.brand_icon = QLabel()
        self.brand_icon.setFixedSize(32, 32)
        self.brand_icon.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1D4ED8);
            border-radius: 8px;
        """)
        self.brand_icon.setAlignment(Qt.AlignCenter)
        
        # Load custom app icon if available, otherwise fallback to sparkles
        from pathlib import Path
        import sys
        app_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
        icon_file = app_dir / "assets" / "icon.png"
        if icon_file.exists():
            from PySide6.QtGui import QPixmap
            pm = QPixmap(str(icon_file)).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.brand_icon.setPixmap(pm)
        else:
            self.brand_icon.setPixmap(get_icon("sparkles", "#FFFFFF", 18).pixmap(18, 18))
        brand_row.addWidget(self.brand_icon)
        
        self.brand_text_box = QWidget()
        b_layout = QVBoxLayout(self.brand_text_box)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(0)
        
        title = QLabel("CleanSheet")
        title.setObjectName("BrandTitle")
        
        sub = QLabel("Smart Data Cleaner")
        sub.setObjectName("BrandSubtitle")
        
        b_layout.addWidget(title)
        b_layout.addWidget(sub)
        brand_row.addWidget(self.brand_text_box, 1)
        
        self.layout.addLayout(brand_row)
        self.layout.addSpacing(16)

    def _setup_nav(self):
        for idx, (label, ico) in enumerate(self.NAV_ITEMS):
            btn = SidebarItem(label, ico, idx, self)
            btn.clicked.connect(lambda checked=False, i=idx: self._on_item_clicked(i))
            self.layout.addWidget(btn)
            self.items.append(btn)

    def _setup_bottom(self):
        self.bottom_card = QFrame()
        self.bottom_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
        """)
        b_layout = QHBoxLayout(self.bottom_card)
        b_layout.setContentsMargins(10, 8, 10, 8)
        b_layout.setSpacing(8)
        
        lock_ico = QLabel()
        lock_ico.setPixmap(get_icon("lock", "#38BDF8", 15).pixmap(15, 15))
        lock_ico.setStyleSheet("background: transparent;")
        b_layout.addWidget(lock_ico)
        
        txt = QLabel("100% Offline & Private")
        txt.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        txt.setStyleSheet("color: #CBD5E1; background: transparent;")
        b_layout.addWidget(txt, 1)
        
        self.layout.addWidget(self.bottom_card)

    def _on_item_clicked(self, idx: int):
        self.select_index(idx)
        self.nav_changed.emit(idx)

    def select_index(self, idx: int):
        for i, item in enumerate(self.items):
            item.set_active(i == idx)
