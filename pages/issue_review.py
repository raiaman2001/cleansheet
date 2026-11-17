"""CleanSheet Issue Review Page.

Displays data quality findings with colored severity badges, category filter chips with live counts,
right-hand side detail panel, and polished empty state.
"""
from typing import Callable, Optional
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidgetItem,
    QStackedWidget, QFrame, QScrollArea
)
from components.widgets import Card, PrimaryButton, Badge, EmptyState
from components.table import ModernTable
from theme import ThemeManager, ThemeColors
from icons import get_icon


class FilterChip(QPushButton):
    """Clickable category filter chip tab with count badge."""
    def __init__(self, category: str, count: int = 0, parent=None):
        super().__init__(parent)
        self.category = category
        self.count = count
        self._active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self._update_label()
        ThemeManager.instance().subscribe(lambda _: self._update_style())

    def set_count(self, count: int):
        self.count = count
        self._update_label()

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_label(self):
        self.setText(f"{self.category} ({self.count})")
        self._update_style()

    def _update_style(self):
        c = ThemeManager.instance().colors
        bg = c.accent if self._active else c.surface
        fg = "#FFFFFF" if self._active else c.text_secondary
        border = c.accent if self._active else c.border
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: {'600' if self._active else '500'};
            }}
            QPushButton:hover {{
                background-color: {c.accent if self._active else c.surface_alt};
            }}
        """)


class IssueReviewPage(QWidget):
    """Issue Review page with category chips, findings table with severity pills, and side inspector."""
    issue_status_updated = Signal(str)
    fuzzy_matches_requested = Signal()
    export_issues_requested = Signal()
    refresh_analysis_requested = Signal()
    import_requested = Signal()

    CATEGORIES = [
        "All issues",
        "Missing values",
        "Duplicate records",
        "Potential outliers",
        "Business-rule warnings",
        "Schema validation",
        "Inconsistent categories",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.issues_df: Optional[pd.DataFrame] = None
        self.current_category = "All issues"
        self.chips = {}
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Header Row with Action Buttons
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        
        category_label = QLabel("Filter by Issue Type")
        category_label.setObjectName("CardTitle")
        header_row.addWidget(category_label)
        header_row.addStretch(1)
        
        self.btn_refresh = QPushButton("Re-check Issues")
        self.btn_refresh.setIcon(get_icon("refresh", "#64748B", 14))
        self.btn_refresh.clicked.connect(self.refresh_analysis_requested.emit)
        header_row.addWidget(self.btn_refresh)
        
        self.btn_export = QPushButton("Save Issues List")
        self.btn_export.setIcon(get_icon("download", "#64748B", 14))
        self.btn_export.clicked.connect(self.export_issues_requested.emit)
        header_row.addWidget(self.btn_export)
        
        main_layout.addLayout(header_row)
        
        # 2. Category Chips Bar (Horizontal scroll with mouse-wheel support)
        chip_scroll = QScrollArea()
        chip_scroll.setWidgetResizable(True)
        chip_scroll.setFixedHeight(44)
        chip_scroll.setFrameShape(QFrame.NoFrame)
        chip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        chip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        chip_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 4px; background: transparent; }
            QScrollBar::handle:horizontal { background: #CBD5E1; border-radius: 2px; }
        """)
        
        chips_container = QWidget()
        chips_container.setStyleSheet("background: transparent;")
        chips_layout = QHBoxLayout(chips_container)
        chips_layout.setContentsMargins(0, 2, 0, 2)
        chips_layout.setSpacing(8)
        
        for cat in self.CATEGORIES:
            chip = FilterChip(cat, 0, self)
            chip.clicked.connect(lambda checked=False, c=cat: self._on_chip_clicked(c))
            chips_layout.addWidget(chip)
            self.chips[cat] = chip
        self.chips["All issues"].set_active(True)
        chips_layout.addStretch(1)
        
        chip_scroll.setWidget(chips_container)
        main_layout.addWidget(chip_scroll)
        
        # 2. Body Stack: Empty State vs Main Content
        self.body_stack = QStackedWidget()
        
        # View 0: Empty state
        self.empty_view = EmptyState(
            "issues",
            "No Data Issues Found",
            "Upload a spreadsheet and click 'Start Cleaning' to review potential problems, unusual numbers, and formatting suggestions.",
            "Choose a Spreadsheet",
            self
        )
        self.empty_view.action_clicked.connect(self.import_requested.emit)
        self.body_stack.addWidget(self.empty_view)
        
        # View 1: Main Table + Right Details Inspector
        content_widget = QWidget()
        cw_layout = QHBoxLayout(content_widget)
        cw_layout.setContentsMargins(0, 0, 0, 0)
        cw_layout.setSpacing(16)
        
        self.table = ModernTable()
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        cw_layout.addWidget(self.table, 2)
        
        # Right Side Detail Panel
        self.detail_card = Card(elevation=False)
        self.detail_card.setMinimumWidth(300)
        self.detail_card.setMaximumWidth(360)
        d_layout = QVBoxLayout(self.detail_card)
        d_layout.setContentsMargins(20, 18, 20, 18)
        d_layout.setSpacing(14)
        
        dt = QLabel("Issue Details")
        dt.setObjectName("CardTitle")
        d_layout.addWidget(dt)
        
        self.insp_category = Badge("Category", "neutral")
        d_layout.addWidget(self.insp_category)
        
        self.insp_col = QLabel("Column: --")
        self.insp_col.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        d_layout.addWidget(self.insp_col)
        
        self.insp_details = QLabel("Click any issue in the table to see details and suggestions here.")
        self.insp_details.setObjectName("CardDesc")
        self.insp_details.setWordWrap(True)
        d_layout.addWidget(self.insp_details)
        
        d_layout.addStretch(1)
        
        # Inspector Action Buttons
        act_box = QVBoxLayout()
        act_box.setSpacing(8)
        
        self.btn_mark_reviewed = QPushButton("✓ Mark as Reviewed")
        self.btn_mark_reviewed.clicked.connect(lambda: self.issue_status_updated.emit("Reviewed"))
        act_box.addWidget(self.btn_mark_reviewed)
        
        self.btn_ignore = QPushButton("Ignore This Issue")
        self.btn_ignore.clicked.connect(lambda: self.issue_status_updated.emit("Ignored"))
        act_box.addWidget(self.btn_ignore)
        
        self.btn_fuzzy = PrimaryButton("Fix Similar Spelling Errors", icon_name="magic")
        self.btn_fuzzy.clicked.connect(self.fuzzy_matches_requested.emit)
        act_box.addWidget(self.btn_fuzzy)
        
        d_layout.addLayout(act_box)
        cw_layout.addWidget(self.detail_card, 1)
        
        self.body_stack.addWidget(content_widget)
        main_layout.addWidget(self.body_stack, 1)

    def _on_chip_clicked(self, category: str):
        self.current_category = category
        for cat, chip in self.chips.items():
            chip.set_active(cat == category)
        self._render_table()

    def set_issues_data(self, df: Optional[pd.DataFrame]):
        self.issues_df = df
        if df is None or df.empty:
            self.body_stack.setCurrentIndex(0)
            for chip in self.chips.values():
                chip.set_count(0)
            return
            
        self.body_stack.setCurrentIndex(1)
        
        # Update chip counts
        self.chips["All issues"].set_count(len(df))
        for cat in self.CATEGORIES[1:]:
            if "Category" in df.columns:
                count = int((df["Category"] == cat).sum())
            else:
                count = 0
            self.chips[cat].set_count(count)
            
        self._render_table()

    def _render_table(self):
        if self.issues_df is None or self.issues_df.empty:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return
            
        filtered = self.issues_df.copy()
        if self.current_category != "All issues" and "Category" in filtered.columns:
            filtered = filtered[filtered["Category"] == self.current_category]
            
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setRowCount(len(filtered))
        self.table.setColumnCount(len(filtered.columns))
        self.table.setHorizontalHeaderLabels([str(c) for c in filtered.columns])
        
        for r in range(len(filtered)):
            for c in range(len(filtered.columns)):
                val = filtered.iloc[r, c]
                txt = "" if pd.isna(val) else str(val)
                item = QTableWidgetItem(txt)
                
                # Severity coloring for Category / Review status
                col_name = str(filtered.columns[c])
                c_theme = ThemeManager.instance().colors
                if col_name == "Category":
                    if txt in ("Business-rule warnings", "Schema validation"):
                        item.setForeground(QColor(c_theme.danger))
                    elif txt in ("Missing values", "Potential outliers"):
                        item.setForeground(QColor(c_theme.warning))
                elif col_name == "Review status":
                    if txt == "Reviewed":
                        item.setForeground(QColor(c_theme.success))
                    elif txt == "Ignored":
                        item.setForeground(QColor(c_theme.text_muted))
                        
                self.table.setItem(r, c, item)
                
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _on_selection_changed(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected or self.issues_df is None:
            self.insp_category.set_text_and_variant("None", "neutral")
            self.insp_col.setText("Column: --")
            self.insp_details.setText("Select an issue row on the left to inspect recommended actions.")
            return
            
        row = selected[0].row()
        filtered = self.issues_df.copy()
        if self.current_category != "All issues" and "Category" in filtered.columns:
            filtered = filtered[filtered["Category"] == self.current_category]
            
        if row < len(filtered):
            rec = filtered.iloc[row]
            cat = str(rec.get("Category", "Issue"))
            variant = "danger" if "Business" in cat or "Schema" in cat else "warning"
            self.insp_category.set_text_and_variant(cat, variant)
            self.insp_col.setText(f"Column: {rec.get('Column', '--')}")
            details = f"{rec.get('Details', '')}\n\nSuggested Action:\n{rec.get('Suggested action', '')}"
            self.insp_details.setText(details)
            self.btn_fuzzy.setVisible(cat == "Inconsistent categories")
