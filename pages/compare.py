"""CleanSheet Compare Page.

Side-by-side or difference-highlighting visual comparison between:
- Uploaded original dataset
- Cleaned dataset

Highlights modified cells, removed rows, standardized values, and summary metrics.
"""
from typing import Callable, Optional
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidgetItem, QStackedWidget, QFrame, QRadioButton, QButtonGroup,
    QScrollArea, QSplitter
)
from components.widgets import Card, StatCard, Badge, EmptyState, PrimaryButton
from components.table import ModernTable
from theme import ThemeManager, ThemeColors
from icons import get_icon


class ComparePage(QWidget):
    """Visual Compare Page highlighting changes between original and cleaned datasets."""
    import_requested = Signal()
    run_workflow_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_df: Optional[pd.DataFrame] = None
        self.cleaned_df: Optional[pd.DataFrame] = None
        self.diff_report_df: Optional[pd.DataFrame] = None
        self.filter_mode = "all"  # 'all' or 'changes_only'

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Top Summary KPI Header
        self.header_card = Card(elevation=False)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(20, 16, 20, 16)
        h_layout.setSpacing(20)

        # Metric Badges
        self.stat_cells_changed = StatCard("Values Changed", "0", "Values cleaned or filled", "magic")
        self.stat_rows_removed = StatCard("Rows Removed", "0", "Duplicates or blanks removed", "rows")
        self.stat_quality_delta = StatCard("Health Score", "--", "Before → After", "trend-up")

        h_layout.addWidget(self.stat_cells_changed)
        h_layout.addWidget(self.stat_rows_removed)
        h_layout.addWidget(self.stat_quality_delta)
        main_layout.addWidget(self.header_card)

        # 2. Control Toolbar & Legend Bar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)

        # Legend Chips
        lbl_legend = QLabel("Color Guide:")
        lbl_legend.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        toolbar.addWidget(lbl_legend)

        self.chip_modified = Badge("● Changed Value (Orange)", "warning")
        self.chip_removed = Badge("● Removed Row (Red)", "danger")
        self.chip_clean = Badge("● Untouched (Normal)", "neutral")

        toolbar.addWidget(self.chip_modified)
        toolbar.addWidget(self.chip_removed)
        toolbar.addWidget(self.chip_clean)

        toolbar.addStretch(1)

        # Filter mode radio buttons
        self.btn_view_diff = QPushButton("Show Only Changed Cells")
        self.btn_view_diff.setCheckable(True)
        self.btn_view_diff.setChecked(False)
        self.btn_view_diff.toggled.connect(self._toggle_view_mode)
        toolbar.addWidget(self.btn_view_diff)

        main_layout.addLayout(toolbar)

        # 3. Body Stack: Empty State vs Comparison Views
        self.body_stack = QStackedWidget()

        # View 0: Empty state when no data or no cleaning yet
        self.empty_view = EmptyState(
            "compare",
            "No Comparison to Show Yet",
            "Upload a dataset and clean it to see a side-by-side comparison of all changes made.",
            "Start Cleaning",
            self
        )
        self.empty_view.action_clicked.connect(self.run_workflow_requested.emit)
        self.body_stack.addWidget(self.empty_view)

        # View 1: Side-by-side Tables Splitter
        self.tables_container = QWidget()
        tc_layout = QHBoxLayout(self.tables_container)
        tc_layout.setContentsMargins(0, 0, 0, 0)
        tc_layout.setSpacing(14)

        # Left Panel: Original Uploaded Data
        left_box = QFrame()
        left_box.setObjectName("Card")
        lb_layout = QVBoxLayout(left_box)
        lb_layout.setContentsMargins(14, 12, 14, 12)
        lb_layout.setSpacing(8)

        lbl_orig_title = QLabel("1. Original Data (Before)")
        lbl_orig_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        lb_layout.addWidget(lbl_orig_title)

        self.table_orig = ModernTable()
        lb_layout.addWidget(self.table_orig, 1)
        tc_layout.addWidget(left_box, 1)

        # Right Panel: Cleaned Data with Highlights
        right_box = QFrame()
        right_box.setObjectName("Card")
        rb_layout = QVBoxLayout(right_box)
        rb_layout.setContentsMargins(14, 12, 14, 12)
        rb_layout.setSpacing(8)

        lbl_clean_title = QLabel("2. Cleaned Data (After)")
        lbl_clean_title.setFont(QFont("Segoe UI", 11, QFont.Bold))
        rb_layout.addWidget(lbl_clean_title)

        self.table_clean = ModernTable()
        rb_layout.addWidget(self.table_clean, 1)
        tc_layout.addWidget(right_box, 1)

        self.body_stack.addWidget(self.tables_container)

        # View 2: Detailed Difference Log Table
        self.diff_container = QWidget()
        dc_layout = QVBoxLayout(self.diff_container)
        dc_layout.setContentsMargins(0, 0, 0, 0)
        dc_layout.setSpacing(8)

        lbl_diff_title = QLabel("Cell-by-Cell Value Discrepancies & Audit Log")
        lbl_diff_title.setObjectName("CardTitle")
        dc_layout.addWidget(lbl_diff_title)

        self.table_diff = ModernTable()
        dc_layout.addWidget(self.table_diff, 1)
        self.body_stack.addWidget(self.diff_container)

        main_layout.addWidget(self.body_stack, 1)

    def set_data(self, original: Optional[pd.DataFrame], cleaned: Optional[pd.DataFrame]):
        """Set original and cleaned dataframes and render diff highlighting."""
        self.original_df = original
        self.cleaned_df = cleaned

        if original is None or cleaned is None or original.empty:
            self.body_stack.setCurrentIndex(0)
            self.header_card.setVisible(False)
            return

        self.header_card.setVisible(True)
        from clean_engine import quality_score, build_change_report

        q_orig = quality_score(original)
        q_clean = quality_score(cleaned)
        diff_report = build_change_report(original, cleaned)
        self.diff_report_df = diff_report

        # Update KPI cards
        cells_changed_count = 0
        rows_removed_count = 0
        if not diff_report.empty:
            cells_changed_count = int((diff_report["Change type"] == "Cell changed").sum())
            rows_removed_count = int((diff_report["Change type"] == "Row removed").sum())

        self.stat_cells_changed.set_value(f"{cells_changed_count:,}")
        self.stat_rows_removed.set_value(f"{rows_removed_count:,}")
        self.stat_quality_delta.set_value(f"{q_clean:.1f}/100", hint=f"{q_orig:.1f} → {q_clean:.1f}")

        # Populate tables
        self._render_comparison_tables(cells_changed_count, rows_removed_count)
        self._render_diff_table(diff_report)

        self.body_stack.setCurrentIndex(2 if self.btn_view_diff.isChecked() else 1)

    def _render_comparison_tables(self, modified_cells: int, removed_rows: int):
        orig = self.original_df
        clean = self.cleaned_df
        if orig is None or clean is None:
            return

        # Render Left: Original Table
        max_r = min(len(orig), 300)
        self.table_orig.setSortingEnabled(False)
        self.table_orig.clear()
        self.table_orig.setRowCount(max_r)
        self.table_orig.setColumnCount(len(orig.columns))
        self.table_orig.setHorizontalHeaderLabels([str(c) for c in orig.columns])

        for r in range(max_r):
            for c in range(len(orig.columns)):
                val = orig.iloc[r, c]
                txt = "" if pd.isna(val) else str(val)
                item = QTableWidgetItem(txt)
                item.setToolTip(txt)
                self.table_orig.setItem(r, c, item)

        self.table_orig.setSortingEnabled(True)
        self.table_orig.resizeColumnsToContents()

        # Render Right: Cleaned Table with Change Highlighting
        max_rc = min(len(clean), 300)
        self.table_clean.setSortingEnabled(False)
        self.table_clean.clear()
        self.table_clean.setRowCount(max_rc)
        self.table_clean.setColumnCount(len(clean.columns))
        self.table_clean.setHorizontalHeaderLabels([str(c) for c in clean.columns])

        # Soft highlight colors
        highlight_bg = QColor(254, 243, 199, 180)  # Amber-100 highlight
        highlight_text = QColor(180, 83, 9)         # Amber-700 text

        # Map column positions for comparison
        col_map = {}
        for c_idx, clean_col in enumerate(clean.columns):
            if clean_col in orig.columns:
                col_map[c_idx] = clean_col
            elif c_idx < len(orig.columns):
                col_map[c_idx] = orig.columns[c_idx]

        for r in range(max_rc):
            clean_idx = clean.index[r] if r < len(clean.index) else r
            orig_row = orig.loc[clean_idx] if clean_idx in orig.index else None

            for c in range(len(clean.columns)):
                val_clean = clean.iloc[r, c]
                txt_clean = "" if pd.isna(val_clean) else str(val_clean)
                item = QTableWidgetItem(txt_clean)
                item.setToolTip(txt_clean)

                # Check if this cell value was changed
                if orig_row is not None and c in col_map:
                    orig_col = col_map[c]
                    val_orig = orig_row[orig_col] if orig_col in orig_row else None
                    val_orig_str = "" if pd.isna(val_orig) else str(val_orig)
                    if txt_clean != val_orig_str:
                        # Highlight changed cell
                        item.setBackground(QBrush(highlight_bg))
                        item.setForeground(highlight_text)
                        item.setToolTip(f"Original: {val_orig_str} → Cleaned: {txt_clean}")

                self.table_clean.setItem(r, c, item)

        self.table_clean.setSortingEnabled(True)
        self.table_clean.resizeColumnsToContents()

    def _render_diff_table(self, diff_report: pd.DataFrame):
        self.table_diff.setSortingEnabled(False)
        self.table_diff.clear()
        if diff_report is None or diff_report.empty:
            self.table_diff.setRowCount(0)
            self.table_diff.setColumnCount(0)
            return

        self.table_diff.setRowCount(len(diff_report))
        self.table_diff.setColumnCount(len(diff_report.columns))
        self.table_diff.setHorizontalHeaderLabels([str(c) for c in diff_report.columns])

        for r in range(len(diff_report)):
            for c in range(len(diff_report.columns)):
                val = diff_report.iloc[r, c]
                txt = "" if pd.isna(val) else str(val)
                item = QTableWidgetItem(txt)
                col_name = str(diff_report.columns[c])
                if col_name == "Change type":
                    if txt == "Row removed":
                        item.setForeground(QColor("#DC2626"))
                    else:
                        item.setForeground(QColor("#D97706"))
                self.table_diff.setItem(r, c, item)

        self.table_diff.setSortingEnabled(True)
        self.table_diff.resizeColumnsToContents()

    def _toggle_view_mode(self, checked: bool):
        if self.original_df is None or self.cleaned_df is None:
            return
        if checked:
            self.btn_view_diff.setText("Side-by-Side View")
            self.body_stack.setCurrentIndex(2)
        else:
            self.btn_view_diff.setText("Changed Cells Only")
            self.body_stack.setCurrentIndex(1)
