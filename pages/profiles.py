"""CleanSheet Cleaning Profiles configuration page.

Allows choosing between:
1. 'Clean Dataset' (Standard automated pipeline overview with zero configuration needed)
2. 'Custom Profile' / Saved Profiles (Full interactive builder with switches, imputation strategy, and JSON validation rules)
"""
from typing import Dict, Any, List, Optional
import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QLineEdit, QScrollArea, QFrame, QStackedWidget
)
from components.widgets import Card, PrimaryButton, AnimatedToggle, Badge
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
        self.setFixedHeight(88)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
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


class ProfilesPage(QWidget):
    """Cleaning Profiles configuration page."""
    run_profile_requested = Signal(str, object)
    save_profile_requested = Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.preset_cards: Dict[str, PresetCard] = {}
        self.selected_preset_name = "Clean Dataset"
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)
        
        # Scroll Area for Profile Content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }")
        
        scroll_content = QWidget()
        scroll_content.setObjectName("MainContent")
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(0, 0, 12, 0)
        content_layout.setSpacing(16)
        
        # 1. Presets Grid
        presets_title = QLabel("Select Profile Preset")
        presets_title.setObjectName("CardTitle")
        content_layout.addWidget(presets_title)
        
        self.presets_grid = QGridLayout()
        self.presets_grid.setSpacing(12)
        content_layout.addLayout(self.presets_grid)
        
        # Stacked view for details:
        # Index 0: "Clean Dataset" automated summary view
        # Index 1: "Custom Profile" interactive switches & rules builder
        self.profile_stack = QStackedWidget()
        
        # ------------------- VIEW 0: Automated Clean Dataset View -------------------
        auto_card = Card(elevation=False)
        auto_card.setObjectName("Card")
        a_layout = QVBoxLayout(auto_card)
        a_layout.setContentsMargins(24, 20, 24, 20)
        a_layout.setSpacing(14)
        
        auto_title = QLabel("Automated Pipeline Overview")
        auto_title.setObjectName("CardTitle")
        a_layout.addWidget(auto_title)
        
        auto_desc = QLabel(
            "This preset runs CleanSheet's standard, reliable data cleaning pipeline. "
            "No manual configuration is required; it prepares your dataset with verified data best-practices."
        )
        auto_desc.setObjectName("CardDesc")
        auto_desc.setWordWrap(True)
        a_layout.addWidget(auto_desc)
        
        steps_grid = QGridLayout()
        steps_grid.setSpacing(12)
        c = ThemeManager.instance().colors
        
        standard_steps = [
            ("Standardize Headers", "Converts all column names to clean snake_case", "check"),
            ("Drop Empty Rows", "Removes rows where all cells are empty", "check"),
            ("Trim Text Whitespace", "Removes leading, trailing, and duplicate spaces", "check"),
            ("Deduplicate Records", "Removes exact matching duplicate rows", "check"),
            ("Convert Numeric Fields", "Cleans currency symbols and converts to numbers", "check"),
            ("Detect & Parse Dates", "Standardizes date formats across records", "check"),
            ("Identify Quality Issues", "Flags outliers and missing values in Issue Review", "check"),
            ("Full Change Audit", "Tracks every single modified cell in Compare tab", "check"),
        ]
        
        for idx, (title, desc, icon_name) in enumerate(standard_steps):
            row = idx // 2
            col = idx % 2
            
            step_box = QHBoxLayout()
            step_box.setSpacing(10)
            
            ico = QLabel()
            ico.setFixedSize(24, 24)
            ico.setPixmap(get_icon(icon_name, c.success, 16).pixmap(16, 16))
            step_box.addWidget(ico)
            
            t_col = QVBoxLayout()
            t_col.setSpacing(1)
            t_lbl = QLabel(title)
            t_lbl.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            d_lbl = QLabel(desc)
            d_lbl.setObjectName("CardDesc")
            d_lbl.setStyleSheet("font-size: 11px;")
            t_col.addWidget(t_lbl)
            t_col.addWidget(d_lbl)
            step_box.addLayout(t_col, 1)
            
            steps_grid.addLayout(step_box, row, col)
            
        a_layout.addLayout(steps_grid)
        self.profile_stack.addWidget(auto_card)
        
        # ------------------- VIEW 1: Custom Profile Interactive Builder -------------------
        custom_container = QWidget()
        custom_layout = QVBoxLayout(custom_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(16)
        
        # Builder Group: Structure & Cleaning Switches
        builder_card = Card(elevation=False)
        b_layout = QVBoxLayout(builder_card)
        b_layout.setContentsMargins(20, 18, 20, 18)
        b_layout.setSpacing(14)
        
        bt = QLabel("Custom Cleaning Transformations & Rules")
        bt.setObjectName("CardTitle")
        b_layout.addWidget(bt)
        
        switches_grid = QGridLayout()
        switches_grid.setHorizontalSpacing(24)
        switches_grid.setVerticalSpacing(12)
        
        self.switch_cols = self._add_switch_row(switches_grid, 0, 0, "Standardize column names", "Convert headers to clean snake_case", True)
        self.switch_empty = self._add_switch_row(switches_grid, 1, 0, "Remove fully empty rows", "Drop rows where all values are null", True)
        self.switch_trim = self._add_switch_row(switches_grid, 2, 0, "Trim extra text spaces", "Strip leading, trailing, and duplicate spaces", True)
        self.switch_case = self._add_switch_row(switches_grid, 3, 0, "Normalize text capitalization", "Convert names and titles to Title Case", False)
        
        self.switch_dupes = self._add_switch_row(switches_grid, 0, 1, "Remove duplicate rows", "Keep first occurrence of identical rows", True)
        self.switch_numeric = self._add_switch_row(switches_grid, 1, 1, "Detect & convert numeric", "Parse currency and comma-separated numbers", True)
        self.switch_dates = self._add_switch_row(switches_grid, 2, 1, "Detect & convert dates", "Standardize date strings to YYYY-MM-DD", True)
        
        b_layout.addLayout(switches_grid)
        
        # Combos for Missing Values & Outliers
        combos_layout = QGridLayout()
        combos_layout.setSpacing(14)
        
        lbl_mv = QLabel("Missing values strategy:")
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
        
        lbl_ot = QLabel("Outlier treatment:")
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
        
        # JSON Validation Rules
        rules_card = Card(elevation=False)
        r_layout = QVBoxLayout(rules_card)
        r_layout.setContentsMargins(20, 18, 20, 18)
        r_layout.setSpacing(10)
        
        r_header = QHBoxLayout()
        rt = QLabel("Custom JSON Validation Rules (Optional)")
        rt.setObjectName("CardTitle")
        r_header.addWidget(rt)
        
        self.rule_valid_badge = Badge("Valid JSON", "success")
        r_header.addWidget(self.rule_valid_badge)
        r_header.addStretch(1)
        
        self.example_combo = QComboBox()
        self.example_combo.setPlaceholderText("Insert example rule template...")
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
        self.profile_stack.addWidget(custom_container)
        
        content_layout.addWidget(self.profile_stack)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, 1)
        
        # 3. Sticky Footer Action Bar
        footer = Card(elevation=False)
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(18, 12, 18, 12)
        f_layout.setSpacing(12)
        
        self.name_input = QLineEdit("My Custom Profile")
        self.name_input.setPlaceholderText("Enter profile name to save...")
        self.name_input.setFixedWidth(260)
        f_layout.addWidget(self.name_input)
        
        self.btn_save = QPushButton("Save Reusable Profile")
        self.btn_save.clicked.connect(self._on_save_clicked)
        f_layout.addWidget(self.btn_save)
        
        f_layout.addStretch(1)
        
        self.btn_run = PrimaryButton("Clean Dataset", icon_name="play")
        self.btn_run.clicked.connect(self._on_run_clicked)
        f_layout.addWidget(self.btn_run)
        
        main_layout.addWidget(footer)
        
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
            self.presets_grid.itemAt(i).widget().setParent(None)
        self.preset_cards.clear()
        
        col = 0
        row = 0
        for name in preset_names:
            desc = "Automated data hygiene & anomaly pipeline" if name == "Clean Dataset" else "Custom configuration"
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
            self.profile_stack.setCurrentIndex(0)
            self.name_input.setVisible(False)
            self.btn_save.setVisible(False)
            self.btn_run.setText("Run Clean Dataset")
        else:
            self.profile_stack.setCurrentIndex(1)
            self.name_input.setVisible(True)
            self.btn_save.setVisible(True)
            self.name_input.setText(name if name != "Custom Profile" else "My Custom Profile")
            self.btn_run.setText(f"Run {name}")

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
        except Exception as e:
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

    def _on_run_clicked(self):
        settings = self.get_custom_settings() if self.selected_preset_name != "Clean Dataset" else None
        self.run_profile_requested.emit(self.selected_preset_name, settings)
