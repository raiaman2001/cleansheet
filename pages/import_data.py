"""CleanSheet Import Data Page.

Features drag & drop zone, metadata info chips, sheet selector combo, search filter box,
and sticky-header QTableView with column type badges.
"""
from typing import Callable, Optional
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QFrame
)
from components.widgets import Card, DropZone, Badge, PrimaryButton
from components.table import ModernTable
from theme import ThemeManager, ThemeColors
from icons import get_icon


class ImportPage(QWidget):
    """Import Data page supporting drag-and-drop, metadata chips, sheet switching, and filtered table preview."""
    file_imported = Signal(str)
    sheet_selected = Signal(str)

    def __init__(self, on_browse: Callable, parent=None):
        super().__init__(parent)
        self.on_browse = on_browse
        self._current_df: Optional[pd.DataFrame] = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Drag and Drop Zone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.file_imported.emit)
        self.drop_zone.browse_clicked.connect(self.on_browse)
        main_layout.addWidget(self.drop_zone)
        
        # 2. File Metadata Chips & Sheet Selector Row (hidden when no file)
        self.meta_card = Card(elevation=False)
        self.meta_card.setVisible(False)
        meta_layout = QHBoxLayout(self.meta_card)
        meta_layout.setContentsMargins(16, 12, 16, 12)
        meta_layout.setSpacing(12)
        
        self.chip_file = Badge("No file", "info")
        self.chip_rows = Badge("0 rows", "neutral")
        self.chip_cols = Badge("0 columns", "neutral")
        self.chip_size = Badge("0 KB", "neutral")
        
        meta_layout.addWidget(self.chip_file)
        meta_layout.addWidget(self.chip_rows)
        meta_layout.addWidget(self.chip_cols)
        meta_layout.addWidget(self.chip_size)
        
        # Excel Sheet Selector
        self.sheet_lbl = QLabel("Sheet:")
        self.sheet_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.sheet_combo = QComboBox()
        self.sheet_combo.setMinimumWidth(160)
        self.sheet_combo.currentTextChanged.connect(self.sheet_selected.emit)
        
        meta_layout.addSpacing(16)
        meta_layout.addWidget(self.sheet_lbl)
        meta_layout.addWidget(self.sheet_combo)
        self.sheet_lbl.setVisible(False)
        self.sheet_combo.setVisible(False)
        
        meta_layout.addStretch(1)
        
        # Table search/filter box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter preview rows...")
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self._filter_table)
        meta_layout.addWidget(self.search_input)
        
        main_layout.addWidget(self.meta_card)
        
        # 3. Data Preview Table
        self.preview_table = ModernTable()
        main_layout.addWidget(self.preview_table, 1)

    def set_dataset(self, path: str, df: pd.DataFrame, sheets: list = None):
        """Update metadata chips, sheets combo, and table preview."""
        self._current_df = df
        self.drop_zone.setVisible(False)
        self.meta_card.setVisible(True)
        
        p = Path(path)
        size_kb = f"{p.stat().st_size / 1024:.1f} KB" if p.exists() else "--"
        self.chip_file.set_text_and_variant(f"📄 {p.name}", "info")
        self.chip_rows.set_text_and_variant(f"{len(df):,} Rows", "neutral")
        self.chip_cols.set_text_and_variant(f"{len(df.columns):,} Columns", "neutral")
        self.chip_size.set_text_and_variant(size_kb, "neutral")
        
        # Sheets
        if sheets and len(sheets) > 1:
            self.sheet_lbl.setVisible(True)
            self.sheet_combo.setVisible(True)
            self.sheet_combo.blockSignals(True)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheets)
            self.sheet_combo.blockSignals(False)
        else:
            self.sheet_lbl.setVisible(False)
            self.sheet_combo.setVisible(False)
            
        self._render_table(df.head(300))

    def update_sheet_data(self, df: pd.DataFrame):
        """Update preview table and chip counters when a new sheet is chosen."""
        self._current_df = df
        self.chip_rows.set_text_and_variant(f"{len(df):,} Rows", "neutral")
        self.chip_cols.set_text_and_variant(f"{len(df.columns):,} Columns", "neutral")
        if hasattr(self, "search_input"):
            self.search_input.clear()
        self._render_table(df.head(300))

    def _render_table(self, df: pd.DataFrame):
        from PySide6.QtWidgets import QTableWidgetItem
        self.preview_table.setSortingEnabled(False)
        self.preview_table.clear()
        
        if df is None or df.empty:
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return
            
        rows_to_show = min(len(df), 300)
        self.preview_table.setRowCount(rows_to_show)
        self.preview_table.setColumnCount(len(df.columns))
        
        # Headers with data types
        headers = []
        for col in df.columns:
            dtype_name = str(df[col].dtype)
            headers.append(f"{col} ({dtype_name})")
        self.preview_table.setHorizontalHeaderLabels(headers)
        
        for r in range(rows_to_show):
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                txt = "" if pd.isna(val) else str(val)
                item = QTableWidgetItem(txt)
                item.setToolTip(txt)
                self.preview_table.setItem(r, c, item)
                
        self.preview_table.setSortingEnabled(True)
        self.preview_table.resizeColumnsToContents()

    def _filter_table(self, query: str):
        if self._current_df is None:
            return
        q = query.strip().lower()
        if not q:
            self._render_table(self._current_df.head(300))
            return
            
        # Filter rows that contain substring in any column
        mask = self._current_df.astype(str).apply(lambda row: row.str.lower().str.contains(q, regex=False)).any(axis=1)
        filtered = self._current_df[mask]
        self._render_table(filtered.head(300))
