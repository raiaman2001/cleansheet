"""CleanSheet Unified Clean Data Page.

Combines Cleaning Workflow execution (live stepper timeline, before/after diff summary)
and Cleaning Profiles (preset cards, custom switches, imputation strategy, and JSON validation rules).
"""
from typing import Callable, Dict, Any, List, Optional
import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QProgressBar, QComboBox, QTextEdit, QLineEdit, QScrollArea, QFrame, QStackedWidget
)
from components.widgets import Card, PrimaryButton, AnimatedToggle, Badge, StatCard
from theme import ThemeManager, ThemeColors
from icons import get_icon


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    """Minimal syntax highlighter for JSON editor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.update_colors()
        ThemeManager.instance().subscribe(lambda _: self.update_colors())

    def update_colors(self):
        c = ThemeManager.instance().colors
        self.key_format = QTextCharFormat()
        self.key_format.setForeground(QColor(c.accent))
        self.key_format.setFontWeight(QFont.DemiBold)
        
        self.str_format = QTextCharFormat()
        self.str_format.setForeground(QColor(c.success))
        
        self.num_format = QTextCharFormat()
        self.num_format.setForeground(QColor(c.warning))
        self.rehighlight()

    def highlightBlock(self, text: str):
        import re
        for m in re.finditer(r'"([^"\\]|\\.)*"\s*:', text):
            self.setFormat(m.start(), m.end() - m.start() - 1, self.key_format)
        for m in re.finditer(r':\s*"([^"\\]|\\.)*"', text):
            self.setFormat(m.start() + 1, m.end() - m.start() - 1, self.str_format)
        for m in re.finditer(r'\b\d+(\.\d+)?\b', text):
            self.setFormat(m.start(), m.end() - m.start(), self.num_format)


class PresetCard(Card):
    """Selectable preset card with radio-like visual selection."""
    clicked = Signal(str)

    def __init__(self, name: str, description: str, icon_name: str, parent=None):
        super().__init__(parent, elevation=False)
        self.setObjectName("Card")
        self.preset_name = name
        self.icon_name = icon_name
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(80)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        self.ico_lbl = QLabel()
        self.ico_lbl.setFixedSize(36, 36)
        self.ico_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.ico_lbl)
        
        txt_box = QVBoxLayout()
        txt_box.setSpacing(2)
        self.t_lbl = QLabel(name)
        self.t_lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.d_lbl = QLabel(description)
        self.d_lbl.setObjectName("CardDesc")
        txt_box.addWidget(self.t_lbl)
        txt_box.addWidget(self.d_lbl)
        layout.addLayout(txt_box, 1)
        
        self.badge_sel = Badge("Active", "info")
        self.badge_sel.setVisible(False)
        layout.addWidget(self.badge_sel)
        
        self._update_appearance()
        ThemeManager.instance().subscribe(lambda _: self._update_appearance())
        
    def _update_appearance(self):
        c = ThemeManager.instance().colors
        self.ico_lbl.setStyleSheet(f"background: {c.surface_alt}; border-radius: 8px; border: none;")
        self.ico_lbl.setPixmap(get_icon(self.icon_name, c.accent if self.selected else c.text_secondary, 20).pixmap(20, 20))
        self.t_lbl.setStyleSheet(f"color: {c.text_primary}; background: transparent; border: none;")
        self.d_lbl.setStyleSheet(f"color: {c.text_muted}; background: transparent; border: none;")
        if self.selected:
            self.setStyleSheet(f"""
                QFrame#Card {{
                    border: 2px solid {c.accent};
                    background: {c.surface};
                    border-radius: 12px;
                }}
            """)
            self.badge_sel.setVisible(True)
        else:
            self.setStyleSheet(f"""
                QFrame#Card {{
                    border: 1px solid {c.border};
                    background: {c.surface};
                    border-radius: 12px;
                }}
                QFrame#Card:hover {{
                    border: 1px solid {c.accent};
                    background: {c.surface_alt};
                }}
            """)
            self.badge_sel.setVisible(False)

    def set_selected(self, selected: bool):
        self.selected = selected
        self._update_appearance()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.preset_name)
        super().mousePressEvent(event)


class StepIndicator(QWidget):
    """Horizontal step timeline: Detect -> Clean -> Validate -> Ready."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        
        self.steps = ["1. Check Issues", "2. Clean Data", "3. Verify Rules", "4. Ready to Save"]
        self.badges = []
        for s in self.steps:
            b = Badge(s, "neutral")
            self.layout.addWidget(b)
            self.badges.append(b)
            
    def set_active_step(self, step_idx: int):
        for i, b in enumerate(self.badges):
            if i < step_idx:
                b.set_text_and_variant(f"✓ {self.steps[i]}", "success")
            elif i == step_idx:
                b.set_text_and_variant(f"▶ {self.steps[i]}", "info")
            else:
                b.set_text_and_variant(self.steps[i], "neutral")


class CleanDataPage(QWidget):
    """Integrated Cleaning Studio page combining Mode Selection, Execution, Stepper, and Custom Builder."""
    run_cleaning_requested = Signal(str, object, bool)  # (profile_name, custom_settings, clean_all_sheets)
    save_profile_requested = Signal(str, object)
    open_fuzzy_merge_requested = Signal()
    open_masking_requested = Signal()
    open_outlier_requested = Signal()
    open_column_transform_requested = Signal()
    open_combine_requested = Signal()
    open_standardizer_requested = Signal()
    open_sql_connector_requested = Signal()
    open_deep_profile_requested = Signal()
    open_lineage_requested = Signal()
    open_big_data_requested = Signal()
    export_recipe_requested = Signal()
    import_recipe_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preset_cards: Dict[str, PresetCard] = {}
        self.selected_preset_name = "Clean Dataset"
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        
        scroll_content = QWidget()
        scroll_content.setObjectName("MainContent")
        main_layout = QVBoxLayout(scroll_content)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # 1. Preset Selection Grid
        p_title = QLabel("Choose How to Clean Your Data")
        p_title.setObjectName("CardTitle")
        main_layout.addWidget(p_title)
        
        self.presets_grid = QGridLayout()
        self.presets_grid.setSpacing(12)
        main_layout.addLayout(self.presets_grid)
        
        # 2. Action Execution Area (Directly below mode selection)
        act_card = Card(elevation=True)
        act_layout = QVBoxLayout(act_card)
        act_layout.setContentsMargins(22, 18, 22, 18)
        act_layout.setSpacing(14)
        
        # Multi-Sheet Selection Scope Bar (Only visible when multi-sheet workbook is loaded)
        self.scope_container = QWidget()
        scope_layout = QHBoxLayout(self.scope_container)
        scope_layout.setContentsMargins(0, 0, 0, 6)
        scope_layout.setSpacing(12)
        
        scope_title = QLabel("Cleaning Scope:")
        scope_title.setStyleSheet("font-weight: 700; font-size: 13px; color: #64748B;")
        scope_layout.addWidget(scope_title)
        
        # Pill buttons for clear active / inactive visual feedback
        self.btn_scope_active = QPushButton("Active Sheet Only")
        self.btn_scope_active.setCheckable(True)
        self.btn_scope_active.setChecked(True)
        self.btn_scope_active.setCursor(Qt.PointingHandCursor)
        self.btn_scope_active.setFixedHeight(32)
        
        self.btn_scope_all = QPushButton("⚡ All Sheets in Workbook")
        self.btn_scope_all.setCheckable(True)
        self.btn_scope_all.setChecked(False)
        self.btn_scope_all.setCursor(Qt.PointingHandCursor)
        self.btn_scope_all.setFixedHeight(32)

        from PySide6.QtWidgets import QButtonGroup
        self.scope_btn_group = QButtonGroup(self)
        self.scope_btn_group.setExclusive(True)
        self.scope_btn_group.addButton(self.btn_scope_active)
        self.scope_btn_group.addButton(self.btn_scope_all)
        
        self.btn_scope_active.clicked.connect(self._update_scope_pill_styles)
        self.btn_scope_all.clicked.connect(self._update_scope_pill_styles)
        self._update_scope_pill_styles()

        scope_layout.addWidget(self.btn_scope_active)
        scope_layout.addWidget(self.btn_scope_all)
        scope_layout.addStretch(1)
        
        self.scope_container.setVisible(False)
        act_layout.addWidget(self.scope_container)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)
        
        self.btn_clean = PrimaryButton("Start Cleaning", icon_name="play")
        self.btn_clean.setFixedHeight(44)
        self.btn_clean.setMinimumWidth(220)
        self.btn_clean.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.btn_clean.clicked.connect(self._on_run_clicked)
        btn_row.addWidget(self.btn_clean)
        
        self.status_lbl = QLabel("Ready · Click button to clean your dataset.")
        self.status_lbl.setObjectName("CardDesc")
        btn_row.addWidget(self.status_lbl, 1)

        # Smart Studio Tools Button
        self.btn_fuzzy = QPushButton("Fuzzy Merge Studio")
        self.btn_fuzzy.setIcon(get_icon("magic", "#4338CA", 14))
        self.btn_fuzzy.setStyleSheet("""
            QPushButton {
                background: #EEF2FF;
                color: #4338CA;
                border: 1px solid #C7D2FE;
                padding: 8px 14px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover { background: #E0E7FF; }
        """)
        self.btn_fuzzy.setToolTip("Find typo variations & merge clusters (e.g. Infosys Ltd vs Infosys Limited)")
        self.btn_fuzzy.clicked.connect(self.open_fuzzy_merge_requested.emit)
        btn_row.addWidget(self.btn_fuzzy)

        self.btn_mask = QPushButton("Data Masking (PII)")
        self.btn_mask.setIcon(get_icon("shield", "#047857", 14))
        self.btn_mask.setStyleSheet("""
            QPushButton {
                background: #ECFDF5;
                color: #047857;
                border: 1px solid #A7F3D0;
                padding: 8px 14px;
                border-radius: 6px;
                font-weight: 600;
            }
            QPushButton:hover { background: #D1FAE5; }
        """)
        self.btn_mask.setToolTip("Mask or anonymize sensitive columns (Email, Phone, IDs)")
        self.btn_mask.clicked.connect(self.open_masking_requested.emit)
        btn_row.addWidget(self.btn_mask)

        # Advanced Tool Buttons
        self.btn_outliers = QPushButton("Outlier Studio")
        self.btn_outliers.setIcon(get_icon("warning", "#B45309", 14))
        self.btn_outliers.setStyleSheet("""
            QPushButton { background: #FEF3C7; color: #B45309; border: 1px solid #FDE68A; padding: 8px 12px; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background: #FDE68A; }
        """)
        self.btn_outliers.setToolTip("Detect & remediate statistical outliers and extreme anomalies (IQR/Z-Score)")
        self.btn_outliers.clicked.connect(self.open_outlier_requested.emit)
        btn_row.addWidget(self.btn_outliers)

        self.btn_cols = QPushButton("Split / Merge")
        self.btn_cols.setIcon(get_icon("columns", "#0284C7", 14))
        self.btn_cols.setStyleSheet("""
            QPushButton { background: #E0F2FE; color: #0284C7; border: 1px solid #BAE6FD; padding: 8px 12px; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background: #BAE6FD; }
        """)
        self.btn_cols.setToolTip("Split delimited columns or concatenate multiple columns")
        self.btn_cols.clicked.connect(self.open_column_transform_requested.emit)
        btn_row.addWidget(self.btn_cols)

        self.btn_combine = QPushButton("Append / Join")
        self.btn_combine.setIcon(get_icon("table", "#7C3AED", 14))
        self.btn_combine.setStyleSheet("""
            QPushButton { background: #EDE9FE; color: #7C3AED; border: 1px solid #DDD6FE; padding: 8px 12px; border-radius: 6px; font-weight: 600; }
            QPushButton:hover { background: #DDD6FE; }
        """)
        self.btn_combine.setToolTip("Vertically stack multiple files or merge/VLOOKUP two tables on key column")
        self.btn_combine.clicked.connect(self.open_combine_requested.emit)
        btn_row.addWidget(self.btn_combine)

        # Recipe action tools
        self.btn_import_rec = QPushButton("Import Recipe")
        self.btn_import_rec.setIcon(get_icon("folder-open", "#475569", 14))
        self.btn_import_rec.setToolTip("Load a pre-configured .recipe file and apply to dataset")
        self.btn_import_rec.clicked.connect(self.import_recipe_requested.emit)
        btn_row.addWidget(self.btn_import_rec)

        self.btn_export_rec = QPushButton("Export Recipe")
        self.btn_export_rec.setIcon(get_icon("download", "#475569", 14))
        self.btn_export_rec.setToolTip("Save all active cleaning rules into a shareable .recipe file")
        self.btn_export_rec.clicked.connect(self.export_recipe_requested.emit)
        btn_row.addWidget(self.btn_export_rec)
        
        act_layout.addLayout(btn_row)

        # Enterprise Tools Row (Standardizer, SQL Connector, Deep Diagnostics, Lineage)
        ent_row = QHBoxLayout()
        ent_row.setSpacing(10)

        self.btn_standardize = QPushButton("Phone & Date Standardizer")
        self.btn_standardize.setIcon(get_icon("magic", "#0D9488", 14))
        self.btn_standardize.setStyleSheet("""
            QPushButton { background: #CCFBF1; color: #0D9488; border: 1px solid #99F6E4; padding: 7px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }
            QPushButton:hover { background: #99F6E4; }
        """)
        self.btn_standardize.setToolTip("Universal phone formatter (E.164), smart mixed date heuristic parsing, pincode extractor & case standardizer")
        self.btn_standardize.clicked.connect(self.open_standardizer_requested.emit)
        ent_row.addWidget(self.btn_standardize)

        self.btn_deep_diag = QPushButton("Deep Diagnostics")
        self.btn_deep_diag.setIcon(get_icon("activity", "#D97706", 14))
        self.btn_deep_diag.setStyleSheet("""
            QPushButton { background: #FEF3C7; color: #D97706; border: 1px solid #FDE68A; padding: 7px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }
            QPushButton:hover { background: #FDE68A; }
        """)
        self.btn_deep_diag.setToolTip("In-depth statistical profiling, cardinality analysis, and automatic collinear/duplicate column detection")
        self.btn_deep_diag.clicked.connect(self.open_deep_profile_requested.emit)
        ent_row.addWidget(self.btn_deep_diag)

        self.btn_sql = QPushButton("SQL DB Connect")
        self.btn_sql.setIcon(get_icon("database", "#2563EB", 14))
        self.btn_sql.setStyleSheet("""
            QPushButton { background: #DBEAFE; color: #2563EB; border: 1px solid #BFDBFE; padding: 7px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }
            QPushButton:hover { background: #BFDBFE; }
        """)
        self.btn_sql.setToolTip("Import directly from SQLite, PostgreSQL, MySQL via custom SQL query or export cleaned table")
        self.btn_sql.clicked.connect(self.open_sql_connector_requested.emit)
        ent_row.addWidget(self.btn_sql)

        self.btn_lineage = QPushButton("Audit Lineage")
        self.btn_lineage.setIcon(get_icon("clock", "#4B5563", 14))
        self.btn_lineage.setStyleSheet("""
            QPushButton { background: #F3F4F6; color: #374151; border: 1px solid #E5E7EB; padding: 7px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }
            QPushButton:hover { background: #E5E7EB; }
        """)
        self.btn_lineage.setToolTip("View full step-by-step audit lineage of all transformations with cryptographic verification")
        self.btn_lineage.clicked.connect(self.open_lineage_requested.emit)
        ent_row.addWidget(self.btn_lineage)

        self.btn_big_data = QPushButton("Big Data Stream")
        self.btn_big_data.setIcon(get_icon("zap", "#9333EA", 14))
        self.btn_big_data.setStyleSheet("""
            QPushButton { background: #F3E8FF; color: #9333EA; border: 1px solid #E9D5FF; padding: 7px 12px; border-radius: 6px; font-weight: 600; font-size: 11px; }
            QPushButton:hover { background: #E9D5FF; }
        """)
        self.btn_big_data.setToolTip("Out-of-core streaming CSV cleaning for huge 500MB to 10GB+ files without memory crashes")
        self.btn_big_data.clicked.connect(self.open_big_data_requested.emit)
        ent_row.addWidget(self.btn_big_data)

        ent_row.addStretch(1)
        act_layout.addLayout(ent_row)
        
        # Stepper & Progress
        self.stepper = StepIndicator()
        act_layout.addWidget(self.stepper)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        act_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(act_card)
        
        # 3. Custom Configuration Builder (Expands when Custom Profile is active)
        self.custom_container = QWidget()
        self.custom_container.setVisible(False)
        custom_layout = QVBoxLayout(self.custom_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(14)
        
        # Switches Card
        builder_card = Card(elevation=False)
        b_layout = QVBoxLayout(builder_card)
        b_layout.setContentsMargins(20, 18, 20, 18)
        b_layout.setSpacing(14)
        
        bt = QLabel("Custom Cleaning Rules & Options")
        bt.setObjectName("CardTitle")
        b_layout.addWidget(bt)
        
        switches_grid = QGridLayout()
        switches_grid.setHorizontalSpacing(24)
        switches_grid.setVerticalSpacing(12)
        
        self.switch_cols = self._add_switch_row(switches_grid, 0, 0, "Clean up column names", "Convert messy headers to neat, readable names", True)
        self.switch_empty = self._add_switch_row(switches_grid, 1, 0, "Remove completely blank rows", "Drop rows where all values are empty", True)
        self.switch_trim = self._add_switch_row(switches_grid, 2, 0, "Fix extra spaces", "Remove accidental spaces at the start and end of text", True)
        self.switch_case = self._add_switch_row(switches_grid, 3, 0, "Capitalize words nicely", "Make names and titles look neat (Title Case)", False)
        
        self.switch_dupes = self._add_switch_row(switches_grid, 0, 1, "Remove duplicate rows", "Keep only the first copy of repeated rows", True)
        self.switch_numeric = self._add_switch_row(switches_grid, 1, 1, "Format numbers properly", "Fix currency symbols and comma-separated numbers", True)
        self.switch_dates = self._add_switch_row(switches_grid, 2, 1, "Format dates neatly", "Convert different date styles to standard YYYY-MM-DD", True)
        
        b_layout.addLayout(switches_grid)
        
        # Combos for Missing Values & Outliers
        combos_layout = QGridLayout()
        combos_layout.setSpacing(14)
        
        lbl_mv = QLabel("How to handle missing values:")
        lbl_mv.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.combo_missing = QComboBox()
        self.combo_missing.addItems([
            "Leave missing values unchanged",
            "Fill numeric median / text mode",
            "Remove rows with missing values",
            "KNN imputation (numeric columns)",
            "Iterative imputation (numeric columns)"
        ])
        combos_layout.addWidget(lbl_mv, 0, 0)
        combos_layout.addWidget(self.combo_missing, 0, 1)
        
        lbl_ot = QLabel("How to handle unusual values (outliers):")
        lbl_ot.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        self.combo_outliers = QComboBox()
        self.combo_outliers.addItems([
            "Flag only",
            "Cap using IQR bounds",
            "Remove outlier rows"
        ])
        combos_layout.addWidget(lbl_ot, 1, 0)
        combos_layout.addWidget(self.combo_outliers, 1, 1)
        
        b_layout.addLayout(combos_layout)
        custom_layout.addWidget(builder_card)
        
        # JSON Validation Rules Card
        rules_card = Card(elevation=False)
        r_layout = QVBoxLayout(rules_card)
        r_layout.setContentsMargins(20, 18, 20, 18)
        r_layout.setSpacing(10)
        
        r_header = QHBoxLayout()
        rt = QLabel("Custom Verification Rules (Optional)")
        rt.setObjectName("CardTitle")
        r_header.addWidget(rt)
        
        self.rule_valid_badge = Badge("Valid Rules", "success")
        r_header.addWidget(self.rule_valid_badge)
        r_header.addStretch(1)
        
        self.example_combo = QComboBox()
        self.example_combo.setPlaceholderText("Insert an example rule...")
        self.example_combo.addItems([
            "Insert Example Template",
            "Email Validation",
            "Age Range (0 - 120)",
            "Allowed Status Values",
            "Custom Regex Pattern"
        ])
        self.example_combo.currentIndexChanged.connect(self._insert_example_rule)
        r_header.addWidget(self.example_combo)
        r_layout.addLayout(r_header)
        
        self.rules_editor = QTextEdit()
        self.rules_editor.setFont(QFont("Consolas", 10))
        self.rules_editor.setPlaceholderText('[\n  {"column": "email", "rule": "email"},\n  {"column": "age", "rule": "range", "min": 0, "max": 120}\n]')
        self.rules_editor.setFixedHeight(110)
        self.rules_editor.textChanged.connect(self._validate_json_syntax)
        self.highlighter = JsonSyntaxHighlighter(self.rules_editor.document())
        r_layout.addWidget(self.rules_editor)
        
        custom_layout.addWidget(rules_card)
        
        save_box = Card(elevation=False)
        sb_layout = QHBoxLayout(save_box)
        sb_layout.setContentsMargins(16, 12, 16, 12)
        sb_layout.setSpacing(12)
        
        self.name_input = QLineEdit("My Custom Profile")
        self.name_input.setPlaceholderText("Name your custom cleaning setup...")
        self.name_input.setFixedWidth(260)
        sb_layout.addWidget(self.name_input)
        
        self.btn_save = QPushButton("Save This Cleaning Setup")
        self.btn_save.clicked.connect(self._on_save_clicked)
        sb_layout.addWidget(self.btn_save)
        sb_layout.addStretch(1)
        
        custom_layout.addWidget(save_box)
        main_layout.addWidget(self.custom_container)
        
        # 4. Permanent Workflow Execution Summary Card
        self.diff_card = Card(elevation=True)
        self.diff_card.setVisible(True)
        diff_layout = QVBoxLayout(self.diff_card)
        diff_layout.setContentsMargins(20, 16, 20, 16)
        diff_layout.setSpacing(12)
        
        dt = QLabel("Cleaning Summary")
        dt.setObjectName("CardTitle")
        diff_layout.addWidget(dt)
        
        summary_grid = QGridLayout()
        self.sum_rows = StatCard("Rows Checked", "--", "Before vs After", "rows")
        self.sum_cells = StatCard("Values Fixed", "--", "Cells cleaned", "check")
        self.sum_issues = StatCard("Things to Review", "--", "Found in Issue Review", "warning")
        
        summary_grid.addWidget(self.sum_rows, 0, 0)
        summary_grid.addWidget(self.sum_cells, 0, 1)
        summary_grid.addWidget(self.sum_issues, 0, 2)
        diff_layout.addLayout(summary_grid)
        
        main_layout.addWidget(self.diff_card)
        main_layout.addStretch(1)
        
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll)
        
        self.refresh_presets(["Clean Dataset", "Custom Profile"])

    def _add_switch_row(self, grid: QGridLayout, row: int, col: int, title: str, desc: str, default: bool) -> AnimatedToggle:
        container = QWidget()
        c_layout = QHBoxLayout(container)
        c_layout.setContentsMargins(0, 4, 0, 4)
        c_layout.setSpacing(12)
        
        switch = AnimatedToggle(checked=default)
        c_layout.addWidget(switch)
        
        txt_box = QVBoxLayout()
        txt_box.setSpacing(1)
        t_lbl = QLabel(title)
        t_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        d_lbl = QLabel(desc)
        d_lbl.setObjectName("CardDesc")
        txt_box.addWidget(t_lbl)
        txt_box.addWidget(d_lbl)
        c_layout.addLayout(txt_box, 1)
        
        grid.addWidget(container, row, col)
        return switch

    def refresh_presets(self, preset_names: List[str]):
        # Clear existing
        for i in reversed(range(self.presets_grid.count())): 
            item = self.presets_grid.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)
        self.preset_cards.clear()
        
        col = 0
        row = 0
        for name in preset_names:
            desc = "Automatically fixes headers, removes blanks, and tidies spacing" if name == "Clean Dataset" else "Customize rules, formatting, and values yourself"
            card = PresetCard(name, desc, "sparkles" if name == "Clean Dataset" else "sliders")
            card.clicked.connect(self._on_preset_selected)
            self.presets_grid.addWidget(card, row, col)
            self.preset_cards[name] = card
            col += 1
            if col > 2:
                col = 0
                row += 1
                
        self._on_preset_selected(self.selected_preset_name)

    def _on_preset_selected(self, name: str):
        self.selected_preset_name = name
        for p_name, card in self.preset_cards.items():
            card.set_selected(p_name == name)
            
        if name == "Clean Dataset":
            self.custom_container.setVisible(False)
            self.btn_clean.setText("Start Cleaning")
            self.status_lbl.setText("Ready · Click 'Start Cleaning' to automatically clean your data.")
        else:
            self.custom_container.setVisible(True)
            self.name_input.setText(name if name != "Custom Profile" else "My Custom Profile")
            self.btn_clean.setText(f"Run {name}")
            self.status_lbl.setText(f"Choose your custom rules below, then click 'Run {name}'.")

    def _validate_json_syntax(self):
        txt = self.rules_editor.toPlainText().strip()
        if not txt:
            self.rule_valid_badge.set_text_and_variant("Empty (Optional)", "neutral")
            return
        try:
            val = json.loads(txt)
            if isinstance(val, list):
                self.rule_valid_badge.set_text_and_variant(f"✓ {len(val)} Rule(s) Valid", "success")
            else:
                self.rule_valid_badge.set_text_and_variant("Must be JSON array [...]", "danger")
        except Exception:
            self.rule_valid_badge.set_text_and_variant("Invalid JSON Syntax", "danger")

    def _insert_example_rule(self, index: int):
        templates = {
            1: '{"column": "email", "rule": "email"}',
            2: '{"column": "age", "rule": "range", "min": 0, "max": 120}',
            3: '{"column": "status", "rule": "allowed_values", "values": ["Active", "Inactive"]}',
            4: '{"column": "phone", "rule": "regex", "pattern": "^[0-9]{3}-[0-9]{3}-[0-9]{4}$"}',
        }
        snippet = templates.get(index)
        if not snippet:
            return
        current = self.rules_editor.toPlainText().strip()
        if not current:
            self.rules_editor.setPlainText(f"[\n  {snippet}\n]")
        else:
            try:
                parsed = json.loads(current)
                if isinstance(parsed, list):
                    parsed.append(json.loads(snippet))
                    self.rules_editor.setPlainText(json.dumps(parsed, indent=2))
            except Exception:
                self.rules_editor.append(f",\n{snippet}")
        self.example_combo.setCurrentIndex(0)

    def get_custom_settings(self) -> Dict[str, Any]:
        raw_rules = self.rules_editor.toPlainText().strip()
        rules = []
        if raw_rules:
            try:
                rules = json.loads(raw_rules)
            except Exception:
                pass
                
        return {
            "normalize_columns": self.switch_cols.isChecked(),
            "remove_empty": self.switch_empty.isChecked(),
            "trim_text": self.switch_trim.isChecked(),
            "normalize_case": self.switch_case.isChecked(),
            "remove_duplicates": self.switch_dupes.isChecked(),
            "convert_numeric": self.switch_numeric.isChecked(),
            "convert_dates": self.switch_dates.isChecked(),
            "fill_missing": self.combo_missing.currentIndex() != 0,
            "missing_strategy": self.combo_missing.currentText(),
            "outlier_strategy": self.combo_outliers.currentText(),
            "validation_rules": rules if isinstance(rules, list) else [],
            "name": self.name_input.text().strip() or "Custom Profile",
        }

    def _on_save_clicked(self):
        name = self.name_input.text().strip() or "My Custom Profile"
        settings = self.get_custom_settings()
        self.save_profile_requested.emit(name, settings)

    def _update_scope_pill_styles(self):
        """Update pill styles so the selected scope is highlighted boldly."""
        if self.btn_scope_active.isChecked():
            self.btn_scope_active.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: #FFFFFF;
                    border: 1px solid #1D4ED8;
                    border-radius: 6px;
                    font-weight: 700;
                    padding: 4px 14px;
                    font-size: 12px;
                }
            """)
            self.btn_scope_all.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #64748B;
                    border: 1px solid #CBD5E1;
                    border-radius: 6px;
                    font-weight: 500;
                    padding: 4px 14px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #F1F5F9;
                    color: #1E293B;
                }
            """)
        else:
            self.btn_scope_active.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #64748B;
                    border: 1px solid #CBD5E1;
                    border-radius: 6px;
                    font-weight: 500;
                    padding: 4px 14px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #F1F5F9;
                    color: #1E293B;
                }
            """)
            self.btn_scope_all.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: #FFFFFF;
                    border: 1px solid #1D4ED8;
                    border-radius: 6px;
                    font-weight: 700;
                    padding: 4px 14px;
                    font-size: 12px;
                }
            """)

    def set_available_sheets(self, sheets: list, current_sheet: str = ""):
        """Configure scope bar depending on whether the workbook has multiple sheets."""
        if sheets and len(sheets) > 1:
            self.scope_container.setVisible(True)
            active_txt = f"✓ Active Sheet (\"{current_sheet or sheets[0]}\")"
            all_txt = f"⚡ All Sheets in Workbook ({len(sheets)} Sheets)"
            self.btn_scope_active.setText(active_txt)
            self.btn_scope_all.setText(all_txt)
        else:
            self.scope_container.setVisible(False)
            self.btn_scope_active.setChecked(True)
        self._update_scope_pill_styles()

    def _on_run_clicked(self):
        settings = self.get_custom_settings() if self.selected_preset_name != "Clean Dataset" else None
        clean_all = self.btn_scope_all.isChecked() and self.scope_container.isVisible()
        self.run_cleaning_requested.emit(self.selected_preset_name, settings, clean_all)

    def set_running(self, running: bool, profile_name: str = "Clean Dataset"):
        self.progress_bar.setVisible(running)
        if running:
            self.stepper.set_active_step(1)
            self.status_lbl.setText(f"Executing {profile_name} on dataset…")
            self.btn_clean.setEnabled(False)
        else:
            self.btn_clean.setEnabled(True)

    def show_completion_summary(self, original_df, cleaned_df, issues_df, logs_df):
        self.stepper.set_active_step(3)
        self.diff_card.setVisible(True)
        rows_str = f"{len(original_df):,} → {len(cleaned_df):,}"
        self.sum_rows.set_value(f"{len(cleaned_df):,}", hint=rows_str)
        
        # Total cells altered
        total_altered = 0
        if logs_df is not None and not logs_df.empty and "Count" in logs_df.columns:
            total_altered = int(logs_df["Count"].sum())
        self.sum_cells.set_value(f"{total_altered:,}")
        
        # Issues flagged
        issue_count = len(issues_df) if issues_df is not None else 0
        self.sum_issues.set_value(f"{issue_count:,}")
        
        self.status_lbl.setText("Dataset cleaned successfully! Inspect findings in Compare or Issue Review.")
