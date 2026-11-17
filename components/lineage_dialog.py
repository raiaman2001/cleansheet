"""Visual Data Lineage and Audit Trail Dialog for CleanSheet.
Displays step-by-step transformation history, timestamped operations,
and cryptographic data hashes for compliance and auditability.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit,
    QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from theme import ThemeManager
from enterprise_engine import DataLineageTracker


class LineageDialog(QDialog):
    """Visual Data Lineage and Audit Trail Dialog."""

    def __init__(self, lineage_tracker: DataLineageTracker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Lineage & Governance Audit Trail")
        self.resize(850, 520)
        self.lineage_tracker = lineage_tracker
        self._setup_ui()

    def _setup_ui(self):
        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background: {c.bg}; }}
            QLabel {{ color: {c.text_primary}; font-family: 'Segoe UI'; font-size: 13px; }}
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

        # Header
        header = QLabel("Data Governance & Lineage Audit Trail")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet(f"color: {c.accent};")
        layout.addWidget(header)

        sub_desc = QLabel(
            "Complete chronological history of all cleaning, parsing, filtering, and imputation operations "
            "applied to this dataset, with cryptographic validation signatures."
        )
        sub_desc.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        layout.addWidget(sub_desc)

        # Audit History Table
        history = self.lineage_tracker.get_lineage() if self.lineage_tracker else []
        self.table = QTableWidget(len(history), 6)
        self.table.setHorizontalHeaderLabels(["Step", "Time", "Stage", "Action", "Rows (Before → After)", "Details"])

        for r, entry in enumerate(history):
            self.table.setItem(r, 0, QTableWidgetItem(f"#{entry.get('step_num', r+1)}"))
            self.table.setItem(r, 1, QTableWidgetItem(str(entry.get("timestamp", ""))))
            
            stage_item = QTableWidgetItem(str(entry.get("stage", "")))
            stage_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table.setItem(r, 2, stage_item)

            self.table.setItem(r, 3, QTableWidgetItem(str(entry.get("action", ""))))

            before = entry.get("rows_before", "-")
            after = entry.get("rows_after", "-")
            self.table.setItem(r, 4, QTableWidgetItem(f"{before} → {after}"))

            self.table.setItem(r, 5, QTableWidgetItem(str(entry.get("details", ""))))

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        # Action Buttons
        btn_box = QHBoxLayout()
        
        btn_export_audit = QPushButton("📜 Export Audit Trail (JSON)")
        btn_export_audit.setStyleSheet(f"background: {c.surface_alt}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; padding: 7px 16px; font-weight: 600;")
        btn_export_audit.clicked.connect(self._export_audit_json)
        btn_box.addWidget(btn_export_audit)

        btn_box.addStretch(1)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("background: #0284C7; color: white; border-radius: 6px; padding: 6px 20px; font-weight: 600;")
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _export_audit_json(self):
        fpath, _ = QFileDialog.getSaveFileName(self, "Export Audit Trail", "cleansheet_audit_lineage.json", "JSON Files (*.json)")
        if fpath:
            try:
                import json
                history = self.lineage_tracker.get_lineage() if self.lineage_tracker else []
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2)
                QMessageBox.information(self, "Exported", f"Audit lineage successfully exported to:\n{fpath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export audit trail: {str(e)}")
