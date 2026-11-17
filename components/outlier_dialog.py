"""CleanSheet Statistical Outlier & Anomaly Studio Dialog.

Detects extreme anomalies and values using Interquartile Range (IQR) & Z-score,
and allows 1-click remediation (Clip to boundary, Impute median, or Drop).
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
from advance_engine import detect_outliers, remediate_outliers
from components.widgets import Card, PrimaryButton
from theme import ThemeManager


class OutlierDialog(QDialog):
    outliers_remediated = Signal(object, dict)  # (remediated_df, remediation_config)

    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Statistical Outlier & Anomaly Studio")
        self.resize(850, 560)
        self.df = df
        self.outlier_info = {}

        c = ThemeManager.instance().colors

        self.setStyleSheet(f"""
            QDialog {{ background-color: {c.bg}; color: {c.text_primary}; }}
            QTableWidget {{ background-color: {c.surface}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 8px; }}
            QHeaderView::section {{ background-color: {c.table_header}; color: {c.text_secondary}; font-weight: 600; padding: 6px; border: none; border-bottom: 1px solid {c.border}; }}
            QComboBox {{ background-color: {c.input_bg}; color: {c.text_primary}; border: 1px solid {c.input_border}; border-radius: 6px; padding: 4px 8px; min-height: 28px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header description
        title_box = QVBoxLayout()
        h_lbl = QLabel("Detect & Remediate Extreme Data Outliers")
        h_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c.accent};")
        d_lbl = QLabel("Statistically identify extreme anomalies (e.g., negative salary, 100x order amounts) and normalize them.")
        d_lbl.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        title_box.addWidget(h_lbl)
        title_box.addWidget(d_lbl)
        layout.addLayout(title_box)

        # Detection method selector
        ctrl_card = Card(elevation=False)
        c_layout = QHBoxLayout(ctrl_card)
        c_layout.setContentsMargins(14, 10, 14, 10)
        c_layout.setSpacing(16)

        c_layout.addWidget(QLabel("Detection Method:"))
        self.radio_iqr = QRadioButton("IQR (Interquartile Range 1.5x)")
        self.radio_iqr.setChecked(True)
        self.radio_zscore = QRadioButton("Z-Score (Standard Deviation 3.0x)")
        c_layout.addWidget(self.radio_iqr)
        c_layout.addWidget(self.radio_zscore)

        self.group = QButtonGroup(self)
        self.group.addButton(self.radio_iqr)
        self.group.addButton(self.radio_zscore)
        self.radio_iqr.toggled.connect(self._run_detection)

        c_layout.addStretch(1)
        layout.addWidget(ctrl_card)

        # Table of outliers
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Numeric Column", "Outliers Detected", "Normal Range [Min, Max]", "Sample Outliers", "Remediation Action"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, 1)

        # Bottom buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(10)
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color: #64748B;")
        btn_bar.addWidget(self.status_lbl)
        btn_bar.addStretch(1)

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("padding: 8px 16px;")
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        self.btn_apply = PrimaryButton("Apply Outlier Remediation", icon_name="magic")
        self.btn_apply.clicked.connect(self._confirm_and_apply)
        btn_bar.addWidget(self.btn_apply)
        layout.addLayout(btn_bar)

        self._run_detection()

    def _run_detection(self):
        method = "iqr" if self.radio_iqr.isChecked() else "zscore"
        thresh = 1.5 if method == "iqr" else 3.0
        self.outlier_info = detect_outliers(self.df, method=method, threshold=thresh)

        self.table.setRowCount(len(self.outlier_info))
        self.action_combos = {}

        if not self.outlier_info:
            self.status_lbl.setText("✅ No statistical outliers detected in numeric columns.")
            return

        total_cnt = sum(info["count"] for info in self.outlier_info.values())
        self.status_lbl.setText(f"Found {total_cnt} outlier value(s) across {len(self.outlier_info)} column(s).")

        for r, (col, info) in enumerate(self.outlier_info.items()):
            self.table.setItem(r, 0, QTableWidgetItem(col))
            cnt_item = QTableWidgetItem(f"⚠️ {info['count']} rows")
            cnt_item.setForeground(Qt.darkRed)
            self.table.setItem(r, 1, cnt_item)
            self.table.setItem(r, 2, QTableWidgetItem(f"[{info['lower_bound']}, {info['upper_bound']} ]"))
            
            samples = ", ".join(str(v) for v in info["values"][:6])
            self.table.setItem(r, 3, QTableWidgetItem(samples))

            combo = QComboBox()
            combo.setMinimumWidth(220)
            combo.addItems(["Clip to Normal Boundaries", "Impute with Column Median", "Drop Outlier Rows", "Ignore (Keep Values)"])
            self.table.setCellWidget(r, 4, combo)
            self.action_combos[col] = combo

    def _confirm_and_apply(self):
        if not self.outlier_info:
            self.reject()
            return

        remediation_cfg = {}
        for col, combo in self.action_combos.items():
            idx = combo.currentIndex()
            if idx == 0:
                action = "clip"
            elif idx == 1:
                action = "median"
            elif idx == 2:
                action = "drop"
            else:
                continue

            info = self.outlier_info[col]
            remediation_cfg[col] = {
                "action": action,
                "lower": info["lower_bound"],
                "upper": info["upper_bound"]
            }

        if not remediation_cfg:
            QMessageBox.information(self, "No Remediation Selected", "No columns were selected for remediation.")
            self.reject()
            return

        remediated_df = remediate_outliers(self.df, remediation_cfg)
        self.outliers_remediated.emit(remediated_df, remediation_cfg)
        self.accept()

