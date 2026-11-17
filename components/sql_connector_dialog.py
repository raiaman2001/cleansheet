"""SQL Database Ingestion and Export Dialog for CleanSheet.
Supports SQLite (.db / .sqlite files) and relational databases (PostgreSQL, MySQL, SQLite URI)
via SQLAlchemy or standard library sqlite3.
"""
import os
import sqlite3
import pandas as pd
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QWidget, QFileDialog, QMessageBox, QSpinBox, QProgressBar
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from theme import ThemeManager
from enterprise_engine import execute_sql_query, export_to_sql_table


class SQLConnectorDialog(QDialog):
    """Dialog to import data via SQL query or export cleaned data back to a database table."""
    data_imported = Signal(object, str)  # (DataFrame, source_name)

    def __init__(self, current_df: pd.DataFrame = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Enterprise Data Connectors — SQL & REST API")
        self.resize(840, 600)
        self.current_df = current_df
        self.preview_df = None
        self._setup_ui()

    def _setup_ui(self):
        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background: {c.bg}; }}
            QLabel {{ color: {c.text_primary}; font-family: 'Segoe UI'; font-size: 13px; }}
            QLineEdit, QTextEdit, QComboBox, QSpinBox {{
                background: {c.surface};
                color: {c.text_primary};
                border: 1px solid {c.border};
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid {c.accent};
            }}
            QTabWidget::pane {{
                border: 1px solid {c.border};
                background: {c.surface};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {c.surface_alt};
                color: {c.text_secondary};
                padding: 8px 18px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
            }}
            QTabBar::tab:selected {{
                background: {c.surface};
                color: {c.accent};
                border: 1px solid {c.border};
                border-bottom: none;
            }}
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
                padding: 5px;
                font-weight: 600;
                border: 1px solid {c.border};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Title Header
        header = QLabel("Enterprise Data Connectors (SQL, REST API & JSON)")
        header.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header.setStyleSheet(f"color: {c.accent};")
        layout.addWidget(header)

        sub_desc = QLabel("Connect directly to SQL databases, live REST APIs, or nested JSON files to query, flatten, or persist data.")
        sub_desc.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        layout.addWidget(sub_desc)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_import_tab(), "📥 SQL Query Import")
        self.tabs.addTab(self._build_api_tab(), "🌐 REST API & JSON Flatten")
        self.tabs.addTab(self._build_export_tab(), "📤 Export to Database Table")
        layout.addWidget(self.tabs, 1)

        # Bottom Close Button
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet(f"background: {c.surface_alt}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; padding: 6px 16px;")
        btn_close.clicked.connect(self.reject)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _build_import_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # DB Type Selector
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Database Source:"))
        self.combo_db_type = QComboBox()
        self.combo_db_type.addItems(["SQLite File (.db, .sqlite)", "PostgreSQL / MySQL / Custom URI"])
        self.combo_db_type.currentIndexChanged.connect(self._on_db_type_changed)
        type_row.addWidget(self.combo_db_type, 1)
        layout.addLayout(type_row)

        # Connection String / File path row
        self.conn_row = QHBoxLayout()
        self.lbl_conn = QLabel("SQLite DB File:")
        self.txt_conn = QLineEdit()
        self.txt_conn.setPlaceholderText("Select or enter path to .db / .sqlite file...")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.setStyleSheet("padding: 6px 14px; font-weight: 600;")
        self.btn_browse.clicked.connect(self._browse_sqlite_file)

        self.conn_row.addWidget(self.lbl_conn)
        self.conn_row.addWidget(self.txt_conn, 1)
        self.conn_row.addWidget(self.btn_browse)
        layout.addLayout(self.conn_row)

        # SQL Query Editor
        layout.addWidget(QLabel("SQL Query:"))
        self.txt_query = QTextEdit()
        self.txt_query.setPlaceholderText("SELECT * FROM your_table LIMIT 1000;")
        self.txt_query.setFixedHeight(90)
        self.txt_query.setFont(QFont("Consolas", 11))
        layout.addWidget(self.txt_query)

        # Action row
        act_row = QHBoxLayout()
        self.btn_preview = QPushButton("Execute & Preview")
        self.btn_preview.setStyleSheet("background: #0284C7; color: white; border-radius: 6px; font-weight: 600; padding: 8px 16px;")
        self.btn_preview.clicked.connect(self._run_import_preview)
        act_row.addWidget(self.btn_preview)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #64748B; font-size: 12px;")
        act_row.addWidget(self.lbl_status, 1)

        self.btn_load_into_app = QPushButton("✓ Load Into CleanSheet")
        self.btn_load_into_app.setEnabled(False)
        self.btn_load_into_app.setStyleSheet("background: #10B981; color: white; border-radius: 6px; font-weight: bold; padding: 8px 18px;")
        self.btn_load_into_app.clicked.connect(self._load_data_into_app)
        act_row.addWidget(self.btn_load_into_app)
        layout.addLayout(act_row)

        # Preview Table
        self.tbl_preview = QTableWidget()
        layout.addWidget(self.tbl_preview, 1)

        return tab

    def _build_api_tab(self) -> QWidget:
        from enterprise_engine import ingest_json_data
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Source Type Selector
        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Data Source:"))
        self.combo_api_src = QComboBox()
        self.combo_api_src.addItems(["REST API Endpoint (HTTP/HTTPS GET)", "Local JSON File (.json)", "Paste Raw JSON Text"])
        src_row.addWidget(self.combo_api_src, 1)
        layout.addLayout(src_row)

        # URL / File path input
        self.api_input_row = QHBoxLayout()
        self.lbl_api_input = QLabel("API URL / Path:")
        self.txt_api_input = QLineEdit()
        self.txt_api_input.setPlaceholderText("https://api.example.com/data or C:/path/to/data.json")
        self.btn_api_browse = QPushButton("Browse JSON...")
        self.btn_api_browse.clicked.connect(self._browse_json_file)
        self.api_input_row.addWidget(self.lbl_api_input)
        self.api_input_row.addWidget(self.txt_api_input, 1)
        self.api_input_row.addWidget(self.btn_api_browse)
        layout.addLayout(self.api_input_row)

        # Record path (optional for nested structures)
        param_row = QHBoxLayout()
        param_row.addWidget(QLabel("Nested Record Key (Optional):"))
        self.txt_record_path = QLineEdit()
        self.txt_record_path.setPlaceholderText("e.g. data or items or results (leave empty for auto-detect)")
        param_row.addWidget(self.txt_record_path, 1)

        param_row.addWidget(QLabel("Bearer Token / Key (Optional):"))
        self.txt_auth_token = QLineEdit()
        self.txt_auth_token.setPlaceholderText("Optional auth token")
        param_row.addWidget(self.txt_auth_token, 1)
        layout.addLayout(param_row)

        # Action Buttons
        act_row = QHBoxLayout()
        self.btn_fetch_api = QPushButton("Fetch & Flatten JSON")
        self.btn_fetch_api.setStyleSheet("background: #0D9488; color: white; border-radius: 6px; font-weight: 600; padding: 8px 16px;")
        self.btn_fetch_api.clicked.connect(self._run_api_fetch)
        act_row.addWidget(self.btn_fetch_api)

        self.lbl_api_status = QLabel("")
        self.lbl_api_status.setStyleSheet("color: #64748B; font-size: 12px;")
        act_row.addWidget(self.lbl_api_status, 1)

        self.btn_load_api_app = QPushButton("✓ Load Into CleanSheet")
        self.btn_load_api_app.setEnabled(False)
        self.btn_load_api_app.setStyleSheet("background: #10B981; color: white; border-radius: 6px; font-weight: bold; padding: 8px 18px;")
        self.btn_load_api_app.clicked.connect(self._load_api_data_into_app)
        act_row.addWidget(self.btn_load_api_app)
        layout.addLayout(act_row)

        # Preview Table
        self.tbl_api_preview = QTableWidget()
        layout.addWidget(self.tbl_api_preview, 1)

        return tab

    def _browse_json_file(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select JSON File", "", "JSON Files (*.json);;All Files (*.*)")
        if fpath:
            self.txt_api_input.setText(fpath)

    def _run_api_fetch(self):
        from enterprise_engine import ingest_json_data
        inp = self.txt_api_input.text().strip()
        rec_path = self.txt_record_path.text().strip() or None
        token = self.txt_auth_token.text().strip()
        if not inp:
            QMessageBox.warning(self, "Missing Input", "Please provide a valid API URL, file path, or raw JSON.")
            return

        is_url = inp.startswith("http://") or inp.startswith("https://")
        headers = {"Authorization": f"Bearer {token}"} if token else None

        self.lbl_api_status.setText("Fetching and flattening JSON structure...")
        try:
            df = ingest_json_data(inp, is_url=is_url, record_path=rec_path, headers=headers)
            if df.empty:
                QMessageBox.warning(self, "Empty Data", "No tabular records could be extracted from this JSON structure.")
                return

            self.preview_df = df
            self.lbl_api_status.setText(f"✓ Flattened {len(df):,} rows × {len(df.columns)} columns")
            self.btn_load_api_app.setEnabled(True)

            self.tbl_api_preview.clear()
            self.tbl_api_preview.setRowCount(min(100, len(df)))
            self.tbl_api_preview.setColumnCount(len(df.columns))
            self.tbl_api_preview.setHorizontalHeaderLabels([str(c) for c in df.columns])
            for r_idx in range(min(100, len(df))):
                for c_idx, val in enumerate(df.iloc[r_idx]):
                    self.tbl_api_preview.setItem(r_idx, c_idx, QTableWidgetItem(str(val) if pd.notna(val) else ""))
            self.tbl_api_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        except Exception as e:
            self.lbl_api_status.setText(f"❌ Error: {str(e)[:80]}")
            QMessageBox.critical(self, "JSON Ingestion Failed", f"Could not parse JSON:\n{str(e)}")

    def _load_api_data_into_app(self):
        if self.preview_df is not None and not self.preview_df.empty:
            name = os.path.basename(self.txt_api_input.text().strip()) or "API_Data"
            self.data_imported.emit(self.preview_df, f"API/JSON: {name}")
            self.accept()

    def _build_export_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        if self.current_df is None or self.current_df.empty:
            empty_lbl = QLabel("No active dataset loaded in CleanSheet to export.\nPlease import or clean a dataset first.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #94A3B8; font-size: 13px; padding: 30px;")
            layout.addWidget(empty_lbl)
            return tab

        info_lbl = QLabel(f"Active Cleaned Dataset: <b>{len(self.current_df):,} rows</b> × <b>{len(self.current_df.columns)} columns</b>")
        layout.addWidget(info_lbl)

        # Target Connection
        conn_box = QHBoxLayout()
        conn_box.addWidget(QLabel("Target Database File or URI:"))
        self.txt_export_conn = QLineEdit()
        self.txt_export_conn.setPlaceholderText("e.g. C:/data/cleaned.db or postgresql://user:pwd@host/db")
        btn_exp_browse = QPushButton("Browse DB...")
        btn_exp_browse.clicked.connect(self._browse_export_sqlite)
        conn_box.addWidget(self.txt_export_conn, 1)
        conn_box.addWidget(btn_exp_browse)
        layout.addLayout(conn_box)

        # Target Table Name
        tbl_box = QHBoxLayout()
        tbl_box.addWidget(QLabel("Target Table Name:"))
        self.txt_export_table = QLineEdit("cleansheet_processed_data")
        tbl_box.addWidget(self.txt_export_table, 1)

        tbl_box.addWidget(QLabel("If Exists:"))
        self.combo_if_exists = QComboBox()
        self.combo_if_exists.addItems(["replace", "append", "fail"])
        tbl_box.addWidget(self.combo_if_exists)
        layout.addLayout(tbl_box)

        btn_export = QPushButton("🚀 Export Active Dataset to SQL Table")
        btn_export.setFixedHeight(40)
        btn_export.setStyleSheet("background: #4F46E5; color: white; font-weight: bold; border-radius: 6px; font-size: 13px;")
        btn_export.clicked.connect(self._run_export)
        layout.addWidget(btn_export)

        self.lbl_export_status = QLabel("")
        layout.addWidget(self.lbl_export_status)
        layout.addStretch(1)

        return tab

    def _on_db_type_changed(self, idx: int):
        if idx == 0:
            self.lbl_conn.setText("SQLite DB File:")
            self.txt_conn.setPlaceholderText("Select or enter path to .db / .sqlite file...")
            self.btn_browse.setVisible(True)
        else:
            self.lbl_conn.setText("Database URI:")
            self.txt_conn.setPlaceholderText("e.g. postgresql://user:pwd@localhost:5432/mydb or mysql+pymysql://...")
            self.btn_browse.setVisible(False)

    def _browse_sqlite_file(self):
        fpath, _ = QFileDialog.getOpenFileName(self, "Select SQLite Database File", "", "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*.*)")
        if fpath:
            self.txt_conn.setText(fpath)
            # Try to auto populate sample query with available tables
            try:
                conn = sqlite3.connect(fpath)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                tables = [r[0] for r in cursor.fetchall()]
                conn.close()
                if tables:
                    self.txt_query.setText(f"SELECT * FROM `{tables[0]}` LIMIT 500;")
                else:
                    self.txt_query.setText("SELECT * FROM your_table LIMIT 500;")
            except Exception:
                self.txt_query.setText("SELECT * FROM your_table LIMIT 500;")

    def _browse_export_sqlite(self):
        fpath, _ = QFileDialog.getSaveFileName(self, "Select or Create SQLite Database", "", "SQLite Databases (*.db *.sqlite);;All Files (*.*)")
        if fpath:
            self.txt_export_conn.setText(fpath)

    def _run_import_preview(self):
        conn_str = self.txt_conn.text().strip()
        query = self.txt_query.text().strip()
        if not conn_str:
            QMessageBox.warning(self, "Missing Connection", "Please select or provide a database path or connection URI.")
            return
        if not query:
            QMessageBox.warning(self, "Missing Query", "Please provide a valid SQL SELECT query.")
            return

        self.lbl_status.setText("Executing query...")
        try:
            import time
            t0 = time.time()
            df = execute_sql_query(conn_str, query)
            elapsed = time.time() - t0
            self.preview_df = df
            self.lbl_status.setText(f"✓ Fetched {len(df):,} rows × {len(df.columns)} cols in {elapsed:.2f}s")
            self.btn_load_into_app.setEnabled(True)
            self._render_preview_table(df.head(100))
        except Exception as e:
            self.lbl_status.setText(f"❌ Error: {str(e)[:80]}")
            QMessageBox.critical(self, "Query Execution Failed", f"Database error:\n{str(e)}")

    def _render_preview_table(self, df: pd.DataFrame):
        self.tbl_preview.clear()
        self.tbl_preview.setRowCount(len(df))
        self.tbl_preview.setColumnCount(len(df.columns))
        self.tbl_preview.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for r_idx, row in df.iterrows():
            pos = df.index.get_loc(r_idx)
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val) if pd.notna(val) else "")
                self.tbl_preview.setItem(pos, c_idx, item)
        self.tbl_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    def _load_data_into_app(self):
        if self.preview_df is not None and not self.preview_df.empty:
            source_name = os.path.basename(self.txt_conn.text().strip()) or "SQL_Database"
            self.data_imported.emit(self.preview_df, f"SQL: {source_name}")
            self.accept()

    def _run_export(self):
        conn_str = self.txt_export_conn.text().strip()
        tbl_name = self.txt_export_table.text().strip()
        if_exists = self.combo_if_exists.currentText()
        if not conn_str or not tbl_name:
            QMessageBox.warning(self, "Missing Details", "Please provide both database path/URI and table name.")
            return

        try:
            rows_written = export_to_sql_table(self.current_df, conn_str, tbl_name, if_exists=if_exists)
            self.lbl_export_status.setText(f"✓ Successfully exported {rows_written:,} rows to table '{tbl_name}'.")
            QMessageBox.information(self, "Export Complete", f"Successfully exported {rows_written:,} rows to table '{tbl_name}' in database.")
        except Exception as e:
            self.lbl_export_status.setText(f"❌ Export Failed: {str(e)[:80]}")
            QMessageBox.critical(self, "Export Failed", f"Database export error:\n{str(e)}")
