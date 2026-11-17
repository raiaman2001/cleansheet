# CleanSheet — Enterprise Desktop Data Cleaning & Preparation Suite

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-blue.svg)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/UI-PySide6%20(Qt6)-orange.svg)](https://wiki.qt.io/Qt_for_Python)
[![Release](https://img.shields.io/badge/Version-1.0.0-purple.svg)](https://github.com/)

**CleanSheet** is an enterprise-grade desktop data preparation, cleaning, and profiling application built with Python and PySide6 (Qt6). It allows data analysts, engineers, and business teams to clean, validate, transform, and profile messy datasets locally without cloud dependencies.

All data processing happens **100% locally on your machine**, ensuring full privacy and compliance with sensitive corporate and personal data.

---

## ✨ Key Features

- **Local & Private:** Zero cloud storage or external transmission; your data never leaves your computer.
- **Multi-Source Connectivity:**
  - Import CSV, Excel (`.xlsx`, `.xls`), and TSV files.
  - Multi-database SQL Connectors (SQLite, PostgreSQL, MySQL) & REST API / JSON flattening.
- **Data Quality & Deep Profiling:**
  - Automated health scoring and dataset diagnostics.
  - Detailed column metrics: data types, missing value percentages, distributions, and cardinality.
- **Comprehensive Cleaning Engine:**
  - Standard cleaning: whitespace trimming, casing normalization, header sanitization, deduplication.
  - Smart string standardization, phone number normalization (E.164), and heuristic mixed-date parsing.
  - Outlier detection and treatment (IQR & Z-score) with flag, cap, or remove options.
  - Advanced missing value imputation (Median, Mode, KNN, Iterative).
- **Enterprise Features:**
  - **Fuzzy Matching & Merging:** Merge and deduplicate datasets with flexible string similarity thresholds.
  - **PII Masking & Anonymization:** Redact and mask sensitive fields (names, emails, credit cards, phones).
  - **Big Data Streaming:** Out-of-core chunk-based processing for files from 500MB up to 10GB+.
  - **Excel Protection:** Password-protected encryption and read-only workbook locks on export.
  - **Data Lineage & Governance:** Complete audit trail tracking and executive compliance reports / certificates.
  - **Profiles & Automation:** Save cleaning profiles and reuse workflows for batch tasks.
  - **In-App Updater:** Built-in auto-update engine for version synchronization.

---

## 📁 Project Structure

```text
CleanSheet/
├── main.py                     # Main application entry point
├── ui.py                       # Core window coordinator & UI styling
├── clean_engine.py             # Level 1–2: Standard cleaning, profiling & summary engine
├── advance_engine.py           # Level 3–4: Validation rules, imputation & outlier treatment
├── enterprise_engine.py        # Enterprise: Fuzzy matching, PII masking, Big Data streaming & SQL
├── updater_engine.py           # In-app background update engine
├── theme.py                    # Qt style sheets, color palettes, and theme helpers
├── icons.py                    # SVG & QtAwesome icon utilities
├── version.py / version.json   # Release version metadata
├── Run_CleanSheet.bat          # Quick launcher script
│
├── pages/                      # Application view pages
│   ├── overview.py             # Dashboard, health score & dataset summary
│   ├── import_data.py          # Multi-source data loader (files, SQL, API)
│   ├── workflow.py             # Interactive step-by-step cleaning pipeline
│   ├── issue_review.py         # Visual before/after data diff review
│   ├── compare.py              # Side-by-side dataset comparison
│   ├── reports.py              # Export center & executive summary generator
│   ├── history.py              # Data lineage & audit history logger
│   ├── profiles.py             # Reusable preset configuration profiles
│   └── automation.py           # Batch processing & automation scheduler
│
├── components/                 # Reusable UI widgets & modal dialogs
│   ├── header.py & sidebar.py  # Navigation bar & layout controls
│   ├── table.py                # High-performance virtualized data table
│   ├── widgets.py              # Custom stat cards, badges & buttons
│   ├── deep_profile_dialog.py  # Detailed statistical profiling modal
│   ├── outlier_dialog.py       # Outlier detection & visual thresholds modal
│   ├── fuzzy_dialog.py         # Record linkage & fuzzy merge modal
│   ├── masking_dialog.py       # PII anonymization & redaction modal
│   ├── big_data_dialog.py      # Large file chunked streaming modal
│   ├── sql_connector_dialog.py # Database query & import modal
│   └── update_dialog.py        # In-app software update dialog
│
├── tests/                      # Automated unit & integration tests
│   └── test_core_smoke.py      # Smoke and regression tests for core engines
├── CleanSheet.spec             # PyInstaller build specification
└── CleanSheet_Installer.iss    # Inno Setup installer script
```

---

## 🚀 Getting Started

### Prerequisites

- **OS:** Windows 10 / 11 (64-bit)
- **Python:** Version 3.10 or newer

### Installation

1. Clone or download this repository:
   ```powershell
   git clone https://github.com/<your-username>/cleansheet.git
   cd cleansheet
   ```

2. Create and activate a virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   *(If on Command Prompt, run: `.\.venv\Scripts\activate.bat`)*

3. Install dependencies:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Launch the application:
   ```powershell
   python main.py
   ```
   *(Or simply double-click `Run_CleanSheet.bat`)*

---

## 🧪 Running Tests

Execute automated unit tests to verify the engines and data operations:

```powershell
python -m unittest discover -s tests -v
```

---

## 📦 Building Standalone Executable & Installer

### 1. Build Single-Folder / Executable with PyInstaller
Ensure dependencies and PyInstaller are installed:
```powershell
pyinstaller CleanSheet.spec --clean --noconfirm
```
The compiled binaries will be output into the `dist/` directory.

### 2. Build Windows Setup Installer
Compile `CleanSheet_Installer.iss` using **Inno Setup 6** to generate the production installer under `dist_installer/`.

---

## 🛡️ Safety & Data Integrity

- **Non-Destructive:** By default, CleanSheet never overwrites original source files. Cleaned files are saved with customizable suffixes or dedicated export paths.
- **Audit Trails:** Every transformation and filter applied is tracked in the local session history and exportable as a compliance certificate.
- **Safe Outlier Remediation:** Outlier detection defaults to visual flagging before any destructive clipping or row removal is performed.

---

## 📄 License & Acknowledgements

- Built with [PySide6 / Qt](https://wiki.qt.io/Qt_for_Python)
- Powered by [pandas](https://pandas.pydata.org/), [scikit-learn](https://scikit-learn.org/), and [openpyxl](https://openpyxl.readthedocs.io/)
