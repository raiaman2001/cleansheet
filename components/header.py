"""CleanSheet Modern Top Header Bar with search, theme switch, sidebar toggle, and quick import."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton
)
from theme import ThemeManager, ThemeColors
from icons import get_icon
from components.widgets import PrimaryButton


class ModernHeader(QFrame):
    """Top application header bar with title breadcrumbs, search, theme toggle, and primary import CTA."""
    user_manual_clicked = Signal()
    toggle_sidebar_clicked = Signal()
    update_badge_clicked = Signal()
    search_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setFixedHeight(64)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)
        
        # Sidebar collapse button
        self.btn_collapse = QPushButton()
        self.btn_collapse.setObjectName("GhostButton")
        self.btn_collapse.setFixedSize(36, 36)
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_collapse.setToolTip("Toggle sidebar (Ctrl+B)")
        self.btn_collapse.clicked.connect(self.toggle_sidebar_clicked.emit)
        layout.addWidget(self.btn_collapse)
        
        # Page Title + Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title_box.setAlignment(Qt.AlignVCenter)
        
        self.title_lbl = QLabel("Overview")
        self.title_lbl.setObjectName("PageTitle")
        
        self.subtitle_lbl = QLabel("")
        self.subtitle_lbl.setObjectName("PageSubtitle")
        self.subtitle_lbl.setVisible(False)
        
        title_box.addWidget(self.title_lbl)
        title_box.addWidget(self.subtitle_lbl)
        layout.addLayout(title_box)
        
        layout.addStretch(1)
        
        # Update Available Pill Button (Hidden by default, shown when update detected)
        self.btn_update = QPushButton("⚡ Update Available")
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setFixedHeight(34)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10B981, stop:1 #059669);
                color: white;
                font-weight: 700;
                font-size: 11px;
                border-radius: 17px;
                padding: 0 14px;
                border: none;
            }
            QPushButton:hover {
                background: #047857;
            }
        """)
        self.btn_update.setToolTip("A new version of CleanSheet is available! Click to review & install.")
        self.btn_update.clicked.connect(self.update_badge_clicked.emit)
        self.btn_update.setVisible(False)
        layout.addWidget(self.btn_update)

        # Global Search box
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search actions, columns, or issues...")
        self.search_edit.setFixedWidth(260)
        self.search_edit.setFixedHeight(34)
        self.search_edit.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.search_edit)
        
        # Theme Toggle Button
        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("GhostButton")
        self.btn_theme.setFixedSize(36, 36)
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setToolTip("Switch Light / Dark Mode (Ctrl+Shift+T)")
        self.btn_theme.clicked.connect(ThemeManager.instance().toggle_theme)
        layout.addWidget(self.btn_theme)
        
        # User Manual button
        self.btn_manual = PrimaryButton("User Manual", icon_name="help")
        self.btn_manual.setToolTip("See simple step-by-step instructions on how to use CleanSheet")
        self.btn_manual.clicked.connect(self.user_manual_clicked.emit)
        layout.addWidget(self.btn_manual)
        
        self._update_icons(ThemeManager.instance().colors)
        ThemeManager.instance().subscribe(self._update_icons)

    def set_title(self, title: str, subtitle: str):
        self.title_lbl.setText(title)
        self.subtitle_lbl.setText(subtitle)
        self.subtitle_lbl.setVisible(bool(subtitle and subtitle.strip()))

    def show_update_badge(self, version_str: str):
        self.btn_update.setText(f"⚡ Update Available ({version_str})")
        self.btn_update.setVisible(True)

    def _update_icons(self, c: ThemeColors):
        self.btn_collapse.setIcon(get_icon("sidebar-collapse", c.text_secondary, 18))
        theme_ico = "sun" if ThemeManager.instance().is_dark else "moon"
        self.btn_theme.setIcon(get_icon(theme_ico, c.text_secondary, 18))
