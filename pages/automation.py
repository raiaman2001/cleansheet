"""CleanSheet Batch Automation Page.

Card-based configuration for batch processing: input files manager, profile selector,
output directory picker, schedule automation, and progress results table.
"""
from typing import Callable, Optional
from pathlib import Path
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QSpinBox, QProgressBar, QListWidget, QFrame
)
from components.widgets import Card, PrimaryButton, Badge
from components.table import ModernTable
from theme import ThemeManager, ThemeColors
from icons import get_icon


class AutomationPage(QWidget):
    """Batch folder processing and recurring schedule automation workspace."""
    add_files_clicked = Signal()
    remove_selected_clicked = Signal()
    browse_output_clicked = Signal()
    run_batch_clicked = Signal()
    start_schedule_clicked = Signal()
    stop_schedule_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Config Card: Split into Left (Files list) & Right (Profile & Output parameters)
        config_card = Card(elevation=False)
        c_layout = QHBoxLayout(config_card)
        c_layout.setContentsMargins(20, 18, 20, 18)
        c_layout.setSpacing(20)
        
        # Left: Files Queue
        left_col = QVBoxLayout()
        left_col.setSpacing(10)
        
        file_header = QHBoxLayout()
        fl_title = QLabel("Files to Clean")
        fl_title.setObjectName("CardTitle")
        file_header.addWidget(fl_title)
        file_header.addStretch(1)
        
        self.btn_add = QPushButton("Add Files")
        self.btn_add.setIcon(get_icon("plus", "#64748B", 14))
        self.btn_add.setMinimumWidth(100)
        self.btn_add.clicked.connect(self.add_files_clicked.emit)
        file_header.addWidget(self.btn_add)
        
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setMinimumWidth(80)
        self.btn_remove.clicked.connect(self.remove_selected_clicked.emit)
        file_header.addWidget(self.btn_remove)
        left_col.addLayout(file_header)
        
        self.batch_list = QListWidget()
        self.batch_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.batch_list.setMinimumHeight(160)
        left_col.addWidget(self.batch_list, 1)
        c_layout.addLayout(left_col, 3)
        
        # Right: Profile, Output Directory & Schedule Setup
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        
        rc_title = QLabel("Cleaning Setup")
        rc_title.setObjectName("CardTitle")
        right_col.addWidget(rc_title)
        
        # Profile selector
        lbl_p = QLabel("Cleaning Profile:")
        lbl_p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.combo_profile = QComboBox()
        self.combo_profile.addItems(["Clean Dataset"])
        right_col.addWidget(lbl_p)
        right_col.addWidget(self.combo_profile)
        
        # Output folder picker
        lbl_o = QLabel("Where to save cleaned files:")
        lbl_o.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        right_col.addWidget(lbl_o)
        
        out_row = QHBoxLayout()
        self.output_path = QLineEdit(str(Path.home() / "CleanSheet_Output"))
        out_row.addWidget(self.output_path, 1)
        self.btn_browse = QPushButton("Browse")
        self.btn_browse.setMinimumWidth(85)
        self.btn_browse.clicked.connect(self.browse_output_clicked.emit)
        out_row.addWidget(self.btn_browse)
        right_col.addLayout(out_row)
        
        # Run Batch Primary Action
        self.btn_run = PrimaryButton("Clean All Files Now", icon_name="play")
        self.btn_run.clicked.connect(self.run_batch_clicked.emit)
        right_col.addWidget(self.btn_run)
        
        # Optional schedule recurring box
        sched_box = QFrame()
        sched_box.setObjectName("SchedBox")
        
        def _style_sched_box(c: ThemeColors):
            sched_box.setStyleSheet(f"""
                QFrame#SchedBox {{
                    background: {c.surface_alt};
                    border: 1px solid {c.border};
                    border-radius: 8px;
                }}
                QFrame#SchedBox QLabel {{
                    background: transparent;
                    color: {c.text_primary};
                }}
            """)
        _style_sched_box(ThemeManager.instance().colors)
        ThemeManager.instance().subscribe(_style_sched_box)
        sb_layout = QVBoxLayout(sched_box)
        sb_layout.setContentsMargins(12, 10, 12, 10)
        sb_layout.setSpacing(8)
        
        lbl_s = QLabel("Run Automatically (While app is open):")
        lbl_s.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        sb_layout.addWidget(lbl_s)
        
        s_row = QHBoxLayout()
        s_row.setSpacing(8)
        self.spin_minutes = QSpinBox()
        self.spin_minutes.setRange(1, 1440)
        self.spin_minutes.setValue(60)
        self.spin_minutes.setSuffix(" minutes")
        self.spin_minutes.setFixedHeight(34)
        s_row.addWidget(self.spin_minutes, 1)
        
        self.btn_start_sched = QPushButton("Start")
        self.btn_start_sched.setFixedHeight(34)
        self.btn_start_sched.setMinimumWidth(70)
        self.btn_start_sched.setCursor(Qt.PointingHandCursor)
        self.btn_start_sched.clicked.connect(self.start_schedule_clicked.emit)
        s_row.addWidget(self.btn_start_sched)
        
        self.btn_stop_sched = QPushButton("Stop")
        self.btn_stop_sched.setFixedHeight(34)
        self.btn_stop_sched.setMinimumWidth(70)
        self.btn_stop_sched.setCursor(Qt.PointingHandCursor)
        self.btn_stop_sched.setEnabled(False)
        self.btn_stop_sched.clicked.connect(self.stop_schedule_clicked.emit)
        s_row.addWidget(self.btn_stop_sched)
        sb_layout.addLayout(s_row)
        
        self.lbl_schedule_status = QLabel("Automatic run is off.")
        self.lbl_schedule_status.setObjectName("CardDesc")
        sb_layout.addWidget(self.lbl_schedule_status)
        right_col.addWidget(sched_box)
        
        c_layout.addLayout(right_col, 2)
        main_layout.addWidget(config_card)
        
        # 2. Progress Bar & Status
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        self.status_lbl = QLabel("No files are currently being cleaned.")
        self.status_lbl.setObjectName("CardDesc")
        main_layout.addWidget(self.status_lbl)
        
        # 3. Batch Processing Results Table
        self.results_table = ModernTable()
        main_layout.addWidget(self.results_table, 1)

    def set_running(self, running: bool, status_msg: str = ""):
        self.progress_bar.setVisible(running)
        self.btn_run.setEnabled(not running)
        if status_msg:
            self.status_lbl.setText(status_msg)

    def set_results(self, df: pd.DataFrame):
        from PySide6.QtWidgets import QTableWidgetItem
        self.results_table.setSortingEnabled(False)
        self.results_table.clear()
        
        if df is None or df.empty:
            self.results_table.setRowCount(0)
            self.results_table.setColumnCount(0)
            return
            
        self.results_table.setRowCount(len(df))
        self.results_table.setColumnCount(len(df.columns))
        self.results_table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        
        c_theme = ThemeManager.instance().colors
        for r in range(len(df)):
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                item = QTableWidgetItem("" if pd.isna(val) else str(val))
                if str(df.columns[c]) == "Status":
                    item.setForeground(QColor(c_theme.success) if str(val) == "Completed" else QColor(c_theme.danger))
                self.results_table.setItem(r, c, item)
                
        self.results_table.setSortingEnabled(True)
        self.results_table.resizeColumnsToContents()
