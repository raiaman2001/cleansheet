"""Modern In-App Update Notification Modal Dialog for CleanSheet.
Presents available version, changelog, progress bar, and 1-click install button.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from theme import ThemeManager
from icons import get_icon
from updater_engine import UpdateDownloadThread, apply_update_and_restart


class UpdateNotificationDialog(QDialog):
    """Modal dialog displaying new software release notes and download progress."""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Software Update Available — CleanSheet")
        self.resize(540, 420)
        self.update_info = update_info
        self.downloader = None
        self._setup_ui()

    def _setup_ui(self):
        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background: {c.bg}; }}
            QLabel {{ color: {c.text_primary}; font-family: 'Segoe UI'; }}
            QTextEdit {{
                background: {c.surface};
                color: {c.text_primary};
                border: 1px solid {c.border};
                border-radius: 8px;
                padding: 10px;
                font-family: 'Segoe UI';
                font-size: 12px;
            }}
            QProgressBar {{
                border: 1px solid {c.border};
                border-radius: 6px;
                text-align: center;
                background: {c.surface_alt};
                color: {c.text_primary};
                height: 22px;
                font-weight: 600;
            }}
            QProgressBar::chunk {{
                background-color: {c.accent};
                border-radius: 5px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        # Header with icon
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        ico_lbl = QLabel()
        ico_lbl.setPixmap(get_icon("sparkles", "#2563EB", 32).pixmap(32, 32))
        header_row.addWidget(ico_lbl)

        title_box = QVBoxLayout()
        new_ver = self.update_info.get("version", "Latest")
        curr_ver = self.update_info.get("current_version", "")
        h_title = QLabel(f"New Version Available: {new_ver}")
        h_title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        h_title.setStyleSheet(f"color: {c.accent};")

        sub_desc = QLabel(f"You are currently using CleanSheet v{curr_ver}. Upgrade now to get the latest features.")
        sub_desc.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        title_box.addWidget(h_title)
        title_box.addWidget(sub_desc)
        header_row.addLayout(title_box, 1)
        layout.addLayout(header_row)

        # Release Notes / Changelog Box
        layout.addWidget(QLabel("What's New in this Update:"))
        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        changelog_text = self.update_info.get("changelog", "")
        if isinstance(changelog_text, list):
            changelog_text = "\n".join([f"• {line}" for line in changelog_text])
        self.txt_notes.setPlainText(changelog_text)
        layout.addWidget(self.txt_notes, 1)

        # Download Progress Bar (Hidden until download starts)
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(self.lbl_status)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_later = QPushButton("Remind Me Later")
        self.btn_later.setFixedHeight(36)
        self.btn_later.setStyleSheet(f"background: {c.surface_alt}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; padding: 6px 16px;")
        self.btn_later.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_later)

        btn_box.addStretch(1)

        self.btn_update = QPushButton("⚡ Update & Restart Now")
        self.btn_update.setFixedHeight(36)
        self.btn_update.setStyleSheet("background: #2563EB; color: white; font-weight: bold; border-radius: 6px; padding: 6px 20px;")
        self.btn_update.clicked.connect(self._start_download)
        btn_box.addWidget(self.btn_update)

        layout.addLayout(btn_box)

    def _start_download(self):
        url = self.update_info.get("download_url", "").strip()
        if not url:
            QMessageBox.information(
                self, "Manual Download Required",
                "Direct download link is not configured yet. Please visit the official repository to download the latest release."
            )
            return

        self.btn_update.setEnabled(False)
        self.btn_later.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.lbl_status.setText("Connecting and downloading update package...")

        self.downloader = UpdateDownloadThread(url)
        self.downloader.progress.connect(self._on_download_progress)
        self.downloader.download_complete.connect(self._on_download_complete)
        self.downloader.download_failed.connect(self._on_download_failed)
        self.downloader.start()

    def _on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            pct = int((downloaded / total) * 100)
            self.prog_bar.setValue(pct)
            mb_down = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024)
            self.lbl_status.setText(f"Downloading: {mb_down:.1f} MB / {mb_tot:.1f} MB ({pct}%)")
        else:
            mb_down = downloaded / (1024 * 1024)
            self.lbl_status.setText(f"Downloading: {mb_down:.1f} MB...")

    def _on_download_complete(self, new_exe_path: str):
        self.lbl_status.setText("✓ Download complete. Preparing to restart application...")
        QMessageBox.information(
            self, "Update Ready",
            "Update has been downloaded successfully!\n\nCleanSheet will now restart with the new version."
        )
        apply_update_and_restart(new_exe_path)

    def _on_download_failed(self, err_msg: str):
        self.btn_update.setEnabled(True)
        self.btn_later.setEnabled(True)
        self.prog_bar.setVisible(False)
        self.lbl_status.setText(f"❌ Download failed: {err_msg[:60]}")
        QMessageBox.critical(self, "Download Failed", f"Could not complete update download:\n{err_msg}")

