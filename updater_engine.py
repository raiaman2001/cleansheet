"""Auto-Updater Engine for CleanSheet Desktop Studio.
Performs background version check, non-blocking download, and seamless hot-replacement
upon application restart on Windows.
"""
import sys
import os
import json
import logging
import subprocess
from pathlib import Path
from PySide6.QtCore import QThread, Signal
import requests

from version import APP_VERSION, UPDATE_CHECK_URL


def parse_semver(ver_str: str) -> tuple:
    """Parse version string like 'v2.1.0' into numeric tuple (2, 1, 0)."""
    clean = ver_str.strip().lstrip("vV")
    parts = []
    for p in clean.split("."):
        try:
            parts.append(int(p.split("-")[0]))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


class UpdateCheckThread(QThread):
    """Background non-blocking thread to check for new version release."""
    update_available = Signal(dict)   # {version, download_url, changelog, title}
    check_finished = Signal(bool)

    def __init__(self, check_url: str = UPDATE_CHECK_URL):
        super().__init__()
        self.check_url = check_url

    def run(self):
        try:
            resp = requests.get(self.check_url, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                latest_ver_str = data.get("version", "0.0.0")
                if parse_semver(latest_ver_str) > parse_semver(APP_VERSION):
                    self.update_available.emit({
                        "version": latest_ver_str,
                        "current_version": APP_VERSION,
                        "download_url": data.get("download_url", ""),
                        "changelog": data.get("changelog", "Bug fixes and performance improvements."),
                        "release_notes": data.get("release_notes", []),
                        "mandatory": data.get("mandatory", False)
                    })
                    self.check_finished.emit(True)
                    return
        except Exception as e:
            logging.debug("Update check skipped (offline or server unreachable): %s", e)
        self.check_finished.emit(False)


class UpdateDownloadThread(QThread):
    """Downloads updated executable file with real-time percentage progress."""
    progress = Signal(int, int)       # (downloaded_bytes, total_bytes)
    download_complete = Signal(str)   # path to downloaded file
    download_failed = Signal(str)     # error message

    def __init__(self, download_url: str, target_path: str = None):
        super().__init__()
        self.download_url = download_url
        self.target_path = target_path or str(Path.home() / ".cleansheet" / "updates" / "CleanSheet_New.exe")

    def run(self):
        try:
            target_p = Path(self.target_path)
            target_p.parent.mkdir(parents=True, exist_ok=True)

            resp = requests.get(self.download_url, stream=True, timeout=20)
            resp.raise_for_status()

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(target_p, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total_size)

            self.download_complete.emit(str(target_p))
        except Exception as e:
            self.download_failed.emit(str(e))


def apply_update_and_restart(new_installer_path: str):
    """Silently run the new installer and relaunch CleanSheet without wizard dialogs,
    just like VS Code / Antigravity background updates.
    """
    current_exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
    current_pid = os.getpid()

    update_script = Path.home() / ".cleansheet" / "updates" / "apply_update.bat"
    update_script.parent.mkdir(parents=True, exist_ok=True)

    # Windows batch updater script:
    # 1. Wait for CleanSheet to cleanly release its files
    # 2. Run installer in /VERYSILENT mode with all dialogs suppressed
    # 3. Relaunch CleanSheet and clean up
    bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
:wait_loop
tasklist /fi "pid eq {current_pid}" 2>nul | find "{current_pid}" > nul
if %ERRORLEVEL% equ 0 (
    timeout /t 1 /nobreak > nul
    goto wait_loop
)

:: Run installer silently in background
"{new_installer_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART

:: Small buffer to ensure extraction completes
timeout /t 2 /nobreak > nul

:: Relaunch the application
start "" "{current_exe}"

:: Cleanup batch file
del "%~f0"
exit
"""
    with open(update_script, "w", encoding="utf-8") as f:
        f.write(bat_content)

    # Launch batch script detached and terminate running app cleanly
    subprocess.Popen(str(update_script), shell=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    sys.exit(0)

