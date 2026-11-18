"""CleanSheet Desktop Studio - Main Presentation Layer.

Redesigned presentation layer with modern desktop ergonomics:
- ThemeManager with full Light/Dark mode support
- ModernSidebar with animated collapse (240px -> 72px)
- ModernHeader with page breadcrumbs, global search, theme toggle, and primary import CTA
- Animated page transitions (QGraphicsOpacityEffect & QPropertyAnimation)
- Toast/snackbar notifications
- High-DPI handling and keyboard shortcuts
"""
import sys
import os
from pathlib import Path

# Ensure application root directory is always on sys.path
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import re
import json
import logging
import traceback
import difflib
from datetime import datetime

import pandas as pd
from PySide6.QtCore import QTimer, Qt, QThread, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QFileDialog, QMessageBox, QDialog, QLabel,
    QGraphicsOpacityEffect, QStatusBar, QProgressBar, QPushButton,
    QTableWidgetItem, QScrollArea, QFrame
)

from clean_engine import (
    norm_cols, profile, quality_score, read_data, column_summary,
    clean_dataframe, issue_frame, validate_dataframe,
    build_change_report, write_excel_report, write_audit, read_audit
)

from theme import ThemeManager, generate_stylesheet, ThemeColors
from icons import get_icon
from components.widgets import ToastNotification, Card, PrimaryButton
from components.sidebar import ModernSidebar
from components.header import ModernHeader
from components.table import ModernTable
from pages import (
    OverviewPage, ImportPage, CleanDataPage,
    IssueReviewPage, ComparePage, HistoryPage, AutomationPage, ReportsPage
)

LOG_DIR = Path.home() / ".cleansheet"
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_DIR / "cleansheet.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
except Exception:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class WorkThread(QThread):
    completed = Signal(object, object, object, object)
    failed = Signal(str)

    def __init__(self, df, profile_name, custom=None):
        super().__init__()
        self.df = df.copy()
        self.profile_name = profile_name
        self.custom = custom

    def run(self):
        try:
            self.completed.emit(*clean_dataframe(self.df, self.profile_name, self.custom))
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


class MultiSheetWorkThread(QThread):
    """Clean all sheets in an Excel workbook sequentially."""
    progress = Signal(str)
    completed = Signal(object, object, object, object, object)  # (cleaned_dict, all_logs, original_dict, total_issues, active_cleaned)
    failed = Signal(str)

    def __init__(self, file_path, sheet_names, profile_name, custom=None, active_sheet=""):
        super().__init__()
        self.file_path = file_path
        self.sheet_names = sheet_names
        self.profile_name = profile_name
        self.custom = custom
        self.active_sheet = active_sheet or (sheet_names[0] if sheet_names else "")

    def run(self):
        try:
            cleaned_dict = {}
            original_dict = {}
            all_logs_list = []
            all_issues_list = []
            active_cleaned = None

            for i, sheet in enumerate(self.sheet_names, 1):
                self.progress.emit(f"Cleaning sheet {i}/{len(self.sheet_names)}: {sheet}")
                df = read_data(self.file_path, sheet=sheet)
                original_dict[sheet] = df.copy()
                cleaned_df, logs_df, old_df, issues_df = clean_dataframe(df, self.profile_name, self.custom)
                cleaned_dict[sheet] = cleaned_df
                
                # Tag logs & issues with sheet name
                if logs_df is not None and not logs_df.empty:
                    logs_tagged = logs_df.copy()
                    logs_tagged["sheet"] = sheet
                    all_logs_list.append(logs_tagged)
                if issues_df is not None and not issues_df.empty:
                    issues_tagged = issues_df.copy()
                    issues_tagged["sheet"] = sheet
                    all_issues_list.append(issues_tagged)

                if sheet == self.active_sheet or active_cleaned is None:
                    active_cleaned = cleaned_df

            combined_logs = pd.concat(all_logs_list, ignore_index=True) if all_logs_list else pd.DataFrame()
            combined_issues = pd.concat(all_issues_list, ignore_index=True) if all_issues_list else pd.DataFrame()

            self.completed.emit(cleaned_dict, combined_logs, original_dict, combined_issues, active_cleaned)
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


class BatchThread(QThread):
    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, paths, output_dir, profile_name, custom=None):
        super().__init__()
        self.paths = paths
        self.output_dir = output_dir
        self.profile_name = profile_name
        self.custom = custom

    def run(self):
        results = []
        try:
            os_dir = Path(self.output_dir)
            os_dir.mkdir(parents=True, exist_ok=True)
            for i, path in enumerate(self.paths, 1):
                self.progress.emit(f"Processing {i}/{len(self.paths)}: {Path(path).name}")
                try:
                    df = read_data(path)
                    cleaned, logs, old, issues = clean_dataframe(df, self.profile_name, self.custom)
                    out = os_dir / f"cleaned_{Path(path).stem}.xlsx"
                    if out.exists():
                        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        out = os_dir / f"cleaned_{Path(path).stem}_{stamp}.xlsx"
                    write_excel_report(out, cleaned, logs, old, issues, (self.custom or {}).get("validation_rules", []))
                    results.append({
                        "File": Path(path).name,
                        "Status": "Completed",
                        "Rows before": len(df),
                        "Rows after": len(cleaned),
                        "Quality before": quality_score(df),
                        "Quality after": quality_score(cleaned),
                        "Output": str(out),
                        "Error": ""
                    })
                except Exception as file_error:
                    results.append({
                        "File": Path(path).name,
                        "Status": "Failed",
                        "Rows before": 0,
                        "Rows after": 0,
                        "Quality before": 0,
                        "Quality after": 0,
                        "Output": "",
                        "Error": str(file_error)[:500]
                    })
            self.completed.emit(pd.DataFrame(results))
        except Exception as e:
            self.failed.emit(f"{e}\n\n{traceback.format_exc()}")


# Backward-compatible Metric frame for any external references
class Metric(QWidget):
    def __init__(self, label, value="--"):
        super().__init__()
        self.val = QLabel(str(value))
    def set(self, v):
        self.val.setText(str(v))


class Window(QMainWindow):
    """Main application window for CleanSheet Desktop Studio."""
    PAGE_INFO = [
        ("Overview", ""),
        ("Uploaded Data", "Browse your imported spreadsheet rows, columns, and sheets."),
        ("Clean Data", "Fix formatting, remove errors, and tidy up your data."),
        ("Issue Review", "Review detected issues, unusual values, and helpful suggestions."),
        ("Compare", "See what changed before and after cleaning side by side."),
        ("History", "View past cleaning activity, dates, and file records."),
        ("Automation", "Clean multiple files automatically in one go."),
        ("Reports & Export", "Download your clean dataset as Excel, CSV, or a summary report."),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CleanSheet | Data Cleaning Studio")
        # Load app icon from assets/icon.ico or assets/icon.png
        icon_path = APP_DIR / "assets" / "icon.ico"
        if not icon_path.exists():
            icon_path = APP_DIR / "assets" / "icon.png"
        if icon_path.exists():
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(get_icon("sparkles", "#2563EB", 64))
        self.resize(1450, 900)
        self.setMinimumSize(1100, 700)

        # Dataset & state variables
        self.df = None
        self.cleaned = None
        self.logs = None
        self.original = None
        self.issues = None
        self.path = None
        self.batch_results = None
        self.active_profile = "Clean Dataset"
        
        # Recurring batch automation timer
        self.schedule_timer = QTimer(self)
        self.schedule_timer.timeout.connect(self.run_scheduled_batch)
        self.schedule_runs = 0
        
        # Profile persistence
        self.profile_store_path = Path.home() / ".cleansheet" / "profiles.json"
        self.saved_profiles = self.load_profiles()

        # Enterprise Lineage Governance Tracker
        from enterprise_engine import DataLineageTracker
        self.lineage_tracker = DataLineageTracker()

        # In-App Auto-Update Checker
        self.pending_update_info = None
        self._check_for_updates_silently()

        # Build Presentation Shell
        self._setup_ui()
        self._setup_shortcuts()
        self._apply_theme(ThemeManager.instance().colors)
        ThemeManager.instance().subscribe(self._apply_theme)

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)
        
        shell_layout = QHBoxLayout(central)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        
        # Left: Modern Collapsible Sidebar
        self.sidebar = ModernSidebar(self)
        self.sidebar.nav_changed.connect(self.switch)
        shell_layout.addWidget(self.sidebar)
        
        # Right: Main Content Area (Header + Stacked Pages)
        main_area = QWidget()
        main_area.setObjectName("MainContent")
        main_layout = QVBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Top Header Bar
        self.header = ModernHeader(self)
        self.header.user_manual_clicked.connect(self.show_user_manual)
        self.header.toggle_sidebar_clicked.connect(self.sidebar.toggle_collapse)
        self.header.update_badge_clicked.connect(self._open_update_dialog)
        main_layout.addWidget(self.header)
        
        # Stacked Pages with transition effect
        self.stack = QStackedWidget()
        self.stack.setObjectName("PageStack")
        
        # Initialize modular pages
        self.page_overview = OverviewPage(
            on_import=self.open_file,
            on_workflow=lambda: self.go(2),
            on_issues=lambda: self.go(3),
            on_auto=lambda: self.go(6),
            on_fix_duplicates=self.quick_fix_duplicates,
            on_fix_blanks=self.quick_fix_blanks,
            on_trim_spaces=self.quick_trim_spaces,
            on_autocast=self.quick_autocast_types,
            on_export=lambda: self.go(7),
            parent=self
        )
        self.page_import = ImportPage(on_browse=self.open_file, parent=self)
        self.page_import.file_imported.connect(self.load_dropped_file)
        self.page_import.sheet_selected.connect(self.load_selected_sheet_by_name)
        
        self.page_workflow = CleanDataPage(parent=self)
        self.page_workflow.run_cleaning_requested.connect(self.on_profile_run_requested)
        self.page_workflow.save_profile_requested.connect(self.on_profile_save_requested)
        self.page_workflow.open_fuzzy_merge_requested.connect(self.open_fuzzy_dialog)
        self.page_workflow.open_masking_requested.connect(self.open_masking_dialog)
        self.page_workflow.open_outlier_requested.connect(self.open_outlier_dialog)
        self.page_workflow.open_column_transform_requested.connect(self.open_column_transform_dialog)
        self.page_workflow.open_combine_requested.connect(self.open_combine_dialog)
        self.page_workflow.open_standardizer_requested.connect(self.open_standardizer_dialog)
        self.page_workflow.open_sql_connector_requested.connect(self.open_sql_connector_dialog)
        self.page_workflow.open_deep_profile_requested.connect(self.open_deep_profile_dialog)
        self.page_workflow.open_lineage_requested.connect(self.open_lineage_dialog)
        self.page_workflow.open_big_data_requested.connect(self.open_big_data_dialog)
        self.page_workflow.export_recipe_requested.connect(self.export_cleaning_recipe)
        self.page_workflow.import_recipe_requested.connect(self.import_cleaning_recipe)
        self.page_workflow.refresh_presets(["Clean Dataset", "Custom Profile"] + sorted(self.saved_profiles.keys()))
        
        self.page_issues = IssueReviewPage(parent=self)
        self.page_issues.issue_status_updated.connect(self.set_issue_status)
        self.page_issues.fuzzy_matches_requested.connect(self.apply_fuzzy_matches)
        self.page_issues.export_issues_requested.connect(self.export_issues)
        self.page_issues.refresh_analysis_requested.connect(self.analyze_issues)
        self.page_issues.import_requested.connect(self.open_file)
        
        self.page_compare = ComparePage(parent=self)
        self.page_compare.import_requested.connect(self.open_file)
        self.page_compare.run_workflow_requested.connect(lambda: self.go(2))
        
        self.page_history = HistoryPage(parent=self)
        self.page_history.import_requested.connect(self.open_file)
        self.page_history.view_run_requested.connect(self.view_history_run)
        
        self.page_automation = AutomationPage(parent=self)
        self.page_automation.add_files_clicked.connect(self.add_batch_files)
        self.page_automation.remove_selected_clicked.connect(self.remove_batch_files)
        self.page_automation.browse_output_clicked.connect(self.choose_output)
        self.page_automation.run_batch_clicked.connect(self.run_batch)
        self.page_automation.start_schedule_clicked.connect(self.start_schedule)
        self.page_automation.stop_schedule_clicked.connect(self.stop_schedule)
        self.page_automation.combo_profile.clear()
        self.page_automation.combo_profile.addItems(["Clean Dataset"] + sorted(self.saved_profiles.keys()))
        
        self.page_reports = ReportsPage(parent=self)
        self.page_reports.save_excel_clicked.connect(self.save_excel)
        self.page_reports.save_protected_excel_clicked.connect(self.save_protected_excel)
        self.page_reports.save_csv_clicked.connect(self.save_csv)
        self.page_reports.save_json_clicked.connect(self.save_json)
        self.page_reports.save_pdf_clicked.connect(self.save_pdf_certificate)
        self.page_reports.view_audit_clicked.connect(self.show_audit_history)
        
        # Add 8 pages to stack
        for p in [
            self.page_overview,
            self.page_import,
            self.page_workflow,
            self.page_issues,
            self.page_compare,
            self.page_history,
            self.page_automation,
            self.page_reports,
        ]:
            p.setObjectName("PageWidget")
            p.setAttribute(Qt.WA_StyledBackground, True)
            self.stack.addWidget(p)
            
        main_layout.addWidget(self.stack, 1)
        shell_layout.addWidget(main_area, 1)
        
        # Hide Uploaded Data tab initially until a dataset is loaded
        self.sidebar.set_item_visible(1, False)
        
        # Rich Status Bar
        self._setup_status_bar()

    def _setup_status_bar(self):
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        
        # Left status label
        self.sb_status = QLabel("Ready · Import a CSV or Excel dataset to begin.")
        sb.addWidget(self.sb_status, 1)
        
        # Center progress bar (for background jobs)
        self.sb_progress = QProgressBar()
        self.sb_progress.setRange(0, 0)
        self.sb_progress.setFixedWidth(160)
        self.sb_progress.setVisible(False)
        sb.addPermanentWidget(self.sb_progress)
        
        # Right info
        self.sb_file_info = QLabel("No active file")
        sb.addPermanentWidget(self.sb_file_info)
        
        self.sb_lock = QLabel()
        self.sb_lock.setPixmap(get_icon("lock", "#94A3B8", 14).pixmap(14, 14))
        self.sb_lock.setToolTip("Local Workspace - files stay on this computer")
        sb.addPermanentWidget(self.sb_lock)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_file)
        QShortcut(QKeySequence("Ctrl+B"), self, self.sidebar.toggle_collapse)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, ThemeManager.instance().toggle_theme)
        
        for i in range(1, len(self.PAGE_INFO) + 1):
            QShortcut(QKeySequence(f"Ctrl+{i}"), self, lambda idx=i-1: self.go(idx))

    def _apply_theme(self, colors: ThemeColors):
        self.setStyleSheet(generate_stylesheet(colors))
        self.sb_lock.setPixmap(get_icon("lock", colors.text_muted, 14).pixmap(14, 14))

    def switch(self, index: int):
        if 0 <= index < len(self.PAGE_INFO):
            title, subtitle = self.PAGE_INFO[index]
            self.header.set_title(title, subtitle)
            self.stack.setCurrentIndex(index)
            
            if index == 3:
                self.refresh_issues()
            elif index == 5:
                self.page_history.refresh_history()
            elif index == 7:
                self.refresh_report()

    def go(self, index: int):
        self.sidebar.select_index(index)
        self.switch(index)

    def load_profiles(self):
        try:
            if self.profile_store_path.exists():
                data = json.loads(self.profile_store_path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            pass
        return {}

    def persist_profiles(self):
        self.profile_store_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.profile_store_path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(self.saved_profiles, indent=2, ensure_ascii=False), encoding="utf-8")
        temp_path.replace(self.profile_store_path)

    # ---------------- File Loading & Data Handling ----------------

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select data file", "", "Data files (*.csv *.xlsx *.xls)")
        if path:
            self._load_file_path(path)

    def load_dropped_file(self, path: str):
        if path:
            self._load_file_path(path)

    def _load_file_path(self, path: str):
        try:
            self.path = path
            sheet_names = []
            if Path(path).suffix.lower() in (".xlsx", ".xls"):
                try:
                    sheet_names = pd.ExcelFile(path).sheet_names
                except Exception:
                    sheet_names = []
                self.df = read_data(path, sheet=sheet_names[0] if sheet_names else 0)
            else:
                self.df = read_data(path)
                
            self.cleaned = self.logs = self.original = self.issues = None
            
            # Update pages
            self.sheet_names = sheet_names
            self.current_sheet = sheet_names[0] if sheet_names else ""
            self.cleaned_sheets_dict = None  # Holds multi-sheet cleaned data
            self.page_import.set_dataset(path, self.df, sheet_names)
            self.page_overview.update_metrics(self.df, path, self.current_sheet)
            self.page_workflow.set_available_sheets(sheet_names, self.current_sheet)
            
            # Update status bar
            p_name = Path(path).name
            self.sb_status.setText(f"Loaded {p_name} ({len(self.df):,} rows × {len(self.df.columns)} cols)")
            self.sb_file_info.setText(f"{p_name} · {len(self.df):,} × {len(self.df.columns)}")
            
            self.analyze_issues()
            
            # Reveal the Uploaded Data tab in sidebar now that dataset is loaded
            self.sidebar.set_item_visible(1, True)
            
            self.go(1)
            ToastNotification.show_toast(self, f"Imported {p_name} successfully", "success")
            if hasattr(self, "lineage_tracker"):
                self.lineage_tracker.record_step("File Import", "Read raw file", 0, len(self.df), f"Imported {p_name} ({len(self.df)} rows, {len(self.df.columns)} cols)")
        except Exception as e:
            logging.exception("File import failed: %s", path)
            QMessageBox.critical(self, "Could not open file", f"The file could not be opened.\n\n{e}")

    def load_selected_sheet_by_name(self, sheet: str):
        if not self.path or not sheet:
            return
        try:
            self.current_sheet = sheet
            self.df = read_data(self.path, sheet=sheet)
            self.cleaned = self.logs = self.original = self.issues = None
            
            # If this sheet was previously multi-sheet cleaned, recover its cleaned view
            if hasattr(self, "cleaned_sheets_dict") and self.cleaned_sheets_dict and sheet in self.cleaned_sheets_dict:
                self.cleaned = self.cleaned_sheets_dict[sheet]

            # Update Import Preview Page with new sheet data
            self.page_import.update_sheet_data(self.df)
            
            # Update Overview Page & Workflow scope
            self.page_overview.update_metrics(self.df, self.path, sheet)
            self.page_workflow.set_available_sheets(getattr(self, "sheet_names", []), sheet)
            self.analyze_issues()
            
            # Update Status Bar
            p_name = Path(self.path).name
            self.sb_status.setText(f"Loaded sheet '{sheet}' ({len(self.df):,} rows × {len(self.df.columns)} cols)")
            self.sb_file_info.setText(f"{p_name} [{sheet}] · {len(self.df):,} × {len(self.df.columns)}")
            
            ToastNotification.show_toast(self, f"Loaded sheet '{sheet}'", "info")
        except Exception as e:
            logging.exception("Excel sheet import failed: %s / %s", self.path, sheet)
            QMessageBox.critical(self, "Could not open sheet", f"The sheet could not be opened.\n\n{e}")

    # ---------------- Cleaning Workflow Execution ----------------

    def run_profile(self, name: str, custom=None):
        # Always use self.cleaned as source if user has already performed actions (like masking or fuzzy merge)
        source_df = self.cleaned if self.cleaned is not None else self.df
        if source_df is None:
            QMessageBox.information(self, "No dataset loaded", "Please import a CSV or Excel dataset first.")
            return
            
        self.active_profile = name
        self.sb_progress.show()
        self.sb_status.setText(f"Executing {name}…")
        self.page_workflow.set_running(True, name)
        
        self.worker = WorkThread(source_df, name, custom)
        self.worker.completed.connect(self.clean_done)
        self.worker.failed.connect(self.clean_error)
        self.worker.start()

    def clean_done(self, d, logs, original, issues):
        # Ensure self.original retains the true initial raw dataset
        true_original = self.original if self.original is not None else (self.df if self.df is not None else original)
        self.cleaned = d
        self.original = true_original
        self.issues = issues
        
        # Combine existing pre-cleaning logs (e.g. masking or fuzzy merge) with new logs
        if self.logs is not None and not self.logs.empty:
            self.logs = pd.concat([self.logs, logs], ignore_index=True)
        else:
            self.logs = logs

        try:
            write_audit(
                "Cleaning run",
                self.path or "Current dataset",
                self.active_profile,
                len(true_original),
                len(d),
                "Completed",
                f"Quality {quality_score(true_original):.1f} → {quality_score(d):.1f}"
            )
        except Exception:
            pass
            
        self.sb_progress.hide()
        self.sb_status.setText(f"Cleaning complete: {len(true_original):,} → {len(d):,} rows")

        # Record enterprise lineage audit
        if hasattr(self, "lineage_tracker"):
            self.lineage_tracker.record_step("Data Cleaning", f"Profile: {self.active_profile}", len(true_original), len(d), f"Quality {quality_score(true_original):.1f} → {quality_score(d):.1f}")
        
        self.page_workflow.set_running(False)
        self.page_workflow.show_completion_summary(true_original, d, issues, self.logs)
        self.page_overview.update_metrics(d, self.path)
        self.page_history.refresh_history()
        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        
        ToastNotification.show_toast(self, f"{self.active_profile} completed successfully!", "success")
        self.go(4)

    def clean_error(self, e):
        logging.error("Cleaning failed: %s", e)
        self.sb_progress.hide()
        self.sb_status.setText("Cleaning failed")
        self.page_workflow.set_running(False)
        QMessageBox.critical(self, "Cleaning failed", str(e))

    # ---------------- Profiles & Configuration Handlers ----------------

    def on_profile_run_requested(self, name: str, custom_settings=None, clean_all_sheets=False):
        settings = None
        if name == "Custom Profile" or custom_settings:
            settings = custom_settings
        elif name in self.saved_profiles:
            settings = dict(self.saved_profiles[name])
            settings.pop("name", None)

        if clean_all_sheets and hasattr(self, "sheet_names") and len(self.sheet_names) > 1:
            self.run_multi_sheet_clean(name, settings)
        else:
            self.run_profile(name, settings)

    def run_multi_sheet_clean(self, name: str, custom=None):
        if not self.path:
            QMessageBox.information(self, "No file loaded", "Please import an Excel file first.")
            return

        self.active_profile = name
        self.sb_progress.show()
        self.sb_status.setText(f"Cleaning all {len(self.sheet_names)} sheets in workbook…")
        self.page_workflow.set_running(True, f"All Sheets ({name})")

        self.multi_worker = MultiSheetWorkThread(
            self.path,
            self.sheet_names,
            name,
            custom,
            active_sheet=getattr(self, "current_sheet", "")
        )
        self.multi_worker.progress.connect(self.sb_status.setText)
        self.multi_worker.completed.connect(self.multi_sheet_clean_done)
        self.multi_worker.failed.connect(self.clean_error)
        self.multi_worker.start()

    def multi_sheet_clean_done(self, cleaned_dict, combined_logs, original_dict, total_issues, active_cleaned):
        self.cleaned_sheets_dict = cleaned_dict
        self.original_sheets_dict = original_dict
        
        # Point active display to current sheet
        curr = getattr(self, "current_sheet", self.sheet_names[0])
        self.cleaned = cleaned_dict.get(curr, active_cleaned)
        self.original = original_dict.get(curr, self.df)
        self.logs = combined_logs
        self.issues = total_issues

        try:
            total_before = sum(len(df) for df in original_dict.values())
            total_after = sum(len(df) for df in cleaned_dict.values())
            write_audit(
                "Multi-Sheet Clean",
                self.path,
                f"All Sheets ({self.active_profile})",
                total_before,
                total_after,
                "Completed",
                f"Cleaned {len(cleaned_dict)} sheets"
            )
        except Exception:
            pass

        self.sb_progress.hide()
        self.sb_status.setText(f"All {len(cleaned_dict)} sheets cleaned successfully!")
        
        self.page_workflow.set_running(False)
        self.page_workflow.show_completion_summary(self.original, self.cleaned, total_issues, combined_logs)
        self.page_overview.update_metrics(self.cleaned, self.path, curr)
        self.page_history.refresh_history()
        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        
        ToastNotification.show_toast(self, f"Cleaned all {len(cleaned_dict)} sheets successfully!", "success")
        self.go(4)

    def on_profile_save_requested(self, name: str, settings: dict):
        try:
            self.saved_profiles[name] = settings
            self.persist_profiles()
            
            # Refresh profiles dropdowns
            all_presets = ["Clean Dataset", "Custom Profile"] + sorted(self.saved_profiles.keys())
            self.page_workflow.refresh_presets(all_presets)
            self.page_automation.combo_profile.clear()
            self.page_automation.combo_profile.addItems(["Clean Dataset"] + sorted(self.saved_profiles.keys()))
            
            ToastNotification.show_toast(self, f"Saved profile '{name}'", "success")
        except Exception as e:
            QMessageBox.critical(self, "Could not save profile", str(e))

    # ---------------- Issue Analysis & Review ----------------

    def analyze_issues(self):
        if self.cleaned is not None:
            self.issues = issue_frame(self.cleaned)
            validation = validate_dataframe(self.cleaned, self.current_validation_rules())
            if not validation.empty:
                row_findings = validation[validation["Row number"].astype(str).ne("")]
                for (col, rule), group in row_findings.groupby(["Column", "Rule"]):
                    self.issues.loc[len(self.issues)] = {
                        "Category": "Schema validation",
                        "Column": col,
                        "Count": len(group),
                        "Details": f"{rule}: {group['Issue'].iloc[0]}",
                        "Suggested action": "Review row-level validation report",
                        "Review status": "Pending"
                    }
        elif self.df is not None:
            self.issues = issue_frame(self.df)
        else:
            self.issues = pd.DataFrame(columns=["Category", "Column", "Count", "Details", "Suggested action", "Review status"])
            
        self.refresh_issues()

    def refresh_issues(self):
        self.page_issues.set_issues_data(self.issues)

    def set_issue_status(self, status: str):
        if self.issues is None or self.issues.empty:
            return
        selected = self.page_issues.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Select an issue", "Select one or more issue rows first.")
            return
            
        filtered = self.issues.copy()
        cat = self.page_issues.current_category
        if cat != "All issues" and "Category" in filtered.columns:
            filtered = filtered[filtered["Category"] == cat]
            
        for idx in selected:
            if idx.row() < len(filtered):
                orig_idx = filtered.index[idx.row()]
                self.issues.loc[orig_idx, "Review status"] = status
                
        self.refresh_issues()
        self.sb_status.setText(f"Issue status marked: {status}")
        ToastNotification.show_toast(self, f"Marked issue as {status}", "info")

    def apply_fuzzy_matches(self):
        if self.issues is None or self.issues.empty:
            QMessageBox.information(self, "No findings", "Run issue analysis first.")
            return
            
        selected = self.page_issues.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "Select a finding", "Select an 'Inconsistent categories' finding first.")
            return
            
        visible = self.issues.copy()
        cat = self.page_issues.current_category
        if cat != "All issues" and "Category" in visible.columns:
            visible = visible[visible["Category"] == cat]
            
        idx = selected[0].row()
        if idx >= len(visible):
            return
            
        finding = visible.iloc[idx]
        if finding.get("Category") != "Inconsistent categories":
            QMessageBox.information(self, "Not a category finding", "Select an 'Inconsistent categories' row to propose matches.")
            return
            
        col = str(finding.get("Column"))
        target = self.cleaned if self.cleaned is not None else self.df
        if target is None or col not in target.columns:
            QMessageBox.warning(self, "Column unavailable", "This finding's column is not in the dataset.")
            return
            
        values = target[col].dropna().astype(str).str.strip()
        unique = list(dict.fromkeys(v for v in values if v))
        counts = values.value_counts().to_dict()
        mapping = {}
        for value in unique:
            best = None
            best_ratio = 0.70
            for candidate in unique:
                if value == candidate or value.casefold() == candidate.casefold():
                    continue
                ratio = difflib.SequenceMatcher(None, value.casefold(), candidate.casefold()).ratio()
                if ratio >= best_ratio and counts.get(candidate, 0) > counts.get(value, 0):
                    best = candidate
                    best_ratio = ratio
            if best:
                mapping[value] = best
                
        if not mapping:
            QMessageBox.information(self, "No safe matches", "No category matches met the 70% similarity threshold.")
            return
            
        preview = "\n".join(f"{old}  →  {new}" for old, new in list(mapping.items())[:20])
        if len(mapping) > 20:
            preview += f"\n… and {len(mapping)-20} more"
            
        answer = QMessageBox.question(
            self,
            "Confirm category standardization",
            f"These suggested labels will be standardized in working copy of '{col}':\n\n{preview}\n\nApply these changes? Source file is not modified.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if answer != QMessageBox.Yes:
            return
            
        if self.cleaned is None:
            self.original = self.df.copy()
            self.cleaned = self.df.copy()
            self.logs = pd.DataFrame(columns=["Time", "Action", "Count", "Details"])
            
        before = self.cleaned[col].astype("string")
        self.cleaned[col] = self.cleaned[col].astype("string").replace(mapping)
        changed = int((before.fillna("<NA>") != self.cleaned[col].fillna("<NA>")).sum())
        
        new_log = pd.DataFrame([{
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Action": "Fuzzy category standardization",
            "Count": changed,
            "Details": f"Column {col}; {len(mapping)} label mapping(s) applied."
        }])
        self.logs = pd.concat([self.logs, new_log], ignore_index=True)
        write_audit("Fuzzy standardization", self.path or "Current dataset", "Manual review", len(self.original), len(self.cleaned), "Completed", f"Column {col}; {changed} values changed")
        
        self.issues = issue_frame(self.cleaned)
        self.page_overview.update_metrics(self.cleaned, self.path)
        self.refresh_issues()
        self.refresh_report()
        ToastNotification.show_toast(self, f"Standardized {changed} values in {col}", "success")

    def quick_fix_duplicates(self):
        """Immediately deduplicate dataset from Overview without switching tabs."""
        target = self.cleaned if self.cleaned is not None else self.df
        if target is None or target.empty:
            ToastNotification.show_toast(self, "No dataset loaded to clean.", "info")
            return
            
        dup_count = int(target.duplicated().sum())
        if dup_count == 0:
            ToastNotification.show_toast(self, "No duplicate rows detected.", "info")
            return
            
        if self.original is None:
            self.original = target.copy()
            
        before_len = len(target)
        cleaned_df = target.drop_duplicates().copy()
        removed = before_len - len(cleaned_df)
        
        self.df = cleaned_df.copy()
        self.cleaned = cleaned_df
        
        new_log = pd.DataFrame([{
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Action": "Removed exact duplicates",
            "Count": int(removed),
            "Details": f"Removed {removed} duplicate rows directly from Overview."
        }])
        self.logs = pd.concat([self.logs, new_log], ignore_index=True) if self.logs is not None else new_log
        
        try:
            write_audit(
                "Quick Fix: Remove Duplicates",
                self.path or "Current dataset",
                "Overview Quick Action",
                before_len,
                len(cleaned_df),
                "Completed",
                f"Removed {removed} duplicate rows without switching tabs."
            )
        except Exception:
            pass
            
        self.issues = issue_frame(cleaned_df)
        self.page_overview.update_metrics(cleaned_df, self.path or "")
        self.page_import.set_dataset(self.path or "", cleaned_df)
        self.page_history.refresh_history()
        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        
        p_name = Path(self.path).name if self.path else "Dataset"
        self.sb_status.setText(f"{p_name}: removed {removed} duplicate row(s) ({len(cleaned_df):,} rows)")
        ToastNotification.show_toast(self, f"Removed {removed} duplicate row(s) successfully!", "success")

    def quick_fix_blanks(self):
        """Immediately fill missing/blank cells from Overview without switching tabs."""
        target = self.cleaned if self.cleaned is not None else self.df
        if target is None or target.empty:
            ToastNotification.show_toast(self, "No dataset loaded to clean.", "info")
            return
            
        cleaned_df = target.copy()
        for col in cleaned_df.select_dtypes(include=["object", "string"]).columns:
            cleaned_df[col] = cleaned_df[col].astype("string").str.strip().replace("", pd.NA)
            
        missing_count = int(cleaned_df.isna().sum().sum())
        all_empty = int(cleaned_df.isna().all(axis=1).sum())
        if missing_count == 0 and all_empty == 0:
            ToastNotification.show_toast(self, "No missing or blank cells detected.", "info")
            return
            
        if self.original is None:
            self.original = target.copy()
            
        before_rows = len(cleaned_df)
        if all_empty > 0:
            cleaned_df = cleaned_df.dropna(how="all").copy()
            
        filled_count = 0
        for col in cleaned_df.columns:
            na_count = int(cleaned_df[col].isna().sum())
            if na_count == 0:
                continue
            if pd.api.types.is_numeric_dtype(cleaned_df[col]):
                val = cleaned_df[col].median()
                if pd.isna(val):
                    val = 0
            else:
                modes = cleaned_df[col].mode(dropna=True)
                val = modes.iloc[0] if not modes.empty else "N/A"
            cleaned_df[col] = cleaned_df[col].fillna(val)
            filled_count += na_count
            
        self.df = cleaned_df.copy()
        self.cleaned = cleaned_df
        
        new_log = pd.DataFrame([{
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Action": "Filled missing values",
            "Count": int(filled_count),
            "Details": f"Filled {filled_count} blank cells (numeric median, text mode)."
        }])
        self.logs = pd.concat([self.logs, new_log], ignore_index=True) if self.logs is not None else new_log
        
        try:
            write_audit(
                "Quick Fix: Fill Blanks",
                self.path or "Current dataset",
                "Overview Quick Action",
                before_rows,
                len(cleaned_df),
                "Completed",
                f"Filled {filled_count} blank cells without switching tabs."
            )
        except Exception:
            pass
            
        self.issues = issue_frame(cleaned_df)
        self.page_overview.update_metrics(cleaned_df, self.path or "")
        self.page_import.set_dataset(self.path or "", cleaned_df)
        self.page_history.refresh_history()
        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        
        p_name = Path(self.path).name if self.path else "Dataset"
        self.sb_status.setText(f"{p_name}: fixed {filled_count} blank cell(s)")
        ToastNotification.show_toast(self, f"Fixed {filled_count} blank cell(s) successfully!", "success")

    def quick_trim_spaces(self):
        """Immediately strip whitespace in string columns without leaving Overview."""
        target = self.cleaned if self.cleaned is not None else self.df
        if target is None or target.empty:
            ToastNotification.show_toast(self, "No dataset loaded to clean.", "info")
            return
        if self.original is None:
            self.original = target.copy()
            
        cleaned_df = target.copy()
        changed = 0
        for col in cleaned_df.select_dtypes(include=["object", "string"]).columns:
            before = cleaned_df[col].astype("string")
            after = before.str.strip().replace("", pd.NA)
            changed += int((before.fillna("<NA>") != after.fillna("<NA>")).sum())
            cleaned_df[col] = after
            
        if changed == 0:
            ToastNotification.show_toast(self, "No untrimmed text values found.", "info")
            return
            
        self.df = cleaned_df.copy()
        self.cleaned = cleaned_df
        
        new_log = pd.DataFrame([{
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Action": "Trimmed text values",
            "Count": int(changed),
            "Details": f"Trimmed whitespace across {changed} cell(s)."
        }])
        self.logs = pd.concat([self.logs, new_log], ignore_index=True) if self.logs is not None else new_log
        
        try:
            write_audit(
                "Quick Fix: Trim Spaces",
                self.path or "Current dataset",
                "Overview Quick Action",
                len(target),
                len(cleaned_df),
                "Completed",
                f"Trimmed whitespace across {changed} cell(s)."
            )
        except Exception:
            pass
            
        self.issues = issue_frame(cleaned_df)
        self.page_overview.update_metrics(cleaned_df, self.path or "")
        self.page_import.set_dataset(self.path or "", cleaned_df)
        self.page_history.refresh_history()
        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, f"Trimmed whitespace across {changed} cell(s)!", "success")

    def quick_autocast_types(self):
        """Automatically detect & cast numbers and date-like strings to proper types."""
        target = self.cleaned if self.cleaned is not None else self.df
        if target is None or target.empty:
            ToastNotification.show_toast(self, "No dataset loaded to clean.", "info")
            return
        if self.original is None:
            self.original = target.copy()
            
        cleaned_df = target.copy()
        converted_cols = []
        for col in cleaned_df.select_dtypes(include=["object", "string"]).columns:
            series = cleaned_df[col].astype("string").str.strip().str.replace(r"[₹$€£,\s]", "", regex=True)
            mask = series.notna() & series.ne("")
            if mask.sum():
                numeric = pd.to_numeric(series, errors="coerce")
                if numeric[mask].notna().mean() >= 0.85:
                    cleaned_df[col] = numeric
                    converted_cols.append(str(col))
                    continue
            if any(k in str(col).lower() for k in ["date", "time", "dob", "created", "updated"]):
                dt = pd.to_datetime(cleaned_df[col], errors="coerce", dayfirst=True)
                mask_dt = cleaned_df[col].notna() & cleaned_df[col].astype("string").str.strip().ne("")
                if mask_dt.sum() and dt[mask_dt].notna().mean() >= 0.70:
                    cleaned_df[col] = dt
                    converted_cols.append(str(col))
                    
        if not converted_cols:
            ToastNotification.show_toast(self, "No convertible column types detected.", "info")
            return
            
        self.df = cleaned_df.copy()
        self.cleaned = cleaned_df
        
        new_log = pd.DataFrame([{
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Action": "Converted data types",
            "Count": len(converted_cols),
            "Details": f"Converted columns: {', '.join(converted_cols)}"
        }])
        self.logs = pd.concat([self.logs, new_log], ignore_index=True) if self.logs is not None else new_log
        
        try:
            write_audit(
                "Quick Fix: Auto-Cast Types",
                self.path or "Current dataset",
                "Overview Quick Action",
                len(target),
                len(cleaned_df),
                "Completed",
                f"Converted {len(converted_cols)} columns: {', '.join(converted_cols)}"
            )
        except Exception:
            pass
            
        self.issues = issue_frame(cleaned_df)
        self.page_overview.update_metrics(cleaned_df, self.path or "")
        self.page_import.set_dataset(self.path or "", cleaned_df)
        self.page_history.refresh_history()
        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, f"Converted {len(converted_cols)} column(s) successfully!", "success")

    def export_issues(self):
        if self.issues is None or self.issues.empty:
            QMessageBox.information(self, "No issues", "No issue findings are available to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export issue findings", "issue_review.csv", "CSV (*.csv)")
        if path:
            if not path.lower().endswith(".csv"):
                path += ".csv"
            try:
                self.issues.to_csv(path, index=False, encoding="utf-8-sig")
                ToastNotification.show_toast(self, "Issues exported successfully", "success")
            except Exception as e:
                QMessageBox.critical(self, "Export failed", str(e))

    # ---------------- Batch Automation ----------------

    def add_batch_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select files for batch processing", "", "Data files (*.csv *.xlsx *.xls)")
        existing = {self.page_automation.batch_list.item(i).text() for i in range(self.page_automation.batch_list.count())}
        for p in paths:
            if p not in existing:
                self.page_automation.batch_list.addItem(p)

    def remove_batch_files(self):
        items = self.page_automation.batch_list.selectedItems()
        for it in items:
            row = self.page_automation.batch_list.row(it)
            self.page_automation.batch_list.takeItem(row)

    def choose_output(self):
        curr = self.page_automation.output_path.text()
        folder = QFileDialog.getExistingDirectory(self, "Select batch output directory", curr)
        if folder:
            self.page_automation.output_path.setText(folder)

    def run_batch(self):
        count = self.page_automation.batch_list.count()
        if count == 0:
            QMessageBox.information(self, "No files", "Add at least one file to the batch list.")
            return
            
        paths = [self.page_automation.batch_list.item(i).text() for i in range(count)]
        profile_name = self.page_automation.combo_profile.currentText()
        custom = dict(self.saved_profiles.get(profile_name, {})) if profile_name in self.saved_profiles else None
        if custom:
            custom.pop("name", None)
            
        self.page_automation.set_running(True, "Starting batch execution…")
        self.sb_progress.show()
        
        self.batch_worker = BatchThread(paths, self.page_automation.output_path.text(), profile_name, custom)
        self.batch_worker.progress.connect(self.page_automation.status_lbl.setText)
        self.batch_worker.completed.connect(self.batch_done)
        self.batch_worker.failed.connect(self.batch_error)
        self.batch_worker.start()

    def batch_done(self, result):
        self.batch_results = result
        self.sb_progress.hide()
        self.page_automation.set_running(False, f"Batch complete · {len(result)} file(s) processed.")
        self.page_automation.set_results(result)
        ToastNotification.show_toast(self, f"Batch job processed {len(result)} file(s)", "success")

    def batch_error(self, e):
        self.sb_progress.hide()
        self.page_automation.set_running(False, "Batch processing failed.")
        QMessageBox.critical(self, "Batch processing failed", str(e))

    def start_schedule(self):
        count = self.page_automation.batch_list.count()
        if count == 0:
            QMessageBox.information(self, "No files", "Add files to the batch list before starting a schedule.")
            return
        minutes = self.page_automation.spin_minutes.value()
        self.schedule_timer.start(minutes * 60 * 1000)
        self.page_automation.btn_start_sched.setEnabled(False)
        self.page_automation.btn_stop_sched.setEnabled(True)
        self.page_automation.lbl_schedule_status.setText(f"Scheduled every {minutes} minute(s) while CleanSheet is open.")
        ToastNotification.show_toast(self, f"Schedule started ({minutes} min)", "info")

    def stop_schedule(self):
        self.schedule_timer.stop()
        self.page_automation.btn_start_sched.setEnabled(True)
        self.page_automation.btn_stop_sched.setEnabled(False)
        self.page_automation.lbl_schedule_status.setText("Schedule is off.")
        ToastNotification.show_toast(self, "Schedule stopped", "info")

    def run_scheduled_batch(self):
        if self.page_automation.batch_list.count() == 0 or not self.page_automation.btn_run.isEnabled():
            return
        self.schedule_runs += 1
        self.page_automation.lbl_schedule_status.setText(f"Scheduled run #{self.schedule_runs} running…")
        self.run_batch()

    # ---------------- Compare & Visual Diff ----------------

    def refresh_compare(self):
        self.page_compare.set_data(self.original if self.original is not None else self.df, self.cleaned)

    def view_history_run(self, source_path: str, profile_name: str):
        """Load the historical run dataset and display side-by-side original vs cleaned comparison strictly in Compare tab."""
        p = Path(source_path)
        if not source_path or source_path == "None" or source_path == "Current dataset":
            # View current dataset in compare
            if self.df is not None:
                if self.cleaned is None:
                    # Clean it now with profile
                    try:
                        c, l, orig, iss = clean_dataframe(self.df, profile_name or "Clean Dataset")
                        self.cleaned, self.logs, self.original, self.issues = c, l, orig, iss
                    except Exception as e:
                        QMessageBox.warning(self, "Could not clean", str(e))
                self.refresh_compare()
                self.go(4)
            else:
                QMessageBox.information(self, "No dataset loaded", "No active dataset is currently in memory.")
            return

        if not p.exists():
            # If path moved or doesn't exist, check current dataset or notify
            if self.path and Path(self.path).name == p.name and self.df is not None:
                if self.cleaned is None:
                    try:
                        c, l, orig, iss = clean_dataframe(self.df, profile_name or "Clean Dataset")
                        self.cleaned, self.logs, self.original, self.issues = c, l, orig, iss
                    except Exception as e:
                        QMessageBox.warning(self, "Could not clean", str(e))
                self.refresh_compare()
                self.go(4)
                return
            QMessageBox.warning(
                self,
                "File not found",
                f"The source file was moved or is no longer at:\n{source_path}\n\nYou can re-import it using '+ Import File'."
            )
            return

        try:
            # Read historical data directly for comparison only (without overriding Overview / Import tabs)
            if p.suffix.lower() in (".xlsx", ".xls"):
                try:
                    sheets = pd.ExcelFile(str(p)).sheet_names
                    hist_df = read_data(str(p), sheet=sheets[0] if sheets else 0)
                except Exception:
                    hist_df = read_data(str(p))
            else:
                hist_df = read_data(str(p))

            custom_settings = None
            if profile_name in self.saved_profiles:
                custom_settings = dict(self.saved_profiles[profile_name])
                custom_settings.pop("name", None)

            # Clean historical dataset to get both original and cleaned versions
            c, l, orig, iss = clean_dataframe(hist_df, profile_name or "Clean Dataset", custom=custom_settings)

            # Set directly into Compare page only
            self.page_compare.set_data(orig if orig is not None else hist_df, c)

            # Switch exclusively to Compare view (Index 4)
            self.go(4)
            ToastNotification.show_toast(self, f"Viewing comparison for: {p.name}", "info")
        except Exception as e:
            logging.exception("Failed to view historical run: %s", source_path)
            QMessageBox.critical(self, "Error loading history data", f"Could not load data for comparison:\n\n{e}")

    # ---------------- Reports & Export ----------------

    def refresh_report(self):
        self.page_reports.set_report_data(self.original, self.cleaned, self.logs, self.path)

    def current_validation_rules(self):
        name = getattr(self, "active_profile", "Clean Dataset")
        if name in self.saved_profiles:
            rules = self.saved_profiles[name].get("validation_rules", [])
            return rules if isinstance(rules, list) else []
        if name == "Custom Profile":
            try:
                settings = self.page_workflow.get_custom_settings()
                return settings.get("validation_rules", [])
            except Exception:
                return []
        return []

    def save_excel(self):
        if self.cleaned is None and not getattr(self, "cleaned_sheets_dict", None):
            QMessageBox.information(self, "No cleaned data", "Run a cleaning workflow first.")
            return
        default_name = f"cleaned_{Path(self.path).stem if self.path else 'dataset'}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Save Excel Workbook", default_name, "Excel Workbook (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            # Check if multi-sheet cleaning was run
            if hasattr(self, "cleaned_sheets_dict") and self.cleaned_sheets_dict:
                target = Path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                temp = target.with_name(f".{target.stem}.{stamp}.tmp.xlsx")
                with pd.ExcelWriter(temp, engine="openpyxl", datetime_format="yyyy-mm-dd") as writer:
                    # Write each cleaned sheet
                    for s_name, s_df in self.cleaned_sheets_dict.items():
                        s_df.to_excel(writer, index=False, sheet_name=s_name[:31])
                    # Add Change Log sheet
                    if self.logs is not None and not self.logs.empty:
                        self.logs.to_excel(writer, index=False, sheet_name="Cleaning Log")
                    # Add Issues sheet
                    if self.issues is not None and not self.issues.empty:
                        self.issues.to_excel(writer, index=False, sheet_name="Issue Review")
                temp.replace(target)
                ToastNotification.show_toast(self, f"Saved multi-sheet workbook ({len(self.cleaned_sheets_dict)} sheets) to {target.name}", "success")
            else:
                write_excel_report(path, self.cleaned, self.logs, self.original, self.issues, self.current_validation_rules())
                ToastNotification.show_toast(self, f"Excel saved to {Path(path).name}", "success")
        except Exception as e:
            logging.exception("Excel export failed")
            QMessageBox.critical(self, "Export failed", str(e))

    def save_protected_excel(self):
        """Export cleaned dataset into an encrypted/password-protected Excel workbook."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None or target_df.empty:
            QMessageBox.information(self, "No Cleaned Data", "Please run a cleaning workflow first.")
            return

        from PySide6.QtWidgets import QInputDialog
        pwd, ok = QInputDialog.getText(
            self, "Excel Encryption & Password Lock",
            "Enter password to protect & lock this cleaned Excel workbook:",
            QLineEdit.Password
        )
        if not ok or not pwd.strip():
            return

        default_name = f"protected_{Path(self.path).stem if self.path else 'dataset'}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Save Password-Protected Excel", default_name, "Excel Workbook (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            from enterprise_engine import save_protected_excel
            save_protected_excel(target_df, path, password=pwd.strip())
            ToastNotification.show_toast(self, f"Protected Excel saved to {Path(path).name} (Password Locked)", "success")
            QMessageBox.information(
                self, "Password Protection Enabled",
                f"Workbook saved successfully with password encryption!\n\nDestination: {path}\nPassword is required to modify/unlock."
            )
        except Exception as e:
            logging.exception("Protected Excel export failed")
            QMessageBox.critical(self, "Export Failed", str(e))

    def save_csv(self):
        if self.cleaned is None:
            QMessageBox.information(self, "No cleaned data", "Run a cleaning workflow first.")
            return
        default_name = f"cleaned_{Path(self.path).stem if self.path else 'dataset'}.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Save Cleaned CSV", default_name, "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            target = Path(path)
            temp = target.with_name(f".{target.stem}.{datetime.now().strftime('%Y%m%d%H%M%S%f')}.tmp{target.suffix}")
            self.cleaned.to_csv(temp, index=False, encoding="utf-8-sig")
            temp.replace(target)
            ToastNotification.show_toast(self, f"CSV saved to {target.name}", "success")
        except Exception as e:
            logging.exception("CSV export failed")
            QMessageBox.critical(self, "Export failed", str(e))

    def save_json(self):
        if self.cleaned is None:
            QMessageBox.information(self, "No cleaned data", "Run a cleaning workflow first.")
            return
        default_name = f"report_{Path(self.path).stem if self.path else 'dataset'}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save JSON Report", default_name, "JSON (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        report = {
            "source_file": self.path,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "profile": getattr(self, "active_profile", "Unknown"),
            "before": profile(self.original),
            "after": profile(self.cleaned),
            "quality_score_before": quality_score(self.original),
            "quality_score_after": quality_score(self.cleaned),
            "cleaning_log": self.logs.to_dict(orient="records"),
            "issues": self.issues.to_dict(orient="records") if self.issues is not None else [],
            "validation_findings": validate_dataframe(self.cleaned, self.current_validation_rules()).to_dict(orient="records"),
            "change_review": build_change_report(self.original, self.cleaned).to_dict(orient="records")
        }
        try:
            target = Path(path)
            temp = target.with_name(f".{target.stem}.{datetime.now().strftime('%Y%m%d%H%M%S%f')}.tmp{target.suffix}")
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            temp.replace(target)
            ToastNotification.show_toast(self, f"JSON report saved to {target.name}", "success")
        except Exception as e:
            logging.exception("JSON export failed")
            QMessageBox.critical(self, "Export failed", str(e))

    def save_pdf_certificate(self):
        """Export executive PDF compliance and data quality certificate."""
        if self.cleaned is None:
            QMessageBox.information(self, "No Cleaned Data", "Please clean a dataset first before exporting an audit certificate.")
            return
        
        default_name = f"Executive_Audit_{Path(self.path).stem if self.path else 'dataset'}.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Export Executive Audit Certificate", default_name, "PDF Documents (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        try:
            from advance_engine import generate_executive_pdf_report, detect_pii_columns
            pii_map = detect_pii_columns(self.cleaned)
            generate_executive_pdf_report(path, self.original, self.cleaned, self.logs, pii_map)
            ToastNotification.show_toast(self, f"Executive PDF Certificate saved: {Path(path).name}", "success")
        except Exception as e:
            logging.exception("PDF certificate export failed")
            QMessageBox.critical(self, "PDF Export Failed", str(e))

    def open_fuzzy_dialog(self):
        """Open Smart Fuzzy Clustering & Merge Studio dialog."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.fuzzy_dialog import FuzzyMergeDialog
        dlg = FuzzyMergeDialog(target_df, self)
        dlg.merges_applied.connect(self._on_fuzzy_merges_applied)
        dlg.exec()

    def _on_fuzzy_merges_applied(self, new_df, col_name, merge_map):
        self.cleaned = new_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()
        
        # Log merge action
        new_logs = []
        for variant, primary in merge_map.items():
            new_logs.append({
                "row_index": "multiple",
                "column": col_name,
                "old_value": variant,
                "new_value": primary
            })
        merge_log_df = pd.DataFrame(new_logs)
        self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), merge_log_df], ignore_index=True)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, f"Merged {len(merge_map)} typo cluster(s) in '{col_name}'", "success")
        self.go(4)  # Switch to Compare tab so user immediately sees merged clusters

    def open_masking_dialog(self):
        """Open Data Masking & PII Protection dialog."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.masking_dialog import DataMaskingDialog
        dlg = DataMaskingDialog(target_df, self)
        dlg.masking_applied.connect(self._on_masking_applied)
        dlg.exec()

    def _on_masking_applied(self, masked_df, mask_cfg):
        self.cleaned = masked_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()

        # Log masking action
        new_logs = []
        for col, method in mask_cfg.items():
            new_logs.append({
                "row_index": "all",
                "column": col,
                "old_value": "Sensitive Data",
                "new_value": f"Masked ({method})"
            })
        mask_log_df = pd.DataFrame(new_logs)
        self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), mask_log_df], ignore_index=True)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, f"Applied privacy masking to {len(mask_cfg)} column(s)", "success")
        self.go(4)  # Switch to Compare tab so user immediately sees masked cells highlighted

    def open_outlier_dialog(self):
        """Open Statistical Outlier & Anomaly Studio dialog."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.outlier_dialog import OutlierDialog
        dlg = OutlierDialog(target_df, self)
        dlg.outliers_remediated.connect(self._on_outliers_remediated)
        dlg.exec()

    def _on_outliers_remediated(self, new_df, rem_cfg):
        self.cleaned = new_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()

        new_logs = []
        for col, cfg in rem_cfg.items():
            new_logs.append({
                "row_index": "outliers",
                "column": col,
                "old_value": "Extreme Anomaly",
                "new_value": f"Remediated ({cfg.get('action')})"
            })
        if new_logs:
            self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), pd.DataFrame(new_logs)], ignore_index=True)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, f"Remediated outliers across {len(rem_cfg)} column(s)", "success")
        self.go(4)

    def open_column_transform_dialog(self):
        """Open Column Split & Merge studio dialog."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.column_transform_dialog import ColumnTransformDialog
        dlg = ColumnTransformDialog(target_df, self)
        dlg.transform_applied.connect(self._on_column_transform_applied)
        dlg.exec()

    def _on_column_transform_applied(self, new_df, desc):
        self.cleaned = new_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()

        log_entry = pd.DataFrame([{"row_index": "schema", "column": "multiple", "old_value": "--", "new_value": desc}])
        self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), log_entry], ignore_index=True)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, desc, "success")
        self.go(4)

    def open_combine_dialog(self):
        """Open Multi-File Append & Join/VLOOKUP studio dialog."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.combine_dialog import CombineDialog
        dlg = CombineDialog(target_df, self)
        dlg.combined_applied.connect(self._on_combined_applied)
        dlg.exec()

    def _on_combined_applied(self, new_df, desc):
        self.cleaned = new_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()

        log_entry = pd.DataFrame([{"row_index": "combine", "column": "multiple", "old_value": "--", "new_value": desc}])
        self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), log_entry], ignore_index=True)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, desc, "success")
        self.go(4)

    def export_cleaning_recipe(self):
        """Export current cleaning steps and settings to a reusable .recipe file."""
        settings = self.page_workflow.get_custom_settings()
        path, _ = QFileDialog.getSaveFileName(self, "Export Cleaning Recipe", "pipeline.recipe", "CleanSheet Recipe (*.recipe)")
        if not path:
            return
        if not path.lower().endswith(".recipe"):
            path += ".recipe"

        try:
            from advance_engine import export_recipe_to_file
            steps = []
            if settings.get("trim_text", True):
                steps.append({"id": "trim", "name": "Trim Whitespace", "action": "trim_spaces", "enabled": True})
            if settings.get("remove_empty", True):
                steps.append({"id": "empty", "name": "Drop Empty Rows", "action": "drop_empty_rows", "enabled": True})
            if settings.get("remove_duplicates", True):
                steps.append({"id": "dupes", "name": "Remove Duplicates", "action": "remove_duplicates", "enabled": True})
            if settings.get("normalize_columns", True):
                steps.append({"id": "norm", "name": "Standardize Headers", "action": "standardize_headers", "enabled": True})
            if settings.get("fill_missing"):
                steps.append({"id": "impute", "name": "Impute Missing", "action": "impute_missing", "params": {"method": "median_mode"}, "enabled": True})

            export_recipe_to_file(path, steps, metadata={"profile": settings.get("name", "Custom")})
            ToastNotification.show_toast(self, f"Saved recipe: {Path(path).name}", "success")
        except Exception as e:
            QMessageBox.critical(self, "Export Recipe Failed", str(e))

    def import_cleaning_recipe(self):
        """Import a .recipe file and execute its cleaning sequence on the active dataset."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload a spreadsheet first.")
            return

        path, _ = QFileDialog.getOpenFileName(self, "Import Cleaning Recipe", "", "CleanSheet Recipe (*.recipe *.json)")
        if not path:
            return

        try:
            from advance_engine import load_recipe_from_file, execute_recipe_pipeline
            steps = load_recipe_from_file(path)
            if not steps:
                QMessageBox.warning(self, "Empty Recipe", "No valid recipe steps found in file.")
                return

            cleaned_df, step_logs = execute_recipe_pipeline(target_df, steps)
            self.cleaned = cleaned_df
            if self.original is None:
                self.original = target_df.copy()

            rec_logs = []
            for s in step_logs:
                rec_logs.append({
                    "row_index": "recipe",
                    "column": "multiple",
                    "old_value": s.get("step", "Recipe Step"),
                    "new_value": s.get("details", "Executed")
                })
            self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), pd.DataFrame(rec_logs)], ignore_index=True)

            self.refresh_issues()
            self.refresh_compare()
            self.refresh_report()
            ToastNotification.show_toast(self, f"Applied recipe '{Path(path).stem}' ({len(steps)} steps)", "success")
            self.go(4)
        except Exception as e:
            QMessageBox.critical(self, "Import Recipe Failed", str(e))

    def open_standardizer_dialog(self):
        """Open Phone, Smart Date, Text Casing, and Address Pincode Standardizer Studio."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.string_standardizer_dialog import StringStandardizerDialog
        dlg = StringStandardizerDialog(target_df, self)
        dlg.standardize_applied.connect(self._on_standardized_applied)
        dlg.exec()

    def _on_standardized_applied(self, new_df, desc):
        target_df = self.cleaned if self.cleaned is not None else self.df
        self.cleaned = new_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()

        log_entry = pd.DataFrame([{"row_index": "standardize", "column": "multiple", "old_value": "--", "new_value": desc}])
        self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), log_entry], ignore_index=True)

        if hasattr(self, "lineage_tracker"):
            self.lineage_tracker.record_step("Standardize", desc, len(target_df) if target_df is not None else len(new_df), len(new_df), desc)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, desc, "success")
        self.go(4)

    def open_sql_connector_dialog(self):
        """Open Enterprise SQL Connector dialog for importing/exporting tables."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        from components.sql_connector_dialog import SQLConnectorDialog
        dlg = SQLConnectorDialog(target_df, self)
        dlg.data_imported.connect(self._on_sql_data_imported)
        dlg.exec()

    def _on_sql_data_imported(self, df: pd.DataFrame, source_name: str):
        self.df = df
        self.cleaned = None
        self.original = None
        self.logs = None
        self.issues = None
        self.path = source_name
        self.sheet_names = []
        self.current_sheet = ""

        if hasattr(self, "lineage_tracker"):
            self.lineage_tracker.record_step("Database Ingestion", f"SQL Query on {source_name}", 0, len(df), f"Imported {len(df)} rows from {source_name}")

        self.page_import.set_dataset(source_name, df, [])
        self.page_overview.update_metrics(df, source_name, "")
        self.page_workflow.set_available_sheets([], "")
        self.analyze_issues()
        self.sidebar.set_item_visible(1, True)
        self.go(1)
        ToastNotification.show_toast(self, f"Loaded {len(df):,} rows from {source_name}", "success")

    def open_deep_profile_dialog(self):
        """Open Deep Statistical Profiling & Redundancy Diagnostics Dialog."""
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            QMessageBox.information(self, "No Dataset Loaded", "Please upload or clean a spreadsheet first.")
            return

        from components.deep_profile_dialog import DeepProfileDialog
        dlg = DeepProfileDialog(target_df, self)
        dlg.remove_columns_requested.connect(self._on_drop_redundant_columns)
        dlg.exec()

    def _on_drop_redundant_columns(self, cols: list):
        target_df = self.cleaned if self.cleaned is not None else self.df
        if target_df is None:
            return
        new_df = target_df.drop(columns=cols, errors="ignore")
        self.cleaned = new_df
        if self.original is None and self.df is not None:
            self.original = self.df.copy()

        desc = f"Dropped redundant/collinear columns: {', '.join(cols)}"
        log_entry = pd.DataFrame([{"row_index": "schema", "column": "dropped", "old_value": str(cols), "new_value": "Dropped"}])
        self.logs = pd.concat([self.logs if self.logs is not None else pd.DataFrame(), log_entry], ignore_index=True)

        if hasattr(self, "lineage_tracker"):
            self.lineage_tracker.record_step("Column Pruning", "Drop Redundant Columns", len(target_df), len(new_df), desc)

        self.refresh_issues()
        self.refresh_compare()
        self.refresh_report()
        ToastNotification.show_toast(self, desc, "success")
        self.go(4)

    def open_lineage_dialog(self):
        """Open Visual Data Lineage & Governance Audit Trail Dialog."""
        if not hasattr(self, "lineage_tracker"):
            from enterprise_engine import DataLineageTracker
            self.lineage_tracker = DataLineageTracker()

        from components.lineage_dialog import LineageDialog
        dlg = LineageDialog(self.lineage_tracker, self)
        dlg.exec()

    def open_big_data_dialog(self):
        """Open Big Data CSV Out-of-Core Stream Cleaner Dialog."""
        from components.big_data_dialog import BigDataDialog
        dlg = BigDataDialog(self)
        dlg.exec()

    def _check_for_updates_silently(self):
        """Check for updates in the background without freezing the UI or interrupting offline users."""
        try:
            from updater_engine import UpdateCheckThread
            self.update_checker = UpdateCheckThread()
            self.update_checker.update_available.connect(self._on_update_detected)
            self.update_checker.start()
        except Exception:
            pass

    def _on_update_detected(self, update_info: dict):
        self.pending_update_info = update_info
        new_ver = update_info.get("version", "")
        # Show top header update pill button
        if hasattr(self, "header"):
            self.header.show_update_badge(new_ver)
        # Notify user with a friendly English toast notification
        ToastNotification.show_toast(self, f"New update available: {new_ver}! Click header to install.", "info")

    def _open_update_dialog(self):
        """Display the release notes and 1-click update dialog."""
        if not self.pending_update_info:
            return
        from components.update_dialog import UpdateNotificationDialog
        dlg = UpdateNotificationDialog(self.pending_update_info, self)
        dlg.exec()

    def show_user_manual(self):
        """Display an easy-to-read User Manual dialog explaining how to use CleanSheet in simple human language."""
        dialog = QDialog(self)
        dialog.setWindowTitle("CleanSheet · User Manual & Guide")
        dialog.resize(780, 580)
        dialog.setMinimumSize(680, 500)
        
        is_dark = ThemeManager.instance().is_dark
        # Crisp contrast palette tuned specifically for the guide popup
        if is_dark:
            dialog_bg = "#0B1220"
            header_title_col = "#F8FAFC"
            header_desc_col = "#94A3B8"
            card_bg = "#131D31"
            card_border = "#1E293B"
            card_title_col = "#60A5FA"
            card_text_col = "#E2E8F0"
            icon_accent = "#38BDF8"
        else:
            dialog_bg = "#F8FAFC"
            header_title_col = "#0F172A"
            header_desc_col = "#475569"
            card_bg = "#FFFFFF"
            card_border = "#E2E8F0"
            card_title_col = "#1D4ED8"
            card_text_col = "#1E293B"
            icon_accent = "#2563EB"
            
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {dialog_bg};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)
        
        # Header banner
        header_row = QHBoxLayout()
        header_row.setSpacing(14)
        
        ico_lbl = QLabel()
        ico_lbl.setPixmap(get_icon("sparkles", icon_accent, 28).pixmap(28, 28))
        header_row.addWidget(ico_lbl)
        
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        t_title = QLabel("CleanSheet User Manual")
        t_title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        t_title.setStyleSheet(f"color: {header_title_col}; background: transparent;")
        
        t_desc = QLabel("Simple step-by-step guide on how to clean, review, and export your spreadsheets.")
        t_desc.setFont(QFont("Segoe UI", 10))
        t_desc.setStyleSheet(f"color: {header_desc_col}; background: transparent;")
        
        title_box.addWidget(t_title)
        title_box.addWidget(t_desc)
        header_row.addLayout(title_box, 1)
        layout.addLayout(header_row)
        
        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 4, 12, 4)
        c_layout.setSpacing(12)
        
        steps = [
            (
                "Step 1: Choose or Drop Your File",
                "folder-open",
                "• Click 'Choose a Spreadsheet' on the Overview screen or drop your file into the Uploaded Data tab.\n"
                "• CleanSheet works with Excel (.xlsx, .xls) and CSV (.csv) files.\n"
                "• If your Excel workbook has multiple sheets, you can pick which sheet to view and clean from the sheet dropdown."
            ),
            (
                "Step 2: Clean Your Data",
                "play",
                "• Go to the 'Clean Data' tab.\n"
                "• Standard Mode: Click 'Start Cleaning' to let CleanSheet automatically fix column headers, remove completely blank rows, fix accidental spaces, and remove duplicate rows.\n"
                "• Custom Mode: Choose 'Custom Profile' to customize specific rules, fill strategies, and data validations.\n"
                "• Fuzzy Merge Studio: Cluster typo variations (e.g. 'Infosys Ltd' vs 'Infosys Limited') and merge into a standard canonical name.\n"
                "• Data Masking (PII): Mask or hash sensitive personal data (emails, phone numbers, tax IDs).\n"
                "• Outlier Studio: Detect and remediate numeric statistical anomalies using IQR and Z-scores.\n"
                "• Split / Merge: Split delimited columns or concatenate multiple columns.\n"
                "• Append / Join: Vertically stack files or perform VLOOKUP merges across tables."
            ),
            (
                "Step 3: Enterprise Tools (Strings, SQL, API, Profiling, Lineage & Big Data)",
                "sparkles",
                "• Phone & Date Standardizer: Standardize messy mixed phone numbers (E.164 / national) and parse mixed EU/US/ISO dates.\n"
                "• Deep Diagnostics: Column-level distributions, unique cardinality %, zero counts, and automatic collinear/duplicate column detection.\n"
                "• SQL DB & REST API Connect: Directly query SQLite, PostgreSQL, or MySQL, or fetch/flatten live REST API JSON endpoints into tables.\n"
                "• Audit Lineage: Full tamper-evident audit log with cryptographic SHA-256 data validation hashes for compliance and governance.\n"
                "• Big Data Stream: Out-of-core streaming CSV cleaner for massive files (500MB to 10GB+) without RAM crashes."
            ),
            (
                "Step 4: Review Findings & Suggestions",
                "warning",
                "• Switch to 'Issue Review' to see if anything looks unusual in your dataset.\n"
                "• CleanSheet flags empty values, repeated records, and unusual numbers (like negative salary or age > 120).\n"
                "• Click on any issue in the table to view suggestions. You can mark it as reviewed, ignore it, or fix spelling variations."
            ),
            (
                "Step 5: Compare Changes (Before vs After)",
                "compare",
                "• Open the 'Compare' tab to see your original file on the left and the cleaned file on the right side by side.\n"
                "• Changed cells are highlighted in Orange, removed rows in Red, and untouched cells remain normal.\n"
                "• You can also click 'Show Only Changed Cells' to quickly see only what was fixed."
            ),
            (
                "Step 6: Download Cleaned File, Password Protect & Audit Certificate",
                "download",
                "• Go to 'Reports & Export'.\n"
                "• Click 'Download Excel File' or 'Save as CSV' to save your new clean spreadsheet.\n"
                "• Password Encrypt Excel: Click 'Password Encrypt Excel' to lock sensitive workbooks with password security.\n"
                "• Executive PDF Certificate: Click 'Executive PDF Certificate' to generate a formal, print-ready data hygiene audit report showing quality gains, PII compliance, and full remediation trail.\n"
                "• Your original uploaded file is NEVER overwritten. It stays safe and untouched on your computer."
            ),
            (
                "Bonus: Clean Multiple Files at Once (Automation)",
                "automation",
                "• Need to clean 10 or 50 files? Open the 'Automation' tab.\n"
                "• Add all your files, choose the folder where you want to save them, and click 'Clean All Files Now'.\n"
                "• Everything is processed locally on your computer with 100% privacy."
            )
        ]
        
        for step_title, step_ico, step_text in steps:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {card_bg};
                    border: 1px solid {card_border};
                    border-radius: 10px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            card_layout.setSpacing(8)
            
            top_h = QHBoxLayout()
            top_h.setSpacing(10)
            ico = QLabel()
            ico.setPixmap(get_icon(step_ico, icon_accent, 18).pixmap(18, 18))
            ico.setStyleSheet("background: transparent;")
            
            lbl = QLabel(step_title)
            lbl.setFont(QFont("Segoe UI", 11, QFont.Bold))
            lbl.setStyleSheet(f"color: {card_title_col}; background: transparent;")
            
            top_h.addWidget(ico)
            top_h.addWidget(lbl)
            top_h.addStretch(1)
            card_layout.addLayout(top_h)
            
            txt_lbl = QLabel(step_text)
            txt_lbl.setFont(QFont("Segoe UI", 9))
            txt_lbl.setStyleSheet(f"color: {card_text_col}; line-height: 1.4; background: transparent;")
            txt_lbl.setWordWrap(True)
            card_layout.addWidget(txt_lbl)
            
            c_layout.addWidget(card)
            
        c_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        
        # Bottom close button
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_close = PrimaryButton("Got it, Close", icon_name="check")
        btn_close.setFixedHeight(38)
        btn_close.setMinimumWidth(130)
        btn_close.clicked.connect(dialog.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)
        
        dialog.exec()

    def show_audit_history(self):
        data = read_audit()
        dialog = QDialog(self)
        dialog.setWindowTitle("CleanSheet · Audit History")
        dialog.resize(1050, 520)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        
        info = QLabel(f"Local Processing Audit Log · {len(data)} record(s)")
        info.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        layout.addWidget(info)
        
        table = ModernTable()
        if not data.empty:
            table.setRowCount(len(data))
            table.setColumnCount(len(data.columns))
            table.setHorizontalHeaderLabels([str(c) for c in data.columns])
            for r in range(len(data)):
                for c in range(len(data.columns)):
                    from PySide6.QtWidgets import QTableWidgetItem
                    table.setItem(r, c, QTableWidgetItem(str(data.iloc[r, c])))
            table.resizeColumnsToContents()
        layout.addWidget(table, 1)
        
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignRight)
        dialog.exec()

    def closeEvent(self, event):
        if self.schedule_timer.isActive():
            self.schedule_timer.stop()
        event.accept()


def main():
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    
    # Set App-level Icon
    from PySide6.QtGui import QIcon
    icon_path = APP_DIR / "assets" / "icon.ico"
    if not icon_path.exists():
        icon_path = APP_DIR / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Initialize main window
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
