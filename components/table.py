"""Reusable Modern Table and JSON Syntax Highlighter components."""
import re
import json
from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import (
    QColor, QTextCharFormat, QFont, QSyntaxHighlighter, QAction, QKeySequence, QGuiApplication
)
from PySide6.QtWidgets import (
    QTableWidget, QHeaderView, QAbstractItemView, QMenu, QApplication
)
from theme import ThemeManager


class ModernTable(QTableWidget):
    """Refined desktop data table with context menus, sticky headers, and row hover."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(40)
        self.setShowGrid(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)
        
        if item:
            copy_cell = menu.addAction("Copy Cell Value")
            copy_cell.triggered.connect(lambda: QGuiApplication.clipboard().setText(item.text()))
            
            col_idx = item.column()
            col_name = self.horizontalHeaderItem(col_idx).text() if self.horizontalHeaderItem(col_idx) else f"Column {col_idx}"
            copy_col = menu.addAction(f"Copy '{col_name}' Column")
            copy_col.triggered.connect(lambda: self._copy_column_values(col_idx))
            
            menu.addSeparator()
            hide_col = menu.addAction(f"Hide Column '{col_name}'")
            hide_col.triggered.connect(lambda: self.setColumnHidden(col_idx, True))
            
            unhide_all = menu.addAction("Unhide All Columns")
            unhide_all.triggered.connect(self._unhide_all_columns)
        else:
            unhide_all = menu.addAction("Unhide All Columns")
            unhide_all.triggered.connect(self._unhide_all_columns)
            
        menu.exec(self.viewport().mapToGlobal(pos))

    def _copy_column_values(self, col_idx: int):
        values = []
        for r in range(self.rowCount()):
            it = self.item(r, col_idx)
            values.append(it.text() if it else "")
        QGuiApplication.clipboard().setText("\n".join(values))

    def _unhide_all_columns(self):
        for c in range(self.columnCount()):
            self.setColumnHidden(c, False)


class JsonSyntaxHighlighter(QSyntaxHighlighter):
    """Fast JSON syntax highlighter for validation rules editor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        self._init_formats()
        ThemeManager.instance().subscribe(lambda _: self._init_formats())

    def _init_formats(self):
        c = ThemeManager.instance().colors
        self.rules = []
        
        # Keys ("key":)
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor(c.accent))
        key_fmt.setFontWeight(QFont.DemiBold)
        self.rules.append((re.compile(r'"(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)'), key_fmt))
        
        # Strings ("value")
        str_fmt = QTextCharFormat()
        str_fmt.setForeground(QColor(c.success))
        self.rules.append((re.compile(r':\s*("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*")'), str_fmt))
        
        # Numbers
        num_fmt = QTextCharFormat()
        num_fmt.setForeground(QColor(c.warning))
        self.rules.append((re.compile(r'\b-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?\b'), num_fmt))
        
        # Booleans / null
        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(c.danger))
        kw_fmt.setFontWeight(QFont.DemiBold)
        self.rules.append((re.compile(r'\b(true|false|null)\b'), kw_fmt))
        
        self.rehighlight()

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
