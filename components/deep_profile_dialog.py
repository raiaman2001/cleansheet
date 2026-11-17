"""Deep Statistical Profiling and Redundancy Diagnostics Dialog for CleanSheet.
Surfaces comprehensive dataset metrics:
- Null %, Zero counts, Cardinality %, Inferred Types
- Collinear / Redundant Column recommendations (Correlation > 0.95 or identical content)
- Constant / Zero-variance warnings
"""
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QWidget, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from theme import ThemeManager
from enterprise_engine import generate_deep_profile, detect_redundant_columns


class DeepProfileDialog(QDialog):
    """Deep Statistical Profiling and Redundancy Diagnostics Dialog."""
    remove_columns_requested = Signal(list)  # list of column names to drop

    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deep Statistical Profiling & Data Diagnostics")
        self.resize(920, 620)
        self.df = df
        self.profile = None
        self.redundancy = None
        self._analyze_data()
        self._setup_ui()

    def _analyze_data(self):
        if self.df is not None and not self.df.empty:
            self.profile = generate_deep_profile(self.df)
            self.redundancy = detect_redundant_columns(self.df)
        else:
            self.profile = {"row_count": 0, "column_count": 0, "columns": {}}
            self.redundancy = {"duplicate_pairs": [], "collinear_numeric_pairs": [], "constant_columns": []}

    def _setup_ui(self):
        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background: {c.bg}; }}
            QLabel {{ color: {c.text_primary}; font-family: 'Segoe UI'; }}
            QTabWidget::pane {{
                border: 1px solid {c.border};
                background: {c.surface};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {c.surface_alt};
                color: {c.text_secondary};
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {c.surface};
                color: {c.accent};
                border: 1px solid {c.border};
                border-bottom: none;
            }}
            QTableWidget {{
                background: {c.surface};
                color: {c.text_primary};
                gridline-color: {c.border};
                border: 1px solid {c.border};
                border-radius: 6px;
            }}
            QHeaderView::section {{
                background: {c.surface_alt};
                color: {c.text_primary};
                padding: 6px;
                font-weight: 600;
                border: 1px solid {c.border};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header with high-level KPI cards
        title_row = QHBoxLayout()
        header = QLabel("Deep Statistical Profiling & Diagnostics")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet(f"color: {c.accent};")
        title_row.addWidget(header)
        title_row.addStretch(1)

        summary = self.profile.get("summary", {})
        rows = summary.get("total_rows", 0)
        cols = summary.get("total_columns", 0)
        mem_kb = summary.get("memory_usage_kb", 0.0)
        kpi_lbl = QLabel(f"Rows: <b>{rows:,}</b>  |  Cols: <b>{cols}</b>  |  Memory: <b>{mem_kb / 1024:.2f} MB</b>")
        kpi_lbl.setStyleSheet(f"background: {c.surface_alt}; padding: 6px 12px; border-radius: 6px; border: 1px solid {c.border}; font-size: 12px;")
        title_row.addWidget(kpi_lbl)
        layout.addLayout(title_row)

        tabs = QTabWidget()
        tabs.addTab(self._build_column_profile_tab(), "📊 Column-by-Column Profiling")
        tabs.addTab(self._build_redundancy_tab(), "⚠️ Redundant & Collinear Columns")
        layout.addWidget(tabs, 1)

        # Bottom Close Button
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet(f"background: {c.surface_alt}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; padding: 6px 20px; font-weight: 600;")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _build_column_profile_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        cols_data = self.profile.get("columns", {})
        table = QTableWidget(len(cols_data), 9)
        table.setHorizontalHeaderLabels([
            "Column Name", "Type", "Null Count", "Null %", "Unique (Cardinality)", "Zeros", "Min / Sample", "Mean", "Max / Sample"
        ])

        for r, (col, stat) in enumerate(cols_data.items()):
            table.setItem(r, 0, QTableWidgetItem(col))
            table.setItem(r, 1, QTableWidgetItem(stat.get("dtype", "")))
            
            # Nulls
            null_cnt = stat.get("null_count", 0)
            null_pct = stat.get("null_ratio_pct", 0.0)
            table.setItem(r, 2, QTableWidgetItem(f"{null_cnt:,}"))
            
            null_item = QTableWidgetItem(f"{null_pct:.1f}%")
            if null_pct > 20:
                null_item.setForeground(QColor("#EF4444"))
            table.setItem(r, 3, null_item)

            # Unique
            uniq = stat.get("unique_count", 0)
            tot = stat.get("total_rows", 1)
            card = (uniq / max(1, tot)) * 100
            table.setItem(r, 4, QTableWidgetItem(f"{uniq:,} ({card:.1f}%)"))

            # Zeros
            zeros = stat.get("zero_count", 0)
            table.setItem(r, 5, QTableWidgetItem(f"{zeros:,}"))

            # Min / Mean / Max
            if "mean" in stat:
                min_v = f"{stat.get('min', ''):.2f}" if stat.get('min') is not None else "-"
                mean_v = f"{stat.get('mean', ''):.2f}" if stat.get('mean') is not None else "-"
                max_v = f"{stat.get('max', ''):.2f}" if stat.get('max') is not None else "-"
            else:
                top_v = list(stat.get("top_values", {}).keys())
                min_v = str(top_v[0]) if top_v else "-"
                mean_v = "-"
                max_v = str(top_v[-1]) if len(top_v) > 1 else "-"

            table.setItem(r, 6, QTableWidgetItem(str(min_v)))
            table.setItem(r, 7, QTableWidgetItem(str(mean_v)))
            table.setItem(r, 8, QTableWidgetItem(str(max_v)))

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(table)
        return widget

    def _build_redundancy_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        desc = QLabel(
            "Detects duplicate columns with identical values, highly collinear numeric features "
            "(Pearson r > 0.95), and zero-variance constant columns that provide no analytical value."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #64748B; font-size: 12px;")
        layout.addWidget(desc)

        redundancy_list = self.redundancy if isinstance(self.redundancy, list) else []

        # Issue table
        all_issues = []
        redundant_to_drop = []
        for item in redundancy_list:
            all_issues.append({
                "type": item.get("type", "Redundant"),
                "col1": item.get("col_a", ""),
                "col2": item.get("col_b", ""),
                "score": str(item.get("similarity", "")),
                "recommendation": item.get("recommendation", "")
            })
            if item.get("col_b") and item.get("col_b") not in redundant_to_drop:
                redundant_to_drop.append(item.get("col_b"))

        if not all_issues:
            no_issue = QLabel("✅ Great news! No duplicate, highly collinear, or zero-variance columns were detected.")
            no_issue.setAlignment(Qt.AlignCenter)
            no_issue.setStyleSheet("color: #10B981; font-weight: bold; font-size: 14px; padding: 40px;")
            layout.addWidget(no_issue)
            return widget

        table = QTableWidget(len(all_issues), 5)
        table.setHorizontalHeaderLabels(["Issue Type", "Primary Column", "Redundant Column", "Correlation / Score", "Action Recommendation"])

        for r, iss in enumerate(all_issues):
            table.setItem(r, 0, QTableWidgetItem(iss["type"]))
            table.setItem(r, 1, QTableWidgetItem(iss["col1"]))
            table.setItem(r, 2, QTableWidgetItem(iss["col2"]))
            table.setItem(r, 3, QTableWidgetItem(iss["score"]))
            table.setItem(r, 4, QTableWidgetItem(iss["recommendation"]))

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table, 1)

        # Quick action row: Drop identified redundant columns
        btn_box = QHBoxLayout()
        if redundant_to_drop:
            btn_drop = QPushButton(f"🗑️ Clean Automatically: Drop {len(redundant_to_drop)} Redundant / Constant Columns")
            btn_drop.setStyleSheet("background: #EF4444; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px;")
            btn_drop.clicked.connect(lambda: self._drop_columns(redundant_to_drop))
            btn_box.addWidget(btn_drop)
        btn_box.addStretch(1)
        layout.addLayout(btn_box)

        return widget

    def _drop_columns(self, cols: list):
        reply = QMessageBox.question(
            self, "Confirm Drop",
            f"Are you sure you want to drop the following columns from the active dataset?\n\n{', '.join(cols)}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.remove_columns_requested.emit(cols)
            QMessageBox.information(self, "Columns Dropped", f"Successfully flagged {len(cols)} columns for removal.")
            self.accept()
