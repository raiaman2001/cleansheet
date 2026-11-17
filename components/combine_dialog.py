"""CleanSheet Multi-File Combine & VLOOKUP/Merge Dialog.

Allows users to vertically append multiple files (stack rows)
or horizontally join another file using a common key column (VLOOKUP style).
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QTabWidget, QWidget, QListWidget
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
from advance_engine import append_datasets, join_datasets
from clean_engine import read_data
from components.widgets import Card, PrimaryButton
from theme import ThemeManager


class CombineDialog(QDialog):
    combined_applied = Signal(object, str)  # (new_df, description)

    def __init__(self, current_df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-File Append & Join Studio (VLOOKUP)")
        self.resize(700, 500)
        self.df = current_df
        self.append_file_paths = []
        self.right_df = None

        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c.bg}; color: {c.text_primary}; }}
            QComboBox {{ background-color: {c.input_bg}; color: {c.text_primary}; border: 1px solid {c.input_border}; border-radius: 6px; padding: 6px; }}
            QListWidget {{ background-color: {c.surface}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.tabs = QTabWidget()

        # Tab 1: Append Files (Stack Rows)
        tab_append = QWidget()
        a_layout = QVBoxLayout(tab_append)
        a_layout.setContentsMargins(14, 14, 14, 14)
        a_layout.setSpacing(10)

        a_layout.addWidget(QLabel("Select additional CSV or Excel files to stack vertically below the active dataset:"))
        self.list_files = QListWidget()
        a_layout.addWidget(self.list_files, 1)

        f_btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add Files to Stack")
        btn_add.clicked.connect(self._add_files)
        f_btn_row.addWidget(btn_add)

        btn_clear = QPushButton("Clear List")
        btn_clear.clicked.connect(self._clear_files)
        f_btn_row.addWidget(btn_clear)
        f_btn_row.addStretch(1)

        btn_run_append = PrimaryButton("Execute Append / Stack", icon_name="play")
        btn_run_append.clicked.connect(self._do_append)
        f_btn_row.addWidget(btn_run_append)

        a_layout.addLayout(f_btn_row)
        self.tabs.addTab(tab_append, "📑 Append / Stack Files")

        # Tab 2: VLOOKUP / Join
        tab_join = QWidget()
        j_layout = QVBoxLayout(tab_join)
        j_layout.setContentsMargins(14, 14, 14, 14)
        j_layout.setSpacing(12)

        j_layout.addWidget(QLabel("Select second file to lookup and merge horizontally:"))
        self.lbl_second_file = QLabel("No secondary file selected.")
        self.lbl_second_file.setStyleSheet("color: #64748B; font-weight: 500;")
        j_layout.addWidget(self.lbl_second_file)

        btn_pick_second = QPushButton("Browse Secondary File (.xlsx, .csv)")
        btn_pick_second.clicked.connect(self._pick_second_file)
        j_layout.addWidget(btn_pick_second)

        j_layout.addWidget(QLabel("Common Key Column (e.g. Customer_ID, Product_Code):"))
        self.combo_join_key = QComboBox()
        j_layout.addWidget(self.combo_join_key)

        j_layout.addWidget(QLabel("Join Type:"))
        self.combo_join_type = QComboBox()
        self.combo_join_type.addItems(["left (Keep all rows from current dataset)", "inner (Only matching rows in both)", "outer (Include all rows from both)"])
        j_layout.addWidget(self.combo_join_type)

        j_layout.addStretch(1)
        btn_run_join = PrimaryButton("Execute Join / VLOOKUP", icon_name="magic")
        btn_run_join.clicked.connect(self._do_join)
        j_layout.addWidget(btn_run_join, alignment=Qt.AlignRight)

        self.tabs.addTab(tab_join, "🔗 VLOOKUP / Join Tables")

        layout.addWidget(self.tabs)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files to Append", "", "Spreadsheets (*.csv *.xlsx *.xls)")
        for p in paths:
            if p not in self.append_file_paths:
                self.append_file_paths.append(p)
                self.list_files.addItem(Path(p).name)

    def _clear_files(self):
        self.append_file_paths.clear()
        self.list_files.clear()

    def _do_append(self):
        if not self.append_file_paths:
            QMessageBox.information(self, "No Files", "Please add at least one file to append.")
            return

        dfs = [self.df]
        for p in self.append_file_paths:
            try:
                dfs.append(read_data(p))
            except Exception as e:
                QMessageBox.warning(self, "Could not read file", f"Skipping {Path(p).name}: {e}")

        master_df = append_datasets(dfs)
        desc = f"Stacked {len(dfs)-1} additional file(s) (Total {len(master_df):,} rows)"
        self.combined_applied.emit(master_df, desc)
        self.accept()

    def _pick_second_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Secondary File", "", "Spreadsheets (*.csv *.xlsx *.xls)")
        if not path:
            return

        try:
            self.right_df = read_data(path)
            self.lbl_second_file.setText(f"Loaded: {Path(path).name} ({len(self.right_df):,} rows, {len(self.right_df.columns)} cols)")
            
            # Find matching common columns
            common_cols = [c for c in self.df.columns if c in self.right_df.columns]
            self.combo_join_key.clear()
            self.combo_join_key.addItems(common_cols if common_cols else list(self.df.columns))
        except Exception as e:
            QMessageBox.critical(self, "Error Reading File", str(e))

    def _do_join(self):
        if self.right_df is None:
            QMessageBox.information(self, "No Secondary File", "Please load a secondary file first.")
            return

        key_col = self.combo_join_key.currentText()
        join_how = self.combo_join_type.currentText().split()[0]

        if not key_col:
            QMessageBox.warning(self, "No Key Column", "Please select a common key column.")
            return

        joined_df = join_datasets(self.df, self.right_df, on_col=key_col, how=join_how)
        desc = f"Joined with secondary dataset on '{key_col}' ({join_how} join)"
        self.combined_applied.emit(joined_df, desc)
        self.accept()

