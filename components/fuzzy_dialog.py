"""CleanSheet Smart Fuzzy Entity Match & Cluster Merge Dialog.

Provides interactive cluster inspection and 1-click canonical name normalization.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox,
    QSlider, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
from advance_engine import find_fuzzy_clusters, apply_fuzzy_cluster_merges
from components.widgets import Card, PrimaryButton
from icons import get_icon


class FuzzyMergeDialog(QDialog):
    """Interactive modal to review similar entity clusters and merge typo variants."""
    merges_applied = Signal(object, str, dict)  # (cleaned_df, column, merge_map)

    def __init__(self, df: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Smart Fuzzy Entity Deduplication & Merge")
        self.resize(840, 580)
        self.df = df
        self.clusters = []

        from theme import ThemeManager
        c = ThemeManager.instance().colors

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg};
                color: {c.text_primary};
            }}
            QTreeWidget {{
                background-color: {c.surface};
                color: {c.text_primary};
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
                min-height: 28px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c.surface};
                color: {c.text_primary};
                selection-background-color: {c.accent};
                selection-color: #FFFFFF;
                border: 1px solid {c.border};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header description
        title_box = QVBoxLayout()
        h_lbl = QLabel("Resolve Typo Duplicates & Name Variations")
        h_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {c.accent};")
        d_lbl = QLabel("Detect similar names (e.g. 'Infosys Ltd' vs 'Infosys Limited') and merge them into a single primary name.")
        d_lbl.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        title_box.addWidget(h_lbl)
        title_box.addWidget(d_lbl)
        layout.addLayout(title_box)

        # Column Selector & Similarity Slider Bar
        ctrl_card = Card(elevation=False)
        c_layout = QHBoxLayout(ctrl_card)
        c_layout.setContentsMargins(14, 10, 14, 10)
        c_layout.setSpacing(14)

        c_layout.addWidget(QLabel("Target Column:"))
        self.combo_cols = QComboBox()
        str_cols = [c for c in self.df.columns if self.df[c].dtype == object] if self.df is not None else []
        self.combo_cols.addItems(str_cols)
        self.combo_cols.currentIndexChanged.connect(self._run_cluster_search)
        c_layout.addWidget(self.combo_cols, 1)

        c_layout.addWidget(QLabel("Similarity Threshold:"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(60, 95)
        self.slider.setValue(82)
        self.slider.valueChanged.connect(self._on_slider_changed)
        c_layout.addWidget(self.slider)

        self.lbl_thresh = QLabel("82%")
        self.lbl_thresh.setStyleSheet("font-weight: 600; min-width: 32px;")
        c_layout.addWidget(self.lbl_thresh)

        layout.addWidget(ctrl_card)

        # Cluster Tree View
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Cluster Primary / Variants", "Row Frequency", "Match Similarity"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.tree, 1)

        # Bottom Action Bar
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

        self.btn_merge = PrimaryButton("Merge Selected Clusters", icon_name="magic")
        self.btn_merge.clicked.connect(self._confirm_and_merge)
        btn_bar.addWidget(self.btn_merge)

        layout.addLayout(btn_bar)

        # Run initial clustering
        self._run_cluster_search()

    def _on_slider_changed(self, val):
        self.lbl_thresh.setText(f"{val}%")
        self._run_cluster_search()

    def _run_cluster_search(self):
        col = self.combo_cols.currentText()
        if not col or self.df is None or col not in self.df.columns:
            return

        thresh = self.slider.value() / 100.0
        self.clusters = find_fuzzy_clusters(self.df, col, threshold=thresh)
        self.tree.clear()

        if not self.clusters:
            self.status_lbl.setText(f"No typo clusters detected in '{col}' at {int(thresh*100)}% threshold.")
            return

        self.status_lbl.setText(f"Found {len(self.clusters)} cluster(s) with potential duplicates.")

        for c_idx, cluster in enumerate(self.clusters):
            primary = cluster["primary"]
            total_freq = cluster["total_rows"]
            parent_item = QTreeWidgetItem([f"Cluster {c_idx+1}: Canonical Name → '{primary}'", f"{total_freq} rows", "100% Target"])
            parent_item.setFlags(parent_item.flags() | Qt.ItemIsUserCheckable)
            parent_item.setCheckState(0, Qt.Checked)
            parent_item.setData(0, Qt.UserRole, cluster)

            for variant in cluster["variants"]:
                val = variant["val"]
                cnt = variant["count"]
                score = int(variant["score"] * 100)
                is_prim = (val == primary)
                label = f"• {val} (KEEP)" if is_prim else f"↳ {val} → merge to '{primary}'"
                child_item = QTreeWidgetItem([label, f"{cnt} rows", f"{score}%"])
                parent_item.addChild(child_item)

            self.tree.addTopLevelItem(parent_item)

        self.tree.expandAll()

    def _confirm_and_merge(self):
        col = self.combo_cols.currentText()
        if not col or not self.clusters:
            self.reject()
            return

        merge_map = {}
        merged_count = 0

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                cluster = item.data(0, Qt.UserRole)
                primary = cluster["primary"]
                for v in cluster["variants"]:
                    if v["val"] != primary:
                        merge_map[v["val"]] = primary
                        merged_count += v["count"]

        if not merge_map:
            QMessageBox.information(self, "No Clusters Checked", "Please check at least one cluster to merge.")
            return

        cleaned_df = apply_fuzzy_cluster_merges(self.df, col, merge_map)
        self.merges_applied.emit(cleaned_df, col, merge_map)
        self.accept()

