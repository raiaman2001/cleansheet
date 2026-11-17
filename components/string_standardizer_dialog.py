"""CleanSheet Smart String & Pattern Standardizer Studio Dialog.

Provides 1-click normalization for:
1. Phone numbers (E.164, Dashed, or National format)
2. Mixed date heuristics (Converts messy dates to universal ISO YYYY-MM-DD)
3. Address parsing (Extracts Pincode / Zip codes automatically)
4. Case formatting (UPPER, lower, Title, Sentence, snake_case)
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QMessageBox, QTabWidget, QWidget, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
from enterprise_engine import normalize_phone_numbers, parse_mixed_dates, extract_address_components, apply_case_format
from components.widgets import Card, PrimaryButton
from theme import ThemeManager


class StringStandardizerDialog(QDialog):
    standardize_applied = Signal(object, str)  # (new_df, description)

    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart String & Pattern Standardizer")
        self.resize(680, 520)
        self.df = df

        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background-color: {c.bg}; color: {c.text_primary}; }}
            QComboBox {{ background-color: {c.input_bg}; color: {c.text_primary}; border: 1px solid {c.input_border}; border-radius: 6px; padding: 6px; min-height: 28px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header description
        title_box = QVBoxLayout()
        h_lbl = QLabel("Standardize Messy Text, Dates & Phone Formats")
        h_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c.accent};")
        d_lbl = QLabel("Fix messy phone digits, harmonize mixed date styles, or format casing in 1 click.")
        d_lbl.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        title_box.addWidget(h_lbl)
        title_box.addWidget(d_lbl)
        layout.addLayout(title_box)

        self.tabs = QTabWidget()

        # Tab 1: Phone Numbers
        tab_phone = QWidget()
        p_layout = QVBoxLayout(tab_phone)
        p_layout.setContentsMargins(14, 14, 14, 14)
        p_layout.setSpacing(12)

        p_layout.addWidget(QLabel("Select Phone Number Column:"))
        self.combo_phone_col = QComboBox()
        self.combo_phone_col.addItems(list(self.df.columns) if self.df is not None else [])
        p_layout.addWidget(self.combo_phone_col)

        p_layout.addWidget(QLabel("Target Output Format:"))
        self.radio_e164 = QRadioButton("E.164 Universal International (+919876543210)")
        self.radio_e164.setChecked(True)
        self.radio_dashed = QRadioButton("Dashed Grouping (+91-98765-43210)")
        self.radio_national = QRadioButton("Clean National 10-Digit (9876543210)")
        p_layout.addWidget(self.radio_e164)
        p_layout.addWidget(self.radio_dashed)
        p_layout.addWidget(self.radio_national)

        self.phone_group = QButtonGroup(self)
        self.phone_group.addButton(self.radio_e164)
        self.phone_group.addButton(self.radio_dashed)
        self.phone_group.addButton(self.radio_national)

        p_layout.addStretch(1)
        btn_run_phone = PrimaryButton("Standardize Phone Numbers", icon_name="magic")
        btn_run_phone.clicked.connect(self._do_phone_clean)
        p_layout.addWidget(btn_run_phone, alignment=Qt.AlignRight)
        self.tabs.addTab(tab_phone, "📞 Phone Numbers")

        # Tab 2: Smart Dates
        tab_dates = QWidget()
        d_layout = QVBoxLayout(tab_dates)
        d_layout.setContentsMargins(14, 14, 14, 14)
        d_layout.setSpacing(12)

        d_layout.addWidget(QLabel("Select Date Column (Containing Mixed Formats):"))
        self.combo_date_col = QComboBox()
        self.combo_date_col.addItems(list(self.df.columns) if self.df is not None else [])
        d_layout.addWidget(self.combo_date_col)

        d_layout.addWidget(QLabel("Target Universal Date Format:"))
        self.combo_date_fmt = QComboBox()
        self.combo_date_fmt.addItems([
            "YYYY-MM-DD (Universal ISO, e.g. 2026-01-12)",
            "DD/MM/YYYY (Indian/British, e.g. 12/01/2026)",
            "MM/DD/YYYY (US Standard, e.g. 01/12/2026)",
            "DD-Mon-YYYY (e.g. 12-Jan-2026)"
        ])
        d_layout.addWidget(self.combo_date_fmt)

        d_layout.addStretch(1)
        btn_run_date = PrimaryButton("Standardize Dates", icon_name="magic")
        btn_run_date.clicked.connect(self._do_date_clean)
        d_layout.addWidget(btn_run_date, alignment=Qt.AlignRight)
        self.tabs.addTab(tab_dates, "📅 Smart Dates")

        # Tab 3: Case Formatting
        tab_case = QWidget()
        c_layout = QVBoxLayout(tab_case)
        c_layout.setContentsMargins(14, 14, 14, 14)
        c_layout.setSpacing(12)

        c_layout.addWidget(QLabel("Select Text Column to Re-Case:"))
        self.combo_case_col = QComboBox()
        self.combo_case_col.addItems(list(self.df.columns) if self.df is not None else [])
        c_layout.addWidget(self.combo_case_col)

        c_layout.addWidget(QLabel("Select Casing Style:"))
        self.combo_case_style = QComboBox()
        self.combo_case_style.addItems(["Title Case (Aman Rai)", "UPPERCASE (AMAN RAI)", "lowercase (aman rai)", "Sentence case (Aman rai)", "snake_case (aman_rai)"])
        c_layout.addWidget(self.combo_case_style)

        c_layout.addStretch(1)
        btn_run_case = PrimaryButton("Apply Text Casing", icon_name="magic")
        btn_run_case.clicked.connect(self._do_case_clean)
        c_layout.addWidget(btn_run_case, alignment=Qt.AlignRight)
        self.tabs.addTab(tab_case, "🔤 Text Casing")

        # Tab 4: Address / Pincode
        tab_addr = QWidget()
        a_layout = QVBoxLayout(tab_addr)
        a_layout.setContentsMargins(14, 14, 14, 14)
        a_layout.setSpacing(12)

        a_layout.addWidget(QLabel("Select Full Address Column:"))
        self.combo_addr_col = QComboBox()
        self.combo_addr_col.addItems(list(self.df.columns) if self.df is not None else [])
        a_layout.addWidget(self.combo_addr_col)

        desc_pincode = QLabel("Auto-extracts 6-digit Pincodes / Zip codes into a dedicated new column and strips them from the raw address.")
        desc_pincode.setWordWrap(True)
        desc_pincode.setStyleSheet("color: #64748B; font-size: 11px;")
        a_layout.addWidget(desc_pincode)

        a_layout.addStretch(1)
        btn_run_addr = PrimaryButton("Extract Pincode / Zip", icon_name="magic")
        btn_run_addr.clicked.connect(self._do_addr_clean)
        a_layout.addWidget(btn_run_addr, alignment=Qt.AlignRight)
        self.tabs.addTab(tab_addr, "📍 Pincode Extract")

        layout.addWidget(self.tabs)

    def _do_phone_clean(self):
        col = self.combo_phone_col.currentText()
        if not col or self.df is None:
            return
        style = "E164" if self.radio_e164.isChecked() else ("DASHED" if self.radio_dashed.isChecked() else "NATIONAL")
        new_df = self.df.copy()
        new_df[col], stats = normalize_phone_numbers(new_df[col], format_style=style)
        desc = f"Standardized {stats['valid_standardized']} phone numbers in '{col}' ({style})"
        self.standardize_applied.emit(new_df, desc)
        self.accept()

    def _do_date_clean(self):
        col = self.combo_date_col.currentText()
        if not col or self.df is None:
            return
        idx = self.combo_date_fmt.currentIndex()
        fmt_map = {0: "%Y-%m-%d", 1: "%d/%m/%Y", 2: "%m/%d/%Y", 3: "%d-%b-%Y"}
        target_fmt = fmt_map.get(idx, "%Y-%m-%d")
        new_df = self.df.copy()
        new_df[col], stats = parse_mixed_dates(new_df[col], output_format=target_fmt)
        desc = f"Parsed & converted {stats['successfully_converted']} date entries in '{col}'"
        self.standardize_applied.emit(new_df, desc)
        self.accept()

    def _do_case_clean(self):
        col = self.combo_case_col.currentText()
        if not col or self.df is None:
            return
        idx = self.combo_case_style.currentIndex()
        style_map = {0: "title", 1: "upper", 2: "lower", 3: "sentence", 4: "snake"}
        style = style_map.get(idx, "title")
        new_df = self.df.copy()
        new_df[col] = apply_case_format(new_df[col], style=style)
        desc = f"Applied {style} case formatting to column '{col}'"
        self.standardize_applied.emit(new_df, desc)
        self.accept()

    def _do_addr_clean(self):
        col = self.combo_addr_col.currentText()
        if not col or self.df is None:
            return
        new_df = self.df.copy()
        extracted_df = extract_address_components(new_df[col])
        new_df[col] = extracted_df[f"{col}_cleaned"]
        new_df[f"{col}_pincode"] = extracted_df[f"{col}_pincode"]
        desc = f"Extracted pincodes from '{col}' into '{col}_pincode'"
        self.standardize_applied.emit(new_df, desc)
        self.accept()

