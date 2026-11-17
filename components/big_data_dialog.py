"""Out-of-Core Big Data CSV Streaming Dialog for CleanSheet.
Allows processing multi-gigabyte files in chunked streams without RAM exhaustion.
"""
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QProgressBar, QFileDialog, QMessageBox, QWidget, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from theme import ThemeManager
from enterprise_engine import process_large_csv_in_chunks


class BigDataStreamThread(QThread):
    progress = Signal(int, int, int)  # (chunk_idx, rows_read, rows_written)
    finished_success = Signal(dict)
    failed = Signal(str)

    def __init__(self, input_path: str, output_path: str, chunk_size: int):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.chunk_size = chunk_size

    def run(self):
        try:
            def cb(idx, read_cnt, write_cnt):
                self.progress.emit(idx, read_cnt, write_cnt)

            res = process_large_csv_in_chunks(
                self.input_path,
                self.output_path,
                chunk_size=self.chunk_size,
                progress_callback=cb
            )
            self.finished_success.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class BigDataDialog(QDialog):
    """Big Data Stream Cleaning Studio for 100MB - 10GB+ CSV files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Big Data Stream Cleaner — Out-of-Core Engine")
        self.resize(650, 440)
        self.worker = None
        self._setup_ui()

    def _setup_ui(self):
        c = ThemeManager.instance().colors
        self.setStyleSheet(f"""
            QDialog {{ background: {c.bg}; }}
            QLabel {{ color: {c.text_primary}; font-family: 'Segoe UI'; }}
            QLineEdit, QSpinBox {{
                background: {c.surface};
                color: {c.text_primary};
                border: 1px solid {c.border};
                border-radius: 6px;
                padding: 7px 10px;
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
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        # Header
        h_lbl = QLabel("Out-of-Core Big Data CSV Streaming Studio")
        h_lbl.setFont(QFont("Segoe UI", 14, QFont.Bold))
        h_lbl.setStyleSheet(f"color: {c.accent};")
        layout.addWidget(h_lbl)

        d_lbl = QLabel(
            "Safely clean massive CSV files (500MB to 10GB+) without memory crashes. "
            "Data is read, cleaned (blank removal, deduplication, whitespace stripping), and streamed to disk."
        )
        d_lbl.setWordWrap(True)
        d_lbl.setStyleSheet(f"color: {c.text_secondary}; font-size: 12px;")
        layout.addWidget(d_lbl)

        # File inputs card
        card = QFrame()
        card.setStyleSheet(f"background: {c.surface}; border: 1px solid {c.border}; border-radius: 8px; padding: 14px;")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(10)

        # Input File
        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Input CSV File:"))
        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText("Select large source CSV file...")
        btn_in_browse = QPushButton("Browse...")
        btn_in_browse.clicked.connect(self._browse_input)
        in_row.addWidget(self.txt_input, 1)
        in_row.addWidget(btn_in_browse)
        c_layout.addLayout(in_row)

        # Output File
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output Cleaned CSV:"))
        self.txt_output = QLineEdit()
        self.txt_output.setPlaceholderText("Select output file destination...")
        btn_out_browse = QPushButton("Browse...")
        btn_out_browse.clicked.connect(self._browse_output)
        out_row.addWidget(self.txt_output, 1)
        out_row.addWidget(btn_out_browse)
        c_layout.addLayout(out_row)

        # Chunk Size
        chunk_row = QHBoxLayout()
        chunk_row.addWidget(QLabel("Chunk Stream Size (Rows per batch):"))
        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(10000, 1000000)
        self.spin_chunk.setSingleStep(25000)
        self.spin_chunk.setValue(100000)
        chunk_row.addWidget(self.spin_chunk)
        chunk_row.addStretch(1)
        c_layout.addLayout(chunk_row)

        layout.addWidget(card)

        # Progress bar & status
        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setVisible(False)
        layout.addWidget(self.prog_bar)

        self.lbl_status = QLabel("Ready to stream process.")
        self.lbl_status.setStyleSheet("color: #64748B; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.lbl_status)

        # Action Buttons
        btn_box = QHBoxLayout()
        self.btn_run = QPushButton("⚡ Start Big Data Stream Cleaning")
        self.btn_run.setFixedHeight(38)
        self.btn_run.setStyleSheet("background: #2563EB; color: white; font-weight: bold; border-radius: 6px; padding: 6px 18px;")
        self.btn_run.clicked.connect(self._start_stream)
        btn_box.addWidget(self.btn_run)

        btn_box.addStretch(1)

        btn_close = QPushButton("Close")
        btn_close.setFixedHeight(38)
        btn_close.setStyleSheet(f"background: {c.surface_alt}; color: {c.text_primary}; border: 1px solid {c.border}; border-radius: 6px; padding: 6px 18px;")
        btn_close.clicked.connect(self.reject)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Massive CSV File", "", "CSV Files (*.csv);;All Files (*.*)")
        if path:
            self.txt_input.setText(path)
            p = Path(path)
            default_out = str(p.parent / f"cleaned_stream_{p.name}")
            self.txt_output.setText(default_out)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Select Cleaned Output CSV", "cleaned_stream.csv", "CSV Files (*.csv)")
        if path:
            self.txt_output.setText(path)

    def _start_stream(self):
        inp = self.txt_input.text().strip()
        outp = self.txt_output.text().strip()
        chunk_size = self.spin_chunk.value()

        if not inp or not Path(inp).exists():
            QMessageBox.warning(self, "File Not Found", "Please choose a valid existing input CSV file.")
            return
        if not outp:
            QMessageBox.warning(self, "Missing Output", "Please choose a valid output file path.")
            return

        self.btn_run.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.lbl_status.setText("Streaming and cleaning chunks...")

        self.worker = BigDataStreamThread(inp, outp, chunk_size)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_success.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, idx: int, read_cnt: int, write_cnt: int):
        self.lbl_status.setText(f"Chunk #{idx:,} processed · Ingested {read_cnt:,} rows → Saved {write_cnt:,} clean rows")

    def _on_finished(self, res: dict):
        self.prog_bar.setVisible(False)
        self.btn_run.setEnabled(True)
        msg = f"✓ Big Data Stream Complete!\n\nChunks Processed: {res['chunks_processed']:,}\nRows Ingested: {res['rows_ingested']:,}\nRows Saved: {res['rows_cleaned']:,}\n\nSaved to: {res['output_file']}"
        self.lbl_status.setText(f"✓ Complete! Saved {res['rows_cleaned']:,} clean rows.")
        QMessageBox.information(self, "Streaming Cleaning Succeeded", msg)

    def _on_failed(self, err_msg: str):
        self.prog_bar.setVisible(False)
        self.btn_run.setEnabled(True)
        self.lbl_status.setText(f"❌ Error: {err_msg[:60]}")
        QMessageBox.critical(self, "Streaming Cleaning Failed", f"An error occurred while streaming:\n{err_msg}")

