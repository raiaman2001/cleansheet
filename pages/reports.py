"""CleanSheet Reports & Export Page.

Displays data quality score transition, cleaning log history, and export actions.
"""
from typing import Callable, Optional
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from components.widgets import Card, PrimaryButton, Badge, StatCard
from components.table import ModernTable
from theme import ThemeManager, ThemeColors
from icons import get_icon


class ReportsPage(QWidget):
    """Reports & Export page with quality score badge, cleaning operation log, and export actions."""
    save_excel_clicked = Signal()
    save_protected_excel_clicked = Signal()
    save_csv_clicked = Signal()
    save_json_clicked = Signal()
    save_pdf_clicked = Signal()
    view_audit_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Summary Card with Quality Score Transition
        summary_card = Card(elevation=False)
        s_layout = QHBoxLayout(summary_card)
        s_layout.setContentsMargins(22, 18, 22, 18)
        s_layout.setSpacing(20)
        
        score_box = QVBoxLayout()
        score_box.setSpacing(2)
        score_lbl = QLabel("Data Health Score")
        score_lbl.setObjectName("StatLabel")
        self.quality_val = QLabel("--")
        self.quality_val.setObjectName("StatValue")
        score_box.addWidget(score_lbl)
        score_box.addWidget(self.quality_val)
        s_layout.addLayout(score_box)
        
        info_box = QVBoxLayout()
        info_box.setSpacing(4)
        info_box.setAlignment(Qt.AlignVCenter)
        self.summary_title = QLabel("Cleaned Dataset Report")
        self.summary_title.setObjectName("CardTitle")
        self.summary_desc = QLabel("Clean a dataset to see quality improvements and download your finished files.")
        self.summary_desc.setObjectName("CardDesc")
        self.summary_desc.setWordWrap(True)
        info_box.addWidget(self.summary_title)
        info_box.addWidget(self.summary_desc)
        s_layout.addLayout(info_box, 1)
        
        main_layout.addWidget(summary_card)
        
        # 2. Cleaning Logs / Changes Table
        table_lbl = QLabel("List of Changes Made")
        table_lbl.setObjectName("CardTitle")
        main_layout.addWidget(table_lbl)
        
        self.log_table = ModernTable()
        main_layout.addWidget(self.log_table, 1)
        
        # 3. Export Action Bar
        export_card = Card(elevation=False)
        e_layout = QHBoxLayout(export_card)
        e_layout.setContentsMargins(18, 12, 18, 12)
        e_layout.setSpacing(12)
        
        self.btn_audit = QPushButton("Past Cleaning History")
        self.btn_audit.setIcon(get_icon("database", "#64748B", 14))
        self.btn_audit.clicked.connect(self.view_audit_clicked.emit)
        e_layout.addWidget(self.btn_audit)
        
        e_layout.addStretch(1)
        
        self.btn_json = QPushButton("Save JSON Report")
        self.btn_json.setIcon(get_icon("code", "#64748B", 14))
        self.btn_json.clicked.connect(self.save_json_clicked.emit)
        e_layout.addWidget(self.btn_json)
        
        self.btn_csv = QPushButton("Save as CSV")
        self.btn_csv.setIcon(get_icon("table", "#64748B", 14))
        self.btn_csv.clicked.connect(self.save_csv_clicked.emit)
        e_layout.addWidget(self.btn_csv)
        
        self.btn_pdf = QPushButton("Executive PDF Certificate")
        self.btn_pdf.setIcon(get_icon("shield", "#1E3A8A", 14))
        self.btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #1E3A8A;
                border: 1px solid #C7D2FE;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #E0E7FF;
            }
        """)
        self.btn_pdf.clicked.connect(self.save_pdf_clicked.emit)
        e_layout.addWidget(self.btn_pdf)
        
        self.btn_protected_excel = QPushButton("🔒 Password Encrypt Excel")
        self.btn_protected_excel.setIcon(get_icon("shield", "#0D9488", 14))
        self.btn_protected_excel.setStyleSheet("""
            QPushButton {
                background-color: #CCFBF1;
                color: #0D9488;
                border: 1px solid #99F6E4;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #99F6E4;
            }
        """)
        self.btn_protected_excel.setToolTip("Export cleaned dataset into a password-protected & encrypted Excel workbook")
        self.btn_protected_excel.clicked.connect(self.save_protected_excel_clicked.emit)
        e_layout.addWidget(self.btn_protected_excel)

        self.btn_excel = PrimaryButton("Download Excel File", icon_name="download")
        self.btn_excel.clicked.connect(self.save_excel_clicked.emit)
        e_layout.addWidget(self.btn_excel)
        
        main_layout.addWidget(export_card)

    def set_report_data(self, original_df, cleaned_df, logs_df, file_path: str = ""):
        from PySide6.QtWidgets import QTableWidgetItem
        from clean_engine import profile, quality_score
        
        if cleaned_df is None or original_df is None:
            self.quality_val.setText("--")
            self.summary_desc.setText("Clean a dataset to see quality improvements and download your finished files.")
            self.log_table.setRowCount(0)
            self.log_table.setColumnCount(0)
            return
            
        q_before = quality_score(original_df)
        q_after = quality_score(cleaned_df)
        c = ThemeManager.instance().colors
        self.quality_val.setText(f"{q_after:.1f}/100")
        self.quality_val.setStyleSheet(f"color: {c.success if q_after >= 80 else c.accent};")
        
        p_before = profile(original_df)
        p_after = profile(cleaned_df)
        src_name = Path(file_path).name if file_path else "Current Dataset"
        self.summary_desc.setText(
            f"Source: {src_name} · Rows: {p_before['Rows']:,} → {p_after['Rows']:,} · "
            f"Missing Cells: {p_before['Missing cells']:,} → {p_after['Missing cells']:,} · "
            f"Duplicates: {p_before['Duplicate rows']:,} → {p_after['Duplicate rows']:,} · "
            f"Score Improvement: {q_before:.1f} → {q_after:.1f}"
        )
        
        # Render logs table
        if logs_df is not None and not logs_df.empty:
            self.log_table.setSortingEnabled(False)
            self.log_table.clear()
            self.log_table.setRowCount(len(logs_df))
            self.log_table.setColumnCount(len(logs_df.columns))
            self.log_table.setHorizontalHeaderLabels([str(col) for col in logs_df.columns])
            
            for r in range(len(logs_df)):
                for col in range(len(logs_df.columns)):
                    v = logs_df.iloc[r, col]
                    self.log_table.setItem(r, col, QTableWidgetItem("" if pd.isna(v) else str(v)))
            self.log_table.setSortingEnabled(True)
            self.log_table.resizeColumnsToContents()
