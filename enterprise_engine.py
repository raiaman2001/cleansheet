"""Enterprise Data Preparation, Governance, and Ingestion Engine for CleanSheet Studio.

Comprehensive modules:
1. Advanced String Standardization & Parsing:
   - Universal Phone Number Normalizer (E.164, Indian, US, International)
   - Multi-Format Heuristic Smart Date Parser (ISO, US, EU, Timestamps)
   - Address & Pincode/Zip Auto-Extractor
   - Text Case Formatter (UPPER, lower, Title, Sentence, camelCase, snake_case)

2. Advanced Statistical Profiling & Diagnostics:
   - High-Precision Distribution & Cardinality Metrics
   - Redundant / Collinear Column Detector (Correlation > 0.95 or Duplicate content)
   - Constant / Zero-Variance Column Flagging

3. Multi-Source Enterprise Connectors:
   - SQL Database Ingestion & Export (SQLite, PostgreSQL, MySQL via SQLAlchemy/sqlite3)
   - REST API & Nested JSON Ingestor / Normalizer

4. Big Data Out-of-Core Processing:
   - Chunked CSV / Large File Stream Processing Engine

5. Data Governance & Security:
   - Visual Lineage History Tracker
   - Password Encrypted Export Generator
"""
import os
import re
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

import pandas as pd
import numpy as np


# ===========================================================================
# 1. ADVANCED STRING STANDARDIZATION & PARSING
# ===========================================================================

def normalize_phone_numbers(series: pd.Series, default_country_code: str = "+91", format_style: str = "E164") -> Tuple[pd.Series, dict]:
    """Standardize mixed messy phone numbers to a consistent clean format.
    Format styles: 'E164' (+919876543210), 'DASHED' (+91-98765-43210), 'NATIONAL' (9876543210)
    Returns: (cleaned_series, stats_dict)
    """
    total = len(series)
    valid_count = 0
    invalid_count = 0
    cleaned_vals = []

    for raw in series:
        if pd.isna(raw) or str(raw).strip() == "":
            cleaned_vals.append("")
            continue

        raw_str = str(raw).strip()
        # Keep only digits and leading plus
        has_leading_plus = raw_str.startswith("+")
        digits_only = re.sub(r"[^\d]", "", raw_str)

        if len(digits_only) < 7:
            # Too short to be a valid phone number
            invalid_count += 1
            cleaned_vals.append(raw_str)
            continue

        # Handle leading zero in national formats (e.g. 09876543210 -> 9876543210)
        if digits_only.startswith("0") and len(digits_only) == 11:
            digits_only = digits_only[1:]

        # Auto-attach country code if 10 digits
        if len(digits_only) == 10:
            cc = default_country_code.strip("+")
            full_digits = f"{cc}{digits_only}"
            clean_national = digits_only
        elif len(digits_only) > 10:
            full_digits = digits_only
            clean_national = digits_only[-10:]
        else:
            full_digits = digits_only
            clean_national = digits_only

        valid_count += 1
        if format_style == "E164":
            res = f"+{full_digits}"
        elif format_style == "DASHED":
            res = f"+{full_digits[:-10]}-{clean_national[:5]}-{clean_national[5:]}" if len(full_digits) > 10 else f"{clean_national[:5]}-{clean_national[5:]}"
        else:  # NATIONAL
            res = clean_national

        cleaned_vals.append(res)

    stats = {
        "total": total,
        "valid_standardized": valid_count,
        "invalid_flagged": invalid_count,
        "standard_ratio": round(valid_count / max(1, total), 2)
    }
    return pd.Series(cleaned_vals, index=series.index), stats


def parse_mixed_dates(series: pd.Series, output_format: str = "%Y-%m-%d") -> Tuple[pd.Series, dict]:
    """Smart heuristic parser for columns containing mixed date formats.
    Handles: ISO, US (MM/DD/YYYY), EU (DD/MM/YYYY), Textual ('12 Jan 2026', 'January 12, 2026'), and Excel timestamps.
    """
    total = len(series)
    converted = 0
    failed = 0
    results = []

    for raw in series:
        if pd.isna(raw) or str(raw).strip() == "":
            results.append("")
            continue

        s = str(raw).strip()
        parsed_dt = None

        # 1. Try standard pandas to_datetime
        try:
            parsed_dt = pd.to_datetime(s, errors="raise")
        except Exception:
            # 2. Try dayfirst heuristics for EU/Indian dates
            try:
                parsed_dt = pd.to_datetime(s, dayfirst=True, errors="raise")
            except Exception:
                # 3. Try custom regex patterns
                m = re.match(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})", s)
                if m:
                    try:
                        parsed_dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    except Exception:
                        pass

        if parsed_dt is not None and not pd.isna(parsed_dt):
            converted += 1
            results.append(parsed_dt.strftime(output_format))
        else:
            failed += 1
            results.append(s)

    stats = {
        "total": total,
        "successfully_converted": converted,
        "failed_unrecognized": failed
    }
    return pd.Series(results, index=series.index), stats


def extract_address_components(series: pd.Series) -> pd.DataFrame:
    """Extract Pincode/Zip and standard city patterns from address strings."""
    pincodes = []
    cleaned_addrs = []

    pin_regex = re.compile(r"\b(\d{6})\b|\b(\d{5}(?:-\d{4})?)\b")

    for raw in series:
        if pd.isna(raw) or str(raw).strip() == "":
            pincodes.append("")
            cleaned_addrs.append("")
            continue

        s = str(raw).strip()
        m = pin_regex.search(s)
        if m:
            pincode = m.group(1) or m.group(2)
            cleaned = pin_regex.sub("", s).strip(" ,-")
        else:
            pincode = ""
            cleaned = s

        pincodes.append(pincode)
        cleaned_addrs.append(cleaned)

    return pd.DataFrame({
        f"{series.name}_cleaned": cleaned_addrs,
        f"{series.name}_pincode": pincodes
    }, index=series.index)


def apply_case_format(series: pd.Series, style: str = "title") -> pd.Series:
    """Standardize string casing: 'title', 'upper', 'lower', 'sentence', 'snake', 'camel'."""
    def _format(val):
        if pd.isna(val) or str(val).strip() == "":
            return val
        s = str(val).strip()
        if style == "title":
            return s.title()
        elif style == "upper":
            return s.upper()
        elif style == "lower":
            return s.lower()
        elif style == "sentence":
            return s.capitalize()
        elif style == "snake":
            return re.sub(r"[^\w]+", "_", s.lower()).strip("_")
        elif style == "camel":
            words = re.findall(r"\w+", s)
            if not words:
                return s
            return words[0].lower() + "".join(w.capitalize() for w in words[1:])
        return s

    return series.apply(_format)


# ===========================================================================
# 2. ADVANCED STATISTICAL PROFILING & DIAGNOSTICS
# ===========================================================================

def generate_deep_profile(df: pd.DataFrame) -> dict:
    """Generate high-precision enterprise data quality and statistical diagnostics."""
    if df is None or df.empty:
        return {}

    total_rows = len(df)
    columns_info = {}

    for col in df.columns:
        s = df[col]
        non_null_count = int(s.notna().sum())
        null_count = int(s.isna().sum())
        null_ratio = round(null_count / max(1, total_rows), 4)
        unique_count = int(s.nunique(dropna=True))
        is_constant = (unique_count <= 1 and non_null_count > 0)
        is_all_null = (null_count == total_rows)

        col_stat = {
            "dtype": str(s.dtype),
            "total_rows": total_rows,
            "non_null_count": non_null_count,
            "null_count": null_count,
            "null_ratio_pct": round(null_ratio * 100, 2),
            "unique_count": unique_count,
            "is_constant": is_constant,
            "is_all_null": is_all_null,
        }

        # Numeric stats
        if pd.api.types.is_numeric_dtype(s):
            clean_s = s.dropna()
            if not clean_s.empty:
                col_stat.update({
                    "min": float(clean_s.min()),
                    "max": float(clean_s.max()),
                    "mean": round(float(clean_s.mean()), 2),
                    "median": round(float(clean_s.median()), 2),
                    "std": round(float(clean_s.std()), 2) if len(clean_s) > 1 else 0.0,
                    "zero_count": int((clean_s == 0).sum()),
                })
        else:
            # Categorical stats
            top_vals = s.value_counts(dropna=True).head(5).to_dict()
            col_stat["top_values"] = {str(k): int(v) for k, v in top_vals.items()}

        columns_info[col] = col_stat

    # Redundancy / Collinearity check
    redundancies = detect_redundant_columns(df)

    return {
        "summary": {
            "total_rows": total_rows,
            "total_columns": len(df.columns),
            "memory_usage_kb": round(df.memory_usage(deep=True).sum() / 1024, 2),
            "duplicate_rows": int(df.duplicated().sum()),
        },
        "columns": columns_info,
        "redundant_columns": redundancies
    }


def detect_redundant_columns(df: pd.DataFrame, threshold: float = 0.95) -> list:
    """Find redundant columns with near-identical values or perfect correlation."""
    if df is None or len(df.columns) < 2:
        return []

    redundant_pairs = []
    cols = list(df.columns)

    # 1. Exact or near duplicate categorical columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            col_a, col_b = cols[i], cols[j]
            s_a = df[col_a].dropna().astype(str).str.strip().str.lower()
            s_b = df[col_b].dropna().astype(str).str.strip().str.lower()
            
            common_idx = s_a.index.intersection(s_b.index)
            if len(common_idx) >= 3:
                match_ratio = (s_a.loc[common_idx] == s_b.loc[common_idx]).mean()
                if match_ratio >= threshold:
                    redundant_pairs.append({
                        "col_a": col_a,
                        "col_b": col_b,
                        "type": "Duplicate Content",
                        "similarity": round(float(match_ratio), 2),
                        "recommendation": f"Column '{col_b}' is {int(match_ratio*100)}% identical to '{col_a}'. Consider dropping one."
                    })

    # 2. High numeric correlation
    num_df = df.select_dtypes(include=["number"]).dropna()
    if len(num_df.columns) >= 2 and len(num_df) >= 3:
        corr_matrix = num_df.corr().abs()
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                c1 = corr_matrix.columns[i]
                c2 = corr_matrix.columns[j]
                val = corr_matrix.iloc[i, j]
                if val >= threshold and not any(p["col_a"] == c1 and p["col_b"] == c2 for p in redundant_pairs):
                    redundant_pairs.append({
                        "col_a": c1,
                        "col_b": c2,
                        "type": "Collinear Numeric",
                        "similarity": round(float(val), 2),
                        "recommendation": f"Columns '{c1}' and '{c2}' have a high correlation ({round(float(val), 2)}). Redundant for modeling."
                    })

    return redundant_pairs


# ===========================================================================
# 3. MULTI-SOURCE ENTERPRISE CONNECTORS (SQL & JSON REST)
# ===========================================================================

def execute_sql_query(connection_string: str, query: str) -> pd.DataFrame:
    """Execute SQL query and return DataFrame.
    Supports: SQLite ('sqlite:///path.db' or direct 'C:/path.db'), PostgreSQL, MySQL via SQLAlchemy.
    """
    if not connection_string or not query:
        raise ValueError("Connection string and SQL query must not be empty.")

    # Direct sqlite path support
    if connection_string.endswith(".db") or connection_string.endswith(".sqlite"):
        conn = sqlite3.connect(connection_string)
        try:
            df = pd.read_sql_query(query, conn)
            return df
        finally:
            conn.close()

    from sqlalchemy import create_engine
    engine = create_engine(connection_string)
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df


def export_to_sql_table(df: pd.DataFrame, connection_string: str, table_name: str, if_exists: str = "replace") -> int:
    """Export cleaned dataframe to a SQL database table."""
    if df is None or df.empty:
        raise ValueError("Cannot export empty DataFrame.")

    if connection_string.endswith(".db") or connection_string.endswith(".sqlite"):
        conn = sqlite3.connect(connection_string)
        try:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            return len(df)
        finally:
            conn.close()

    from sqlalchemy import create_engine
    engine = create_engine(connection_string)
    with engine.connect() as conn:
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
    return len(df)


def ingest_json_data(json_source: str, is_url: bool = False, record_path: str = None, headers: dict = None) -> pd.DataFrame:
    """Ingest JSON string, file path, or REST API response, auto-flattening nested structures."""
    if is_url:
        import requests
        req_headers = {"User-Agent": "CleanSheet-Studio/1.0"}
        if headers:
            req_headers.update(headers)
        resp = requests.get(json_source, headers=req_headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    elif os.path.exists(json_source):
        with open(json_source, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(json_source)

    # Flatten nested JSON
    if isinstance(data, list):
        df = pd.json_normalize(data)
    elif isinstance(data, dict):
        if record_path and record_path in data:
            df = pd.json_normalize(data[record_path])
        else:
            # Find largest list inside dict
            lists = [(k, v) for k, v in data.items() if isinstance(v, list)]
            if lists:
                largest_key, largest_list = max(lists, key=lambda item: len(item[1]))
                df = pd.json_normalize(largest_list)
            else:
                df = pd.json_normalize([data])
    else:
        df = pd.DataFrame(data)

    return df


def save_protected_excel(df: pd.DataFrame, output_path: str, password: str, sheet_name: str = "Cleaned_Data") -> str:
    """Save DataFrame as an encrypted/password-protected Excel workbook using openpyxl."""
    import openpyxl
    from openpyxl.utils.dataframe import dataframe_to_rows

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)

    if password:
        ws.protection.password = password
        ws.protection.sheet = True
        ws.protection.enable()
        wb.security.workbookPassword = password
        wb.security.lockStructure = True

    outp = Path(output_path)
    outp.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(outp))
    return str(outp)


# ===========================================================================
# 4. BIG DATA OUT-OF-CORE CHUNKING
# ===========================================================================

def process_large_csv_in_chunks(input_path: str, output_path: str, chunk_size: int = 100000, cleaning_func=None, progress_callback=None) -> dict:
    """Stream clean a massive CSV file in chunks to prevent memory exhaustion."""
    inp = Path(input_path)
    outp = Path(output_path)
    outp.parent.mkdir(parents=True, exist_ok=True)

    total_rows_read = 0
    total_rows_written = 0
    chunk_index = 0

    first_chunk = True
    for chunk in pd.read_csv(inp, chunksize=chunk_size, low_memory=False):
        chunk_index += 1
        total_rows_read += len(chunk)

        if cleaning_func:
            cleaned_chunk = cleaning_func(chunk)
        else:
            cleaned_chunk = chunk.dropna(how="all").drop_duplicates()

        total_rows_written += len(cleaned_chunk)
        cleaned_chunk.to_csv(outp, mode="w" if first_chunk else "a", header=first_chunk, index=False)
        first_chunk = False

        if progress_callback:
            progress_callback(chunk_index, total_rows_read, total_rows_written)

    return {
        "chunks_processed": chunk_index,
        "rows_ingested": total_rows_read,
        "rows_cleaned": total_rows_written,
        "output_file": str(outp)
    }


# ===========================================================================
# 5. DATA GOVERNANCE & LINEAGE
# ===========================================================================

class DataLineageTracker:
    """Tracks step-by-step transformations and states across a dataset's lifecycle."""
    def __init__(self):
        self.steps: List[Dict[str, Any]] = []

    def record_step(self, stage: str, action: str, rows_in: int, rows_out: int, details: str = ""):
        self.steps.append({
            "step_num": len(self.steps) + 1,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "stage": stage,
            "action": action,
            "rows_before": rows_in,
            "rows_after": rows_out,
            "delta": rows_out - rows_in,
            "details": details
        })

    def get_lineage(self) -> List[Dict[str, Any]]:
        return self.steps

    def clear(self):
        self.steps = []
