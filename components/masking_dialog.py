"""CleanSheet Privacy & Data Masking Modal Dialog.

Allows users to scan for PII (Personally Identifiable Information) and choose masking
options (Partial, Full, or Hash) to ensure GDPR/HIPAA/DPDP compliance.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
from advance_engine import detect_pii_columns, mask_data
from components.widgets import Card, PrimaryButton
from icons import get_icon


class DataMaskingDialog(QDialog):
    """Interactive modal to review PII columns and select privacy masking rules."""
    masking_applied = Signal(object, dict)  # (masked_df, mask_config)

    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Privacy & Masking Studio (PII)")
        self.resize(820, 540)
        self.df = df
        self.mask_configs = {}

        # Adapt styling to current Light / Dark theme
        from theme import ThemeManager
        c = ThemeManager.instance().colors
        is_dark = ThemeManager.instance().is_dark

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg};
                color: {c.text_primary};
            }}
            QTableWidget {{
                background-color: {c.surface};
                color: {c.text_primary};
                gridline-color: {c.border};
                border: 1px solid {c.border};
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background-color: {c.table_header};
                color: {c.text_secondary};
                font-weight: 600;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {c.border};
            }}
            QComboBox {{
                background-color: {c.input_bg};
                color: {c.text_primary};
                border: 1px solid {c.input_border};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 500;
                min-height: 28px;
            }}
            QComboBox:hover {{
                border-color: {c.accent};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid {c.border};
            }}
            QComboBox QAbstractItemView {{
                background-color: {c.surface};
                color: {c.text_primary};
                selection-background-color: {c.accent};
                selection-color: #FFFFFF;
                border: 1px solid {c.border};
                padding: 4px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header description
        title_box = QVBoxLayout()
        h_lbl = QLabel("Shield Sensitive & Personally Identifiable Information")
        h_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c.accent};")
        d_lbl = QLabel("Select masking actions for sensitive columns before sharing or exporting data.")
        d_lbl.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        title_box.addWidget(h_lbl)
        title_box.addWidget(d_lbl)
        layout.addLayout(title_box)

        # Table of columns
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Column Name", "PII Type Detected", "Sample Value", "Masking Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        # Populate table
        self._populate_table()

        # Action bar
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)

        self.btn_auto_mask = QPushButton("Apply Recommended Masking")
        self.btn_auto_mask.setStyleSheet("padding: 8px 14px; font-weight: 600;")
        self.btn_auto_mask.clicked.connect(self._apply_auto_masking)
        btn_bar.addWidget(self.btn_auto_mask)

        btn_bar.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("padding: 8px 16px;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_apply = PrimaryButton("Apply Privacy Masking", icon_name="shield")
        self.btn_apply.clicked.connect(self._confirm_and_apply)
        btn_bar.addWidget(self.btn_apply)

        layout.addLayout(btn_bar)

    def _populate_table(self):
        if self.df is None or self.df.empty:
            return

        pii_dict = detect_pii_columns(self.df)
        cols = list(self.df.columns)
        self.table.setRowCount(len(cols))

        self.combo_map = {}

        for r, col in enumerate(cols):
            # Col name
            item_name = QTableWidgetItem(col)
            item_name.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(r, 0, item_name)

            # PII tag
            is_pii = col in pii_dict
            tag_text = f"⚠️ {pii_dict[col]['type']} ({int(pii_dict[col]['ratio']*100)}%)" if is_pii else "None"
            item_tag = QTableWidgetItem(tag_text)
            item_tag.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if is_pii:
                item_tag.setForeground(Qt.darkYellow)
            self.table.setItem(r, 1, item_tag)

            # Sample val
            val = self.df[col].dropna().iloc[0] if not self.df[col].dropna().empty else ""
            item_val = QTableWidgetItem(str(val)[:30])
            item_val.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(r, 2, item_val)

            # Combo action
            combo = QComboBox()
            combo.setMinimumWidth(260)
            combo.setFixedHeight(30)
            combo.addItems(["Keep Original (No Mask)", "Partial Mask (jo***@dom.com)", "Full Mask (********)", "SHA-256 Hash Token"])
            if is_pii:
                combo.setCurrentIndex(1)  # Default partial mask for PII
            self.table.setCellWidget(r, 3, combo)
            self.combo_map[col] = combo

    def _apply_auto_masking(self):
        pii_dict = detect_pii_columns(self.df)
        for col, combo in self.combo_map.items():
            if col in pii_dict:
                combo.setCurrentIndex(1)  # Partial
            else:
                combo.setCurrentIndex(0)  # Keep

    def _confirm_and_apply(self):
        mask_cfg = {}
        action_map = {
            1: "partial",
            2: "full",
            3: "hash"
        }
        for col, combo in self.combo_map.items():
            idx = combo.currentIndex()
            if idx in action_map:
                mask_cfg[col] = action_map[idx]

        if not mask_cfg:
            QMessageBox.information(self, "No Masking Selected", "No columns were selected for masking.")
            self.reject()
            return

        masked_df = mask_data(self.df, mask_cfg)
        self.masking_applied.emit(masked_df, mask_cfg)
        self.accept()

