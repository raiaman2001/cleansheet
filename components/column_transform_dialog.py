"""CleanSheet Smart Column Split & Merge Dialog.

Supports splitting delimited strings (e.g., Full Name -> First Name, Last Name)
and concatenating multiple columns with a separator.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QMessageBox, QTabWidget, QWidget, QListWidget, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
from advance_engine import split_column, merge_columns
from components.widgets import Card, PrimaryButton
from theme import ThemeManager


class ColumnTransformDialog(QDialog):
    transform_applied = Signal(object, str)  # (new_df, description)

    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Column Split & Merge Studio")
        self.resize(650, 480)
        self.df = df

        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c.bg}; color: {c.text_primary}; }}
            QComboBox, QLineEdit {{ background-color: {c.input_bg}; color: {c.text_primary}; border: 1px solid {c.input_border}; border-radius: 6px; padding: 6px; }}
            QListWidget {{ background-color: {c.surface}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.tabs = QTabWidget()
        
        # Tab 1: Split Column
        tab_split = QWidget()
        s_layout = QVBoxLayout(tab_split)
        s_layout.setContentsMargins(14, 14, 14, 14)
        s_layout.setSpacing(12)

        s_layout.addWidget(QLabel("Select Column to Split:"))
        self.combo_split_col = QComboBox()
        self.combo_split_col.addItems(list(self.df.columns) if self.df is not None else [])
        s_layout.addWidget(self.combo_split_col)

        s_layout.addWidget(QLabel("Delimiter (Separator character):"))
        self.input_delim = QLineEdit(",")
        self.input_delim.setPlaceholderText("e.g. , or space or -")
        s_layout.addWidget(self.input_delim)

        s_layout.addWidget(QLabel("New Column Names (comma separated):"))
        self.input_new_cols = QLineEdit("First_Name, Last_Name")
        s_layout.addWidget(self.input_new_cols)

        s_layout.addStretch(1)
        btn_run_split = PrimaryButton("Execute Column Split", icon_name="magic")
        btn_run_split.clicked.connect(self._do_split)
        s_layout.addWidget(btn_run_split, alignment=Qt.AlignRight)

        self.tabs.addTab(tab_split, "✂️ Split Column")

        # Tab 2: Merge Columns
        tab_merge = QWidget()
        m_layout = QVBoxLayout(tab_merge)
        m_layout.setContentsMargins(14, 14, 14, 14)
        m_layout.setSpacing(12)

        m_layout.addWidget(QLabel("Select Multiple Columns to Merge (Hold Ctrl to select):"))
        self.list_merge_cols = QListWidget()
        self.list_merge_cols.setSelectionMode(QAbstractItemView.MultiSelection)
        if self.df is not None:
            for col in self.df.columns:
                self.list_merge_cols.addItem(col)
        m_layout.addWidget(self.list_merge_cols, 1)

        m_layout.addWidget(QLabel("New Combined Column Name:"))
        self.input_merge_name = QLineEdit("Full_Address")
        m_layout.addWidget(self.input_merge_name)

        m_layout.addWidget(QLabel("Join Separator:"))
        self.input_merge_sep = QLineEdit(" ")
        m_layout.addWidget(self.input_merge_sep)

        btn_run_merge = PrimaryButton("Execute Column Merge", icon_name="magic")
        btn_run_merge.clicked.connect(self._do_merge)
        m_layout.addWidget(btn_run_merge, alignment=Qt.AlignRight)

        self.tabs.addTab(tab_merge, "🔗 Merge Columns")

        layout.addWidget(self.tabs)

    def _do_split(self):
        col = self.combo_split_col.currentText()
        delim = self.input_delim.text()
        raw_names = self.input_new_cols.text().strip()
        names = [n.strip() for n in raw_names.split(",") if n.strip()] if raw_names else None

        if not col or not delim:
            QMessageBox.warning(self, "Invalid Inputs", "Please select a column and delimiter.")
            return

        new_df = split_column(self.df, col, delimiter=delim, new_names=names, max_split=len(names)-1 if names else 1)
        desc = f"Split column '{col}' by '{delim}'"
        self.transform_applied.emit(new_df, desc)
        self.accept()

    def _do_merge(self):
        selected_items = self.list_merge_cols.selectedItems()
        cols = [it.text() for it in selected_items]
        new_name = self.input_merge_name.text().strip()
        sep = self.input_merge_sep.text()

        if len(cols) < 2 or not new_name:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least 2 columns and specify a new column name.")
            return

        new_df = merge_columns(self.df, cols, new_col_name=new_name, separator=sep)
        desc = f"Merged columns ({', '.join(cols)}) into '{new_name}'"
        self.transform_applied.emit(new_df, desc)
        self.accept()

