"""CleanSheet Audit & History Page.

Displays a complete chronological log of all cleaning runs, timestamps, source filenames,
cleaning profiles applied, before vs after row counts, status, and quality deltas.
"""
from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidgetItem, QHeaderView
)
from components.widgets import Card, StatCard, PrimaryButton, Badge, EmptyState
from components.table import ModernTable
from theme import ThemeManager, ThemeColors
from icons import get_icon
from clean_engine import read_audit


class HistoryPage(QWidget):
    """Cleaning History & Audit Log page."""
    import_requested = Signal()
    view_run_requested = Signal(str, str)  # (source_path, profile_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_data = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Top KPI Summary Cards
        stats_grid = QHBoxLayout()
        stats_grid.setSpacing(14)
        
        self.stat_runs = StatCard("Cleaning Runs", "--", "Total times files cleaned", "history")
        self.stat_latest = StatCard("Last Cleaned On", "--", "Most recent cleaning date", "overview")
        self.stat_processed = StatCard("Total Rows Cleaned", "--", "All records cleaned so far", "rows")
        
        stats_grid.addWidget(self.stat_runs)
        stats_grid.addWidget(self.stat_latest)
        stats_grid.addWidget(self.stat_processed)
        main_layout.addLayout(stats_grid)
        
        # 2. Main Audit Log Table Card
        table_card = Card(elevation=True)
        t_layout = QVBoxLayout(table_card)
        t_layout.setContentsMargins(20, 16, 20, 16)
        t_layout.setSpacing(12)
        
        # Header Controls: Search + Refresh + Quick Count
        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)
        
        t_title = QLabel("Past Cleaning Activity")
        t_title.setObjectName("CardTitle")
        top_bar.addWidget(t_title)
        
        self.count_badge = Badge("0 Records", "neutral")
        top_bar.addWidget(self.count_badge)
        top_bar.addStretch(1)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by file name or cleaning profile...")
        self.search_input.setFixedWidth(280)
        self.search_input.setFixedHeight(34)
        self.search_input.textChanged.connect(self._filter_table)
        top_bar.addWidget(self.search_input)
        
        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setFixedHeight(34)
        c = ThemeManager.instance().colors
        self.btn_refresh.setIcon(get_icon("refresh", c.text_primary, 14))
        self.btn_refresh.clicked.connect(self.refresh_history)
        top_bar.addWidget(self.btn_refresh)

        self.btn_clear = QPushButton(" Clear History")
        self.btn_clear.setFixedHeight(34)
        self.btn_clear.setIcon(get_icon("trash", "#DC2626", 14))
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: #FEE2E2;
                color: #DC2626;
                border: 1px solid #FECACA;
                font-weight: 600;
                border-radius: 6px;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #FCA5A5;
            }
        """)
        self.btn_clear.setToolTip("Clear all cleaning history records from the audit database")
        self.btn_clear.clicked.connect(self._clear_history_prompt)
        top_bar.addWidget(self.btn_clear)
        
        t_layout.addLayout(top_bar)
        
        # Table Widget
        self.table = ModernTable()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Date & Time", "File Name", "View Data", "Profile Used", "Rows Before", "Rows After", "Status", "Details"
        ])
        
        # Configure generous sizing so text is NEVER squeezed or cut off with '...'
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 100)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(80)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setTextElideMode(Qt.ElideNone)
        
        self.table.cellClicked.connect(self._on_cell_clicked)
        t_layout.addWidget(self.table, 1)
        
        main_layout.addWidget(table_card, 1)
        
        self.refresh_history()

    def refresh_history(self):
        """Fetch audit trail records from SQLite and populate the table."""
        try:
            df = read_audit(limit=500)
            self.raw_data = df
            self._populate_table(df)
            
            # Update KPI Stat cards
            if df is not None and not df.empty:
                self.stat_runs.set_value(f"{len(df):,}")
                latest_ts = str(df["Timestamp"].iloc[0]).replace("T", " ")[:19]
                self.stat_latest.set_value(latest_ts)
                
                if "Rows after" in df.columns:
                    total_rows = int(df["Rows after"].sum())
                    self.stat_processed.set_value(f"{total_rows:,}")
                self.count_badge.set_text_and_variant(f"{len(df)} Run(s)", "info")
            else:
                self.stat_runs.set_value("0")
                self.stat_latest.set_value("No runs yet")
                self.stat_processed.set_value("0")
                self.count_badge.set_text_and_variant("0 Runs", "neutral")
        except Exception:
            pass

    def _populate_table(self, df):
        self._current_displayed_df = df
        if df is None or df.empty:
            self.table.setRowCount(0)
            return
            
        c = ThemeManager.instance().colors
        self.table.setRowCount(len(df))
        
        for r in range(len(df)):
            row = df.iloc[r]
            src_raw = str(row.get("Source", ""))
            src_clean = Path(src_raw).name if src_raw and src_raw != "None" else "Current dataset"
            prof_name = str(row.get("Profile", "Clean Dataset"))
            
            # 0. Timestamp
            ts_str = str(row.get("Timestamp", "")).replace("T", " ")[:19]
            it_ts = QTableWidgetItem(ts_str)
            self.table.setItem(r, 0, it_ts)
            
            # 1. Source File (styled with link color and underline look)
            it_src = QTableWidgetItem(f"{src_clean}")
            it_src.setToolTip(f"Source file: {src_raw}\nClick to view uploaded & cleaned data comparison.")
            it_src.setForeground(QColor(c.accent))
            self.table.setItem(r, 1, it_src)
            
            # 2. View Data Action Button (Opens uploaded & cleaned data comparison)
            btn_view = QPushButton("View Data")
            btn_view.setCursor(Qt.PointingHandCursor)
            btn_view.setFixedSize(76, 26)
            btn_view.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.accent_subtle};
                    color: {c.accent};
                    border: 1px solid {c.accent};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {c.accent};
                    color: #FFFFFF;
                }}
            """)
            btn_view.setToolTip(f"View uploaded & cleaned data comparison for '{src_clean}'")
            btn_view.clicked.connect(lambda checked=False, s=src_raw, p=prof_name: self.view_run_requested.emit(s, p))
            
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(4, 2, 4, 2)
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.addWidget(btn_view)
            self.table.setCellWidget(r, 2, btn_container)
            
            # 3. Profile Used
            it_prof = QTableWidgetItem(prof_name)
            self.table.setItem(r, 3, it_prof)
            
            # 4. Rows Before
            it_before = QTableWidgetItem(f"{int(row.get('Rows before', 0)):,}")
            it_before.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 4, it_before)
            
            # 5. Rows After
            it_after = QTableWidgetItem(f"{int(row.get('Rows after', 0)):,}")
            it_after.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 5, it_after)
            
            # 6. Status
            status_text = str(row.get("Status", "Completed"))
            it_status = QTableWidgetItem(f"● {status_text}")
            if status_text.lower() == "completed":
                it_status.setForeground(QColor(c.success))
            else:
                it_status.setForeground(QColor(c.danger))
            self.table.setItem(r, 6, it_status)
            
            # 7. Details / Quality Score Delta
            det_str = str(row.get("Details", ""))
            it_det = QTableWidgetItem(det_str)
            it_det.setToolTip(det_str)
            self.table.setItem(r, 7, it_det)
            
            # Row height & generous vertical spacing
            self.table.setRowHeight(r, 40)
            
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(2, 105)
        # Add extra safety padding to Details column so there is never clipping
        self.table.setColumnWidth(7, max(self.table.columnWidth(7) + 24, 160))

    def _on_cell_clicked(self, row: int, col: int):
        if col == 1:  # Source File column clicked
            current_df = getattr(self, "_current_displayed_df", self.raw_data)
            if current_df is not None and row < len(current_df):
                r = current_df.iloc[row]
                src = str(r.get("Source", ""))
                prof = str(r.get("Profile", "Clean Dataset"))
                self.view_run_requested.emit(src, prof)

    def _filter_table(self, query: str):
        if self.raw_data is None or self.raw_data.empty:
            return
        query = query.strip().lower()
        if not query:
            self._populate_table(self.raw_data)
            return
            
        mask = (
            self.raw_data["Source"].astype(str).str.lower().str.contains(query) |
            self.raw_data["Profile"].astype(str).str.lower().str.contains(query) |
            self.raw_data["Status"].astype(str).str.lower().str.contains(query) |
            self.raw_data["Details"].astype(str).str.lower().str.contains(query)
        )
        filtered = self.raw_data[mask]
        self._populate_table(filtered)
        self.count_badge.set_text_and_variant(f"{len(filtered)} / {len(self.raw_data)} Runs", "warning")

    def _clear_history_prompt(self):
        from PySide6.QtWidgets import QMessageBox
        import sqlite3
        from clean_engine import audit_db_path

        reply = QMessageBox.question(
            self, "Clear Cleaning History",
            "Are you sure you want to delete all past cleaning activity records?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                db_p = audit_db_path()
                if db_p.exists():
                    conn = sqlite3.connect(str(db_p))
                    conn.execute("DELETE FROM audit_log")
                    conn.commit()
                    conn.execute("VACUUM")
                    conn.close()
                self.refresh_history()
                QMessageBox.information(self, "History Cleared", "All cleaning history records have been cleared successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not clear history: {str(e)}")
