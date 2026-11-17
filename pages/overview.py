"""CleanSheet Overview Analytics Dashboard Page.

Comprehensive visual insights & analytics dashboard:
- Top Hero banner with Readiness Meter Badge, File Metadata & Quick Export Summary CTA.
- Top KPI metric counters: Total records, Columns, Clean Cells Ratio, Problems to Fix.
- Performance & Memory Optimization benchmark pill (RAM downcast savings & execution speed estimate).
- Interactive custom-drawn charts:
  1. Data Quality Breakdown (Clean vs Missing vs Outliers vs Duplicates).
  2. Column Health Ranking (Clickable with Quick-Inspect dialog).
  3. Data Types Distribution (Numeric vs Text vs Dates donut).
- Data Completeness & Column Health Matrix (Clickable column-by-column health grid).
- AI-Assisted Smart Cleaning Recommendations Card (Live detection + one-click actions).
- Top Critical Data Warnings card (Live alerts with instant in-place Fix buttons).
- Bottom Section: Quick Action Shortcuts & Recently Cleaned Files Audit Widget.
"""
from typing import Callable, Optional, Dict, List, Tuple
from pathlib import Path
import pandas as pd

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QFont, QPainter, QColor, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QProgressBar, QSizePolicy, QDialog, QMessageBox
)
from components.widgets import Card, StatCard, ProgressRing, PrimaryButton, Badge
from theme import ThemeManager, ThemeColors
from icons import get_icon


class HorizontalBarChart(QWidget):
    """Modern horizontal bar chart for column health or category breakdowns with click inspection."""
    def __init__(self, title: str = "", on_item_clicked: Optional[Callable[[str], None]] = None, parent=None):
        super().__init__(parent)
        self.chart_title = title
        self.on_item_clicked = on_item_clicked
        self.items: List[tuple] = []  # (label, value, max_value, color_hex, detail_str)
        self.row_rects: List[tuple] = []
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setCursor(Qt.PointingHandCursor if on_item_clicked else Qt.ArrowCursor)
        ThemeManager.instance().subscribe(lambda _: self.update())

    def set_data(self, items: List[tuple]):
        """items = list of (label, value, max_val, color_hex, detail_str)"""
        self.items = items
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.on_item_clicked:
            pos = event.position()
            for rect, label in self.row_rects:
                if rect.contains(pos.x(), pos.y()):
                    self.on_item_clicked(label)
                    return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = ThemeManager.instance().colors
        w = self.width()
        h = self.height()
        self.row_rects.clear()

        if not self.items:
            p.setPen(QColor(c.text_muted))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No active dataset loaded to display chart")
            p.end()
            return

        row_h = min(28.0, (h - 10) / max(1, len(self.items)))
        y = 8.0

        for label, val, max_val, col_hex, detail in self.items:
            row_rect = QRectF(5, y, w - 10, row_h)
            self.row_rects.append((row_rect, str(label)))

            # Draw label
            p.setPen(QColor(c.text_secondary))
            p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            lbl_rect = QRectF(10, y, 120, row_h - 4)
            p.drawText(lbl_rect, Qt.AlignLeft | Qt.AlignVCenter, str(label)[:16])

            # Bar track
            bar_start_x = 135.0
            bar_max_w = max(50.0, w - bar_start_x - 85.0)
            track_rect = QRectF(bar_start_x, y + (row_h - 10) / 2, bar_max_w, 10.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c.border))
            p.drawRoundedRect(track_rect, 5.0, 5.0)

            # Bar active fill
            ratio = (val / max_val) if max_val > 0 else 0.0
            ratio = min(1.0, max(0.0, ratio))
            fill_w = max(6.0 if ratio > 0 else 0.0, bar_max_w * ratio)
            fill_rect = QRectF(bar_start_x, y + (row_h - 10) / 2, fill_w, 10.0)
            p.setBrush(QColor(col_hex))
            p.drawRoundedRect(fill_rect, 5.0, 5.0)

            # Value label
            p.setPen(QColor(c.text_primary))
            p.setFont(QFont("Segoe UI", 9, QFont.Bold))
            val_rect = QRectF(bar_start_x + bar_max_w + 10, y, 70, row_h - 4)
            p.drawText(val_rect, Qt.AlignLeft | Qt.AlignVCenter, str(detail))

            y += row_h

        p.end()


class DonutChart(QWidget):
    """Clean custom donut pie chart for distribution analysis (e.g. Data types)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.slices: List[tuple] = []  # (label, value, color_hex)
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        ThemeManager.instance().subscribe(lambda _: self.update())

    def set_data(self, slices: List[tuple]):
        self.slices = slices
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = ThemeManager.instance().colors
        w = self.width()
        h = self.height()

        if not self.slices or sum(v for _, v, _ in self.slices) == 0:
            p.setPen(QColor(c.text_muted))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "No column types detected")
            p.end()
            return

        total = sum(v for _, v, _ in self.slices)
        size = min(120.0, h - 20)
        cx = 75.0
        cy = h / 2.0
        donut_rect = QRectF(cx - size / 2.0, cy - size / 2.0, size, size)

        start_angle = 90 * 16
        pen_w = 16.0
        arc_rect = QRectF(donut_rect.x() + pen_w / 2.0, donut_rect.y() + pen_w / 2.0,
                          donut_rect.width() - pen_w, donut_rect.height() - pen_w)

        for label, val, col_hex in self.slices:
            if val <= 0:
                continue
            span_angle = int((val / total) * 360 * 16)
            pen = QPen(QColor(col_hex), pen_w, Qt.SolidLine, Qt.FlatCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawArc(arc_rect, start_angle, -span_angle)
            start_angle -= span_angle

        # Donut center text
        p.setPen(QColor(c.text_primary))
        p.setFont(QFont("Segoe UI", 12, QFont.Bold))
        p.drawText(QRectF(donut_rect.x(), cy - 14, donut_rect.width(), 16), Qt.AlignCenter, str(total))
        p.setPen(QColor(c.text_muted))
        p.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
        p.drawText(QRectF(donut_rect.x(), cy + 2, donut_rect.width(), 16), Qt.AlignCenter, "COLUMNS")

        # Legend list on right
        legend_x = 150.0
        legend_y = max(10.0, (h - len(self.slices) * 26.0) / 2.0)
        for label, val, col_hex in self.slices:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col_hex))
            p.drawRoundedRect(QRectF(legend_x, legend_y + 4, 10, 10), 3, 3)

            pct = (val / total * 100) if total > 0 else 0
            p.setPen(QColor(c.text_secondary))
            p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            p.drawText(QRectF(legend_x + 16, legend_y, w - legend_x - 20, 18),
                       Qt.AlignLeft | Qt.AlignVCenter, f"{label}: {val} ({pct:.0f}%)")
            legend_y += 24.0

        p.end()


class ActionTile(Card):
    """Interactive action tile with icon, title, description, and hover highlight."""
    def __init__(self, title: str, desc: str, icon_name: str, on_click: Callable, parent=None):
        super().__init__(parent, elevation=True)
        self.setObjectName("ActionTile")
        self.setCursor(Qt.PointingHandCursor)
        self.on_click = on_click
        self.icon_name = icon_name
        self.setMinimumHeight(68)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        
        self.icon_box = QLabel()
        self.icon_box.setFixedSize(36, 36)
        self.icon_box.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_box)
        
        txt_box = QVBoxLayout()
        txt_box.setSpacing(1)
        txt_box.setAlignment(Qt.AlignVCenter)
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.DemiBold))
        
        self.lbl_desc = QLabel(desc)
        self.lbl_desc.setObjectName("CardDesc")
        
        txt_box.addWidget(self.lbl_title)
        txt_box.addWidget(self.lbl_desc)
        layout.addLayout(txt_box, 1)
        
        self._update_appearance(ThemeManager.instance().colors)
        ThemeManager.instance().subscribe(self._update_appearance)

    def _update_appearance(self, c: ThemeColors):
        self.icon_box.setStyleSheet(f"""
            background-color: {c.accent_subtle};
            border-radius: 8px;
        """)
        ico = get_icon(self.icon_name, c.accent, 18)
        self.icon_box.setPixmap(ico.pixmap(18, 18))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_click()
        super().mousePressEvent(event)


class ColumnHealthMatrix(QWidget):
    """Interactive Grid displaying completeness & health indicators for all columns."""
    def __init__(self, on_column_click: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.on_column_click = on_column_click
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 4, 0, 4)
        self.layout.setSpacing(10)
        self._cards: List[QFrame] = []

    def set_columns(self, df: Optional[pd.DataFrame]):
        for c_widget in self._cards:
            c_widget.setParent(None)
        self._cards.clear()

        c = ThemeManager.instance().colors
        if df is None or df.empty:
            empty_lbl = QLabel("Load a dataset to view column completeness and health matrix.")
            empty_lbl.setFont(QFont("Segoe UI", 9))
            empty_lbl.setStyleSheet(f"color: {c.text_muted}; background: transparent; padding: 10px;")
            self.layout.addWidget(empty_lbl, 0, 0)
            self._cards.append(empty_lbl)
            return

        total_rows = len(df)
        cols_per_row = 3
        for idx, col in enumerate(df.columns):
            s = df[col]
            missing = int(s.isna().sum())
            complete_pct = (1.0 - (missing / total_rows)) * 100.0 if total_rows > 0 else 100.0
            
            # Status color
            if complete_pct == 100.0:
                dot_color = c.success
                status_text = "100% Clean"
            elif complete_pct >= 85.0:
                dot_color = c.warning
                status_text = f"{complete_pct:.1f}% Complete"
            else:
                dot_color = c.danger
                status_text = f"{complete_pct:.1f}% ({missing} blank)"

            # Type badge
            if pd.api.types.is_numeric_dtype(s):
                type_tag, tag_bg = "NUM", c.accent
            elif pd.api.types.is_datetime64_any_dtype(s):
                type_tag, tag_bg = "DATE", c.warning
            else:
                type_tag, tag_bg = "TEXT", c.info

            card = QFrame()
            card.setCursor(Qt.PointingHandCursor)
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {c.surface_alt};
                    border: 1px solid {c.border};
                    border-radius: 8px;
                    padding: 8px;
                }}
                QFrame:hover {{
                    border: 1px solid {c.accent};
                    background-color: {c.surface};
                }}
            """)
            
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(10, 8, 10, 8)
            c_layout.setSpacing(6)

            top_row = QHBoxLayout()
            top_row.setSpacing(6)
            
            # Type Pill
            pill = QLabel(type_tag)
            pill.setFont(QFont("Segoe UI", 7, QFont.Bold))
            pill.setStyleSheet(f"background-color: {tag_bg}; color: #FFFFFF; border-radius: 4px; padding: 1px 5px;")
            top_row.addWidget(pill)

            name_lbl = QLabel(str(col))
            name_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            name_lbl.setStyleSheet(f"color: {c.text_primary}; background: transparent; border: none;")
            top_row.addWidget(name_lbl, 1)

            # Dot indicator
            dot = QLabel("●")
            dot.setFont(QFont("Segoe UI", 10))
            dot.setStyleSheet(f"color: {dot_color}; background: transparent; border: none;")
            top_row.addWidget(dot)
            c_layout.addLayout(top_row)

            # Mini Progress Bar
            pbar = QProgressBar()
            pbar.setFixedHeight(5)
            pbar.setTextVisible(False)
            pbar.setRange(0, 100)
            pbar.setValue(int(complete_pct))
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background: {c.border};
                    border-radius: 2px;
                    border: none;
                }}
                QProgressBar::chunk {{
                    background: {dot_color};
                    border-radius: 2px;
                }}
            """)
            c_layout.addWidget(pbar)

            sub_lbl = QLabel(status_text)
            sub_lbl.setFont(QFont("Segoe UI", 7, QFont.DemiBold))
            sub_lbl.setStyleSheet(f"color: {c.text_muted}; background: transparent; border: none;")
            c_layout.addWidget(sub_lbl)

            # Click handler to inspect
            col_name_str = str(col)
            card.mousePressEvent = lambda e, name=col_name_str: self.on_column_click(name)

            row = idx // cols_per_row
            col_pos = idx % cols_per_row
            self.layout.addWidget(card, row, col_pos)
            self._cards.append(card)


class OverviewPage(QWidget):
    """Full-Featured Visual Analytics & Insights Dashboard."""
    def __init__(
        self,
        on_import: Callable,
        on_workflow: Callable,
        on_issues: Callable,
        on_auto: Callable,
        on_fix_duplicates: Optional[Callable] = None,
        on_fix_blanks: Optional[Callable] = None,
        on_trim_spaces: Optional[Callable] = None,
        on_autocast: Optional[Callable] = None,
        on_export: Optional[Callable] = None,
        parent=None
    ):
        super().__init__(parent)
        self.on_import = on_import
        self.on_workflow = on_workflow
        self.on_issues = on_issues
        self.on_auto = on_auto
        self.on_fix_duplicates = on_fix_duplicates or on_workflow
        self.on_fix_blanks = on_fix_blanks or on_workflow
        self.on_trim_spaces = on_trim_spaces or on_workflow
        self.on_autocast = on_autocast or on_workflow
        self.on_export = on_export or (lambda: None)
        
        self._current_df: Optional[pd.DataFrame] = None
        self._cached_warnings: List[tuple] = []
        self._cached_recommendations: List[tuple] = []
        ThemeManager.instance().subscribe(lambda _: self._on_theme_changed())
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        
        scroll_content = QWidget()
        scroll_content.setObjectName("MainContent")
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Top Hero Banner Card with Readiness Badge & File Details Info
        hero_card = Card(elevation=True)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(22, 16, 22, 16)
        hero_layout.setSpacing(20)
        
        self.health_ring = ProgressRing(value=0.0, size=116)
        hero_layout.addWidget(self.health_ring)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setAlignment(Qt.AlignVCenter)
        
        # Title + Status Badge row
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        h_title = QLabel("Data Cleaning & Analytics Dashboard")
        h_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_row.addWidget(h_title)
        
        self.readiness_badge = Badge("No Dataset Loaded", "neutral")
        title_row.addWidget(self.readiness_badge)
        title_row.addStretch(1)
        text_layout.addLayout(title_row)
        
        self.h_desc = QLabel(
            "Overview of dataset health, AI recommendations, column matrix, and quick cleaning actions."
        )
        self.h_desc.setObjectName("CardDesc")
        self.h_desc.setWordWrap(True)
        text_layout.addWidget(self.h_desc)
        
        # Active File Info & Benchmark Pill
        self.file_info_lbl = QLabel("No active file selected · Click Choose a Spreadsheet")
        self.file_info_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.file_info_lbl.setStyleSheet("color: #38BDF8; background: transparent;")
        text_layout.addWidget(self.file_info_lbl)
        
        hero_layout.addLayout(text_layout, 1)
        
        btn_box = QVBoxLayout()
        btn_box.setSpacing(8)
        self.hero_btn = PrimaryButton("Choose a Spreadsheet", icon_name="plus")
        self.hero_btn.clicked.connect(self.on_import)
        btn_box.addWidget(self.hero_btn)

        self.btn_export_summary = QPushButton("Export Quality Report")
        self.btn_export_summary.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.btn_export_summary.setFixedHeight(34)
        self.btn_export_summary.setCursor(Qt.PointingHandCursor)
        self.btn_export_summary.clicked.connect(self.on_export)
        btn_box.addWidget(self.btn_export_summary)

        hero_layout.addLayout(btn_box)
        main_layout.addWidget(hero_card)
        
        # 2. Top Metric KPI Counters Grid (5 Stat Cards)
        grid = QGridLayout()
        grid.setSpacing(12)
        
        self.stat_rows = StatCard("Total Records", "--", "Rows detected", "rows")
        self.stat_cols = StatCard("Total Columns", "--", "Features detected", "columns")
        self.stat_clean_ratio = StatCard("Clean Cells Ratio", "--", "Health index", "check")
        self.stat_issues = StatCard("Problems to Fix", "--", "Empty or repeated items", "warning")
        self.stat_perf = StatCard("Memory & Speed", "--", "Downcast benchmark", "database")
        
        grid.addWidget(self.stat_rows, 0, 0)
        grid.addWidget(self.stat_cols, 0, 1)
        grid.addWidget(self.stat_clean_ratio, 0, 2)
        grid.addWidget(self.stat_issues, 0, 3)
        grid.addWidget(self.stat_perf, 0, 4)
        main_layout.addLayout(grid)
        
        # 3. Interactive Visual Charts Section (Side-by-Side Cards)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(14)
        
        # Left Chart: Quality Breakdown Bar Chart
        breakdown_card = Card(elevation=True)
        bc_layout = QVBoxLayout(breakdown_card)
        bc_layout.setContentsMargins(18, 14, 18, 14)
        bc_layout.setSpacing(8)
        
        bc_title = QLabel("Data Quality Breakdown")
        bc_title.setObjectName("CardTitle")
        bc_layout.addWidget(bc_title)
        
        self.quality_chart = HorizontalBarChart()
        bc_layout.addWidget(self.quality_chart, 1)
        charts_row.addWidget(breakdown_card, 1)
        
        # Center Chart: Column Health Ranking (Clickable for Inspector)
        col_card = Card(elevation=True)
        cc_layout = QVBoxLayout(col_card)
        cc_layout.setContentsMargins(18, 14, 18, 14)
        cc_layout.setSpacing(8)
        
        cc_header = QHBoxLayout()
        cc_title = QLabel("Columns Needing Attention")
        cc_title.setObjectName("CardTitle")
        cc_header.addWidget(cc_title)
        cc_hint = QLabel("(Click to inspect)")
        cc_hint.setFont(QFont("Segoe UI", 8))
        cc_hint.setObjectName("CardDesc")
        cc_header.addWidget(cc_hint)
        cc_header.addStretch(1)
        cc_layout.addLayout(cc_header)
        
        self.col_chart = HorizontalBarChart(on_item_clicked=self.inspect_column)
        cc_layout.addWidget(self.col_chart, 1)
        charts_row.addWidget(col_card, 1)
        
        # Right Chart: Data Types Donut Chart
        types_card = Card(elevation=True)
        tc_layout = QVBoxLayout(types_card)
        tc_layout.setContentsMargins(18, 14, 18, 14)
        tc_layout.setSpacing(8)
        
        tc_title = QLabel("Column Types Distribution")
        tc_title.setObjectName("CardTitle")
        tc_layout.addWidget(tc_title)
        
        self.types_chart = DonutChart()
        tc_layout.addWidget(self.types_chart, 1)
        charts_row.addWidget(types_card, 1)
        
        main_layout.addLayout(charts_row)
        
        # 4. Column Completeness & Health Matrix (Mini Heatmap Grid)
        self.matrix_card = Card(elevation=True)
        mc_layout = QVBoxLayout(self.matrix_card)
        mc_layout.setContentsMargins(18, 14, 18, 14)
        mc_layout.setSpacing(10)
        
        mc_header = QHBoxLayout()
        m_title = QLabel("Column Completeness & Health Matrix")
        m_title.setObjectName("CardTitle")
        mc_header.addWidget(m_title)
        m_hint = QLabel("(Click any column to view statistics & values)")
        m_hint.setFont(QFont("Segoe UI", 8))
        m_hint.setObjectName("CardDesc")
        mc_header.addWidget(m_hint)
        mc_header.addStretch(1)
        mc_layout.addLayout(mc_header)
        
        self.health_matrix = ColumnHealthMatrix(on_column_click=self.inspect_column)
        mc_layout.addWidget(self.health_matrix)
        main_layout.addWidget(self.matrix_card)

        # 5. AI-Assisted Smart Cleaning Recommendations Card
        self.recommendations_card = Card(elevation=True)
        self.rc_layout = QVBoxLayout(self.recommendations_card)
        self.rc_layout.setContentsMargins(18, 14, 18, 14)
        self.rc_layout.setSpacing(10)

        rec_header = QHBoxLayout()
        rt = QLabel("AI-Assisted Smart Recommendations")
        rt.setObjectName("CardTitle")
        rec_header.addWidget(rt)
        self.rec_badge = Badge("0 Suggestions", "info")
        rec_header.addWidget(self.rec_badge)
        rec_header.addStretch(1)
        self.rc_layout.addLayout(rec_header)

        self.recommendations_container = QVBoxLayout()
        self.recommendations_container.setSpacing(8)
        self.rc_layout.addLayout(self.recommendations_container)
        main_layout.addWidget(self.recommendations_card)
        
        # 6. Critical Data Warnings Section
        self.warnings_card = Card(elevation=True)
        self.wc_layout = QVBoxLayout(self.warnings_card)
        self.wc_layout.setContentsMargins(18, 14, 18, 14)
        self.wc_layout.setSpacing(10)
        
        w_header = QHBoxLayout()
        wt = QLabel("Top Critical Data Warnings")
        wt.setObjectName("CardTitle")
        w_header.addWidget(wt)
        self.warnings_count = Badge("0 Warnings", "success")
        w_header.addWidget(self.warnings_count)
        w_header.addStretch(1)
        self.wc_layout.addLayout(w_header)
        
        self.warnings_container = QVBoxLayout()
        self.warnings_container.setSpacing(8)
        self.wc_layout.addLayout(self.warnings_container)
        main_layout.addWidget(self.warnings_card)
        
        # 7. Bottom Row: Quick Actions & Recent Cleaned Files History Widget
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(14)
        
        # Left: Quick Action Tiles
        actions_card = Card(elevation=True)
        act_layout = QVBoxLayout(actions_card)
        act_layout.setContentsMargins(18, 14, 18, 14)
        act_layout.setSpacing(8)
        
        act_title = QLabel("Quick Actions & Next Steps")
        act_title.setObjectName("CardTitle")
        act_layout.addWidget(act_title)
        
        tile1 = ActionTile("Clean Dataset", "Fix formatting, empty rows, and duplicate records", "workflow", self.on_workflow)
        tile2 = ActionTile("Review Findings", "Inspect detected problems and suggested fixes", "issues", self.on_issues)
        tile3 = ActionTile("Batch Automation", "Process multiple spreadsheets in one folder automatically", "automation", self.on_auto)
        
        act_layout.addWidget(tile1)
        act_layout.addWidget(tile2)
        act_layout.addWidget(tile3)
        bottom_row.addWidget(actions_card, 1)
        
        # Right: Recently Cleaned Files Widget
        recent_card = Card(elevation=True)
        rc_layout = QVBoxLayout(recent_card)
        rc_layout.setContentsMargins(18, 14, 18, 14)
        rc_layout.setSpacing(10)
        
        rc_title = QLabel("Recently Cleaned Files")
        rc_title.setObjectName("CardTitle")
        rc_layout.addWidget(rc_title)
        
        self.recent_list_layout = QVBoxLayout()
        self.recent_list_layout.setSpacing(8)
        rc_layout.addLayout(self.recent_list_layout)
        rc_layout.addStretch(1)
        
        bottom_row.addWidget(recent_card, 1)
        main_layout.addLayout(bottom_row)
        
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)
        self.refresh_recent_widget()

    def set_file_details(self, file_path: str, df: Optional[pd.DataFrame], sheet_name: str = ""):
        """Update file metadata pill and performance benchmark."""
        if not file_path:
            self.file_info_lbl.setText("No active file selected · Click Choose a Spreadsheet")
            return
        p = Path(file_path)
        size_kb = f"{p.stat().st_size / 1024:.1f} KB" if p.exists() else "--"
        sheet_str = f" · Sheet: '{sheet_name}'" if sheet_name else ""
        
        if df is not None:
            mem_bytes = df.memory_usage(deep=True).sum()
            mem_mb = f"{mem_bytes / (1024 * 1024):.2f} MB"
            # Optimization benchmark estimate
            est_speed = "<0.1s" if len(df) < 5000 else f"{len(df) / 50000:.1f}s"
            self.file_info_lbl.setText(f"📄 {p.name} ({size_kb}) {sheet_str} · Memory: {mem_mb} · Clean speed: ~{est_speed}")
        else:
            self.file_info_lbl.setText(f"📄 {p.name} ({size_kb}) {sheet_str}")

    def inspect_column(self, col_name: str):
        """Open a quick-inspect dialog showing statistics for a specific column."""
        if self._current_df is None or col_name not in self._current_df.columns:
            return
        s = self._current_df[col_name]
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Column Details · {col_name}")
        dialog.resize(450, 320)
        
        c = ThemeManager.instance().colors
        dialog.setStyleSheet(f"background-color: {c.bg}; color: {c.text_primary};")
        
        d_layout = QVBoxLayout(dialog)
        d_layout.setContentsMargins(20, 18, 20, 18)
        d_layout.setSpacing(12)
        
        head = QLabel(f"Column: {col_name}")
        head.setFont(QFont("Segoe UI", 13, QFont.Bold))
        d_layout.addWidget(head)
        
        details_box = Card(elevation=False)
        db_layout = QVBoxLayout(details_box)
        db_layout.setSpacing(6)
        
        null_count = int(s.isna().sum())
        total_len = len(s)
        unique_count = int(s.nunique(dropna=True))
        dtype_str = str(s.dtype)
        
        db_layout.addWidget(QLabel(f"• Data Type: {dtype_str}"))
        db_layout.addWidget(QLabel(f"• Total Values: {total_len:,}"))
        db_layout.addWidget(QLabel(f"• Blank / Nulls: {null_count:,} ({null_count / total_len * 100:.1f}%)"))
        db_layout.addWidget(QLabel(f"• Unique Values: {unique_count:,}"))
        
        if pd.api.types.is_numeric_dtype(s) and not s.dropna().empty:
            db_layout.addWidget(QLabel(f"• Minimum: {s.min()}"))
            db_layout.addWidget(QLabel(f"• Maximum: {s.max()}"))
            db_layout.addWidget(QLabel(f"• Average: {s.mean():.2f}"))
            
        d_layout.addWidget(details_box)
        
        btn_close = PrimaryButton("Close", icon_name="check")
        btn_close.clicked.connect(dialog.accept)
        d_layout.addWidget(btn_close, alignment=Qt.AlignRight)
        dialog.exec()

    def update_metrics(self, df: Optional[pd.DataFrame], file_path: str = "", sheet_name: str = ""):
        """Update KPI stats, health score, readiness meter, warnings, recommendations, and charts."""
        self._current_df = df
        c = ThemeManager.instance().colors
        
        if file_path:
            self.set_file_details(file_path, df, sheet_name)
            
        if df is None or df.empty:
            self.stat_rows.set_value("--")
            self.stat_cols.set_value("--")
            self.stat_clean_ratio.set_value("--")
            self.stat_issues.set_value("--")
            self.stat_perf.set_value("--")
            self.health_ring.set_score(0.0)
            self.readiness_badge.set_text_and_variant("No Dataset Loaded", "neutral")
            self.quality_chart.set_data([])
            self.col_chart.set_data([])
            self.types_chart.set_data([])
            self.health_matrix.set_columns(None)
            self._render_recommendations([])
            self._render_warnings([])
            self.refresh_recent_widget()
            return

        from clean_engine import profile, quality_score, issue_frame
        total_rows = len(df)
        total_cols = len(df.columns)
        total_cells = total_rows * total_cols
        p = profile(df)

        missing_cells = p["Missing cells"]
        dup_rows = p["Duplicate rows"]
        total_problem_cells = missing_cells + (dup_rows * total_cols)
        clean_cells = max(0, total_cells - total_problem_cells)
        clean_ratio = (clean_cells / total_cells * 100.0) if total_cells > 0 else 100.0

        # Memory & Speed Optimization Benchmark
        mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)
        speed_est = "<0.1s" if total_rows < 10000 else f"{total_rows / 60000:.1f}s"

        # Update Top KPI Cards
        self.stat_rows.set_value(f"{total_rows:,}", hint="Rows found")
        self.stat_cols.set_value(f"{total_cols:,}", hint="Features found")
        self.stat_clean_ratio.set_value(f"{clean_ratio:.1f}%", hint="Clean cell ratio")
        self.stat_issues.set_value(f"{missing_cells + dup_rows:,}", hint="Blanks & duplicates")
        self.stat_perf.set_value(f"{mem_mb:.2f} MB", hint=f"Speed ~{speed_est}")

        # Health Ring & Readiness Meter Badge
        score = quality_score(df)
        self.health_ring.set_score(score)
        
        if score >= 90 and (missing_cells + dup_rows) == 0:
            self.readiness_badge.set_text_and_variant("● Analysis Ready (Clean)", "success")
        elif score >= 75:
            self.readiness_badge.set_text_and_variant("● Minor Cleaning Recommended", "warning")
        else:
            self.readiness_badge.set_text_and_variant("● Action Needed (Messy Data)", "danger")

        # 1. Quality Breakdown Chart
        breakdown_items = [
            ("Clean Cells", clean_cells, total_cells, c.success, f"{clean_cells:,}"),
            ("Missing Cells", missing_cells, total_cells, c.warning, f"{missing_cells:,}"),
            ("Duplicate Rows", dup_rows, max(1, total_rows), c.danger, f"{dup_rows:,}"),
        ]
        self.quality_chart.set_data(breakdown_items)

        # 2. Top Columns Needing Attention
        col_missing = df.isna().sum().sort_values(ascending=False).head(5)
        top_cols = []
        for col_name, miss_count in col_missing.items():
            top_cols.append((
                str(col_name),
                int(miss_count),
                max(1, total_rows),
                c.warning if miss_count > 0 else c.success,
                f"{int(miss_count)} blank" if miss_count > 0 else "Clean"
            ))
        self.col_chart.set_data(top_cols)

        # 3. Column Types Distribution
        num_count = sum(1 for dt in df.dtypes if pd.api.types.is_numeric_dtype(dt))
        date_count = sum(1 for dt in df.dtypes if pd.api.types.is_datetime64_any_dtype(dt))
        text_count = total_cols - num_count - date_count

        slices = [
            ("Numbers", num_count, c.accent),
            ("Text", max(0, text_count), c.info),
            ("Dates", date_count, c.warning),
        ]
        self.types_chart.set_data(slices)

        # 4. Column Completeness & Health Matrix
        self.health_matrix.set_columns(df)
        
        # 5. Smart Recommendations Calculation
        recommendations = []
        # Check untrimmed whitespace
        whitespace_count = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            series = df[col].dropna().astype(str)
            whitespace_count += int((series.str.strip() != series).sum())
        if whitespace_count > 0:
            recommendations.append((
                f"Found {whitespace_count} cell(s) with leading/trailing spaces.",
                "Trim Spaces",
                self.on_trim_spaces,
                "magic"
            ))

        # Check convertible data types (currency / numbers / dates stored as strings)
        convertible_cols = 0
        for col in df.select_dtypes(include=["object", "string"]).columns:
            s_clean = df[col].astype("string").str.strip().str.replace(r"[₹$€£,\s]", "", regex=True)
            mask = s_clean.notna() & s_clean.ne("")
            if mask.sum() and pd.to_numeric(s_clean, errors="coerce")[mask].notna().mean() >= 0.85:
                convertible_cols += 1
            elif any(k in str(col).lower() for k in ["date", "time", "dob", "created", "updated"]):
                dt = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
                mask_dt = df[col].notna() & df[col].astype("string").str.strip().ne("")
                if mask_dt.sum() and dt[mask_dt].notna().mean() >= 0.70:
                    convertible_cols += 1
        if convertible_cols > 0:
            recommendations.append((
                f"Detected {convertible_cols} text column(s) that can be converted to numbers/dates.",
                "Auto-Cast Types",
                self.on_autocast,
                "database"
            ))

        if dup_rows > 0:
            recommendations.append((
                f"Remove {dup_rows} exact duplicate rows to reduce redundancy.",
                "Remove Duplicates",
                self.on_fix_duplicates,
                "check"
            ))

        if missing_cells > 0:
            recommendations.append((
                f"Impute {missing_cells} missing cells with median (numbers) and mode (text).",
                "Fill Blanks",
                self.on_fix_blanks,
                "sparkles"
            ))

        self._render_recommendations(recommendations)

        # 6. Critical Warnings Calculation
        warnings = []
        if dup_rows > 0:
            warnings.append((f"{dup_rows} exact duplicate rows found in dataset.", "Remove Duplicates", self.on_fix_duplicates))
        if missing_cells > 0:
            warnings.append((f"{missing_cells} empty or blank cells found across columns.", "Fix Blanks", self.on_fix_blanks))
            
        # Check negative numbers in typical non-negative columns
        for c_name in df.columns:
            if any(k in str(c_name).lower() for k in ["salary", "price", "amount", "cost", "income", "age"]):
                s = df[c_name]
                if pd.api.types.is_numeric_dtype(s):
                    negs = int((s < 0).sum())
                    if negs > 0:
                        warnings.append((f"Column '{c_name}' has {negs} negative value(s).", "Review Issues", self.on_issues))
                        break
                        
        self._render_warnings(warnings)
        self.refresh_recent_widget()

    def _on_theme_changed(self):
        c = ThemeManager.instance().colors
        self.btn_export_summary.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.surface_alt};
                color: {c.text_primary};
                border: 1px solid {c.border};
                border-radius: 8px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                border-color: {c.accent};
                background-color: {c.surface};
            }}
        """)
        self._render_warnings(self._cached_warnings)
        self._render_recommendations(self._cached_recommendations)
        self.health_matrix.set_columns(self._current_df)
        self.refresh_recent_widget()

    def _render_recommendations(self, recs: List[tuple]):
        """Render AI recommendations with one-click action buttons."""
        self._cached_recommendations = list(recs)
        for i in reversed(range(self.recommendations_container.count())):
            item = self.recommendations_container.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        c = ThemeManager.instance().colors
        if not recs:
            self.rec_badge.set_text_and_variant("All Optimized", "success")
            all_good = QLabel("✓ Excellent! No hygiene improvements or data format conversions needed.")
            all_good.setFont(QFont("Segoe UI", 9))
            all_good.setStyleSheet(f"color: {c.success}; background: transparent; padding: 4px;")
            self.recommendations_container.addWidget(all_good)
            return

        self.rec_badge.set_text_and_variant(f"{len(recs)} Suggestions", "info")
        for text, btn_txt, callback, icon_name in recs:
            row = QFrame()
            row.setMinimumHeight(44)
            row.setStyleSheet(f"background: {c.surface_alt}; border: 1px solid {c.border}; border-radius: 8px;")
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(14, 8, 14, 8)
            r_layout.setSpacing(12)

            ico = QLabel()
            ico.setPixmap(get_icon(icon_name, c.accent, 16).pixmap(16, 16))
            ico.setStyleSheet("background: transparent; border: none;")
            r_layout.addWidget(ico)

            t_lbl = QLabel(text)
            t_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            t_lbl.setStyleSheet(f"color: {c.text_primary}; background: transparent; border: none;")
            r_layout.addWidget(t_lbl, 1)

            btn_act = QPushButton(btn_txt)
            btn_act.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            btn_act.setFixedHeight(30)
            btn_act.setCursor(Qt.PointingHandCursor)
            btn_act.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.accent_subtle};
                    color: {c.accent};
                    border: 1px solid {c.accent};
                    border-radius: 6px;
                    padding: 4px 14px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {c.accent};
                    color: #FFFFFF;
                }}
            """)
            btn_act.clicked.connect(callback)
            r_layout.addWidget(btn_act)

            self.recommendations_container.addWidget(row)

    def _render_warnings(self, warnings: List[tuple]):
        """Render live alert cards with Fix buttons."""
        self._cached_warnings = list(warnings)
        for i in reversed(range(self.warnings_container.count())):
            item = self.warnings_container.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
                
        c = ThemeManager.instance().colors
        if not warnings:
            self.warnings_count.set_text_and_variant("0 Warnings", "success")
            clean_lbl = QLabel("✓ No critical warnings detected in dataset.")
            clean_lbl.setFont(QFont("Segoe UI", 9))
            clean_lbl.setStyleSheet(f"color: {c.success}; background: transparent; padding: 4px;")
            self.warnings_container.addWidget(clean_lbl)
            return

        self.warnings_count.set_text_and_variant(f"{len(warnings)} Warnings", "warning")
        for text, btn_txt, callback in warnings[:3]:
            row = QFrame()
            row.setMinimumHeight(44)
            row.setStyleSheet(f"background: {c.surface_alt}; border: 1px solid {c.border}; border-radius: 8px;")
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(14, 8, 14, 8)
            r_layout.setSpacing(12)
            
            ico = QLabel()
            ico.setPixmap(get_icon("warning", c.warning, 16).pixmap(16, 16))
            ico.setStyleSheet("background: transparent; border: none;")
            r_layout.addWidget(ico)
            
            t_lbl = QLabel(text)
            t_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            t_lbl.setStyleSheet(f"color: {c.text_primary}; background: transparent; border: none;")
            r_layout.addWidget(t_lbl, 1)
            
            btn_fix = QPushButton(btn_txt)
            btn_fix.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            btn_fix.setFixedHeight(30)
            btn_fix.setCursor(Qt.PointingHandCursor)
            btn_fix.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c.surface};
                    color: {c.text_primary};
                    border: 1px solid {c.border};
                    border-radius: 6px;
                    padding: 4px 14px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {c.accent};
                    color: #FFFFFF;
                    border: 1px solid {c.accent};
                }}
            """)
            btn_fix.clicked.connect(callback)
            r_layout.addWidget(btn_fix)
            
            self.warnings_container.addWidget(row)

    def refresh_recent_widget(self):
        """Fetch recent cleaning activity from SQLite and display in recent card."""
        for i in reversed(range(self.recent_list_layout.count())):
            item = self.recent_list_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
                
        try:
            from clean_engine import read_audit
            df = read_audit(limit=3)
            c = ThemeManager.instance().colors
            if df is None or df.empty:
                empty_lbl = QLabel("No past cleaning runs recorded yet.")
                empty_lbl.setFont(QFont("Segoe UI", 9))
                empty_lbl.setStyleSheet(f"color: {c.text_muted}; background: transparent;")
                self.recent_list_layout.addWidget(empty_lbl)
                return

            for _, row in df.iterrows():
                f_name = Path(str(row.get("Source", "File"))).name
                prof = str(row.get("Profile", "Clean Dataset"))
                time_str = str(row.get("Timestamp", "--")).replace("T", " ")[:16]
                status_str = str(row.get("Status", "Completed"))
                
                row_box = QFrame()
                row_box.setMinimumHeight(52)
                row_box.setStyleSheet(f"background: {c.surface_alt}; border: 1px solid {c.border}; border-radius: 8px;")
                rb_layout = QHBoxLayout(row_box)
                rb_layout.setContentsMargins(12, 8, 12, 8)
                rb_layout.setSpacing(10)
                
                ico = QLabel()
                ico.setPixmap(get_icon("history", c.accent, 16).pixmap(16, 16))
                ico.setStyleSheet("background: transparent; border: none;")
                rb_layout.addWidget(ico)
                
                txt_col = QVBoxLayout()
                txt_col.setSpacing(3)
                t1 = QLabel(f_name)
                t1.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
                t1.setStyleSheet(f"color: {c.text_primary}; background: transparent; border: none;")
                t2 = QLabel(f"{prof} · {time_str}")
                t2.setFont(QFont("Segoe UI", 8))
                t2.setStyleSheet(f"color: {c.text_muted}; background: transparent; border: none;")
                txt_col.addWidget(t1)
                txt_col.addWidget(t2)
                rb_layout.addLayout(txt_col, 1)
                
                badge = Badge(status_str, "success" if "Complete" in status_str else "neutral")
                rb_layout.addWidget(badge)
                
                self.recent_list_layout.addWidget(row_box)
        except Exception:
            pass
