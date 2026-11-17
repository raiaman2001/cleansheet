"""CleanSheet Core Engine: Unified data profiling, cleaning, validation, audit, and reporting.

Combines all data preparation, cleaning, missing-value imputation, outlier handling,
schema validation, change auditing, and Excel reporting in a single unified module.
"""
from datetime import datetime
import difflib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import traceback

import pandas as pd


# ---------------------------------------------------------------------------
# 1. Column Normalization, Profiling & Quality Scoring
# ---------------------------------------------------------------------------

def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names to clean snake_case identifiers."""
    names = []
    for c in df.columns:
        n = re.sub(r"_+", "_", re.sub(r"[^\w]", "_", re.sub(r"\s+", "_", str(c).strip().lower()))).strip("_") or "unnamed_column"
        names.append(n)
    seen = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    x = df.copy()
    x.columns = out
    return x


def profile(df: pd.DataFrame) -> dict:
    """Generate high-level dataset health profile."""
    return {
        "Rows": len(df),
        "Columns": len(df.columns),
        "Missing cells": int(df.isna().sum().sum()),
        "Duplicate rows": int(df.duplicated().sum()) if len(df) else 0,
        "Empty rows": int(df.isna().all(axis=1).sum()) if len(df) else 0,
    }


def quality_score(df: pd.DataFrame) -> float:
    """Transparent heuristic quality score from 0 to 100."""
    if df is None or len(df.columns) == 0 or len(df) == 0:
        return 0.0
    total_cells = max(1, len(df) * len(df.columns))
    missing_rate = float(df.isna().sum().sum()) / total_cells
    duplicate_rate = float(df.duplicated().sum()) / max(1, len(df))
    empty_rate = float(df.isna().all(axis=1).sum()) / max(1, len(df))
    invalid_rate = 0.0
    checks = 0
    invalid = 0
    for c in df.columns:
        s = df[c]
        name = str(c).lower()
        if pd.api.types.is_numeric_dtype(s):
            if "age" in name:
                checks += len(s.dropna())
                invalid += int(((s.dropna() < 0) | (s.dropna() > 120)).sum())
            elif any(k in name for k in ["salary", "price", "amount", "quantity", "qty", "count", "cost", "revenue", "balance", "income"]):
                checks += len(s.dropna())
                invalid += int((s.dropna() < 0).sum())
            if "percent" in name or "percentage" in name or name.endswith("_pct"):
                checks += len(s.dropna())
                invalid += int(((s.dropna() < 0) | (s.dropna() > 100)).sum())
        if any(k in name for k in ["email", "e_mail"]) and len(s.dropna()):
            vals = s.dropna().astype(str)
            checks += len(vals)
            invalid += int((~vals.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")).sum())
    if checks:
        invalid_rate = min(1.0, invalid / checks)
    score = 100 * (1 - min(1, 0.45 * missing_rate + 0.25 * duplicate_rate + 0.15 * empty_rate + 0.15 * invalid_rate))
    return round(max(0.0, score), 1)


def read_data(path, sheet=0) -> pd.DataFrame:
    """Read CSV, XLSX, or XLS files reliably."""
    ext = Path(path).suffix.lower()
    if ext == ".csv":
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return pd.read_csv(path, encoding=enc, sep=None, engine="python")
            except Exception:
                pass
        raise ValueError("CSV could not be read. Check delimiter or encoding.")
    if ext == ".xlsx":
        return pd.read_excel(path, engine="openpyxl", sheet_name=sheet)
    if ext == ".xls":
        return pd.read_excel(path, sheet_name=sheet)
    raise ValueError("Choose a CSV, XLSX, or XLS file.")


def column_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Column-level summary table."""
    rows = []
    for c in df.columns:
        s = df[c]
        rows.append({
            "Column": str(c),
            "Data type": str(s.dtype),
            "Missing values": int(s.isna().sum()),
            "Unique values": int(s.nunique(dropna=True)),
            "Missing %": round(float(s.isna().mean() * 100), 2) if len(s) else 0,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. Issue Detection & Schema Validation
# ---------------------------------------------------------------------------

def issue_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Scan dataset for quality findings, anomalies, and potential issues."""
    rows = []
    if df is None:
        return pd.DataFrame(columns=["Category", "Column", "Count", "Details", "Suggested action", "Review status"])

    for c in df.columns:
        s = df[c]
        n = int(s.isna().sum())
        if n:
            rows.append({
                "Category": "Missing values",
                "Column": str(c),
                "Count": n,
                "Details": f"{n} blank value(s)",
                "Suggested action": "Review or fill missing values",
            })

    dups = int(df.duplicated().sum()) if len(df) else 0
    if dups:
        rows.append({
            "Category": "Duplicate records",
            "Column": "All columns",
            "Count": dups,
            "Details": "Exact duplicate rows found",
            "Suggested action": "Keep first occurrence",
        })

    for c in df.columns:
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) and len(s.dropna()) >= 8:
            clean = s.dropna()
            q1 = clean.quantile(.25)
            q3 = clean.quantile(.75)
            iqr = q3 - q1
            if pd.notna(iqr) and iqr > 0:
                n = int(((clean < q1 - 1.5 * iqr) | (clean > q3 + 1.5 * iqr)).sum())
                if n:
                    rows.append({
                        "Category": "Potential outliers",
                        "Column": str(c),
                        "Count": n,
                        "Details": "Values outside the 1.5×IQR range; these are flags, not automatic errors",
                        "Suggested action": "Inspect before changing values",
                    })

        name = str(c).lower()
        if pd.api.types.is_numeric_dtype(s):
            bad = None
            rule = None
            if "age" in name:
                bad = (s < 0) | (s > 120)
                rule = "Age values below 0 or above 120"
            elif any(k in name for k in ["salary", "price", "amount", "quantity", "qty", "count", "cost", "revenue", "balance", "income"]):
                bad = s < 0
                rule = "Negative values in a commonly non-negative field"
            elif "percent" in name or "percentage" in name or name.endswith("_pct"):
                bad = (s < 0) | (s > 100)
                rule = "Percentage outside 0–100"
            if bad is not None:
                n = int(bad.fillna(False).sum())
                if n:
                    rows.append({
                        "Category": "Business-rule warnings",
                        "Column": str(c),
                        "Count": n,
                        "Details": rule,
                        "Suggested action": "Validate against business rules and source records",
                    })

        # Fuzzy matching suggestions for text columns
        if not pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) <= 50 and len(s.dropna()) >= 5:
            values = s.dropna().astype(str).str.strip()
            unique = list(dict.fromkeys(v for v in values if v))
            counts = values.value_counts().to_dict()
            for i, val in enumerate(unique):
                for other in unique[i + 1:]:
                    if val.casefold() == other.casefold():
                        continue
                    ratio = difflib.SequenceMatcher(None, val.casefold(), other.casefold()).ratio()
                    if ratio >= 0.70:
                        popular, less_popular = (val, other) if counts.get(val, 0) >= counts.get(other, 0) else (other, val)
                        rows.append({
                            "Category": "Inconsistent categories",
                            "Column": str(c),
                            "Count": counts.get(less_popular, 0),
                            "Details": f"'{less_popular}' is similar to '{popular}' ({int(ratio * 100)}% match)",
                            "Suggested action": f"Standardize '{less_popular}' to '{popular}'",
                        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out["Review status"] = "Pending"
    else:
        out = pd.DataFrame(columns=["Category", "Column", "Count", "Details", "Suggested action", "Review status"])
    return out


def validate_dataframe(df: pd.DataFrame, rules: list) -> pd.DataFrame:
    """Validate dataframe rows against custom schema rules."""
    cols = ["Row number", "Column", "Rule", "Value", "Issue"]
    if df is None or not rules:
        return pd.DataFrame(columns=cols)
    findings = []
    for r in rules:
        if not isinstance(r, dict):
            continue
        col = r.get("column")
        kind = r.get("rule")
        if not col or not kind or col not in df.columns:
            continue
        series = df[col]
        try:
            if kind == "required":
                bad = series.isna() | series.astype("string").str.strip().eq("").fillna(True)
                issue = "Required value is missing"
            elif kind == "range":
                numeric = pd.to_numeric(series, errors="coerce")
                bad = pd.Series(False, index=df.index)
                if "min" in r:
                    bad |= numeric < float(r["min"])
                if "max" in r:
                    bad |= numeric > float(r["max"])
                issue = f"Value outside range [{r.get('min', '-inf')}, {r.get('max', 'inf')}]"
            elif kind == "regex":
                pattern = r.get("pattern", "")
                text = series.astype("string").fillna("")
                bad = ~text.str.contains(pattern, regex=True, na=False)
                issue = f"Does not match pattern {pattern}"
            elif kind == "allowed_values":
                allowed = set(r.get("values", []))
                bad = ~series.isin(allowed)
                issue = "Value not in allowed set"
            elif kind == "unique":
                bad = series.duplicated(keep=False) & series.notna()
                issue = "Duplicate value in unique column"
            elif kind == "email":
                text = series.astype("string").fillna("")
                bad = ~text.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", na=False)
                issue = "Invalid email format"
            else:
                findings.append({"Row number": "", "Column": col, "Rule": kind, "Value": "", "Issue": f"Unsupported validation rule: {kind}"})
                continue
        except Exception as exc:
            findings.append({"Row number": "", "Column": col, "Rule": kind, "Value": "", "Issue": f"Rule configuration error: {exc}"})
            continue

        for idx in df.index[bad.fillna(False)]:
            try:
                row_number = int(df.index.get_loc(idx)) + 1
            except Exception:
                row_number = str(idx)
            value = series.loc[idx]
            findings.append({"Row number": row_number, "Column": col, "Rule": kind, "Value": str(value)[:300], "Issue": issue})

    return pd.DataFrame(findings, columns=cols)


# ---------------------------------------------------------------------------
# 3. Change Audit & Diff Reporting
# ---------------------------------------------------------------------------

def build_change_report(original: pd.DataFrame, cleaned: pd.DataFrame) -> pd.DataFrame:
    """Summarize row removals and cell changes for review."""
    cols = ["Source row", "Column", "Before", "After", "Change type"]
    if original is None or cleaned is None:
        return pd.DataFrame(columns=cols)
    out = []
    original_idx = set(original.index.tolist())
    cleaned_idx = set(cleaned.index.tolist())
    for idx in sorted(original_idx - cleaned_idx, key=str):
        out.append({"Source row": str(idx), "Column": "", "Before": "Entire row", "After": "", "Change type": "Row removed"})

    if list(original.columns) == list(cleaned.columns):
        column_pairs = [(c, c) for c in original.columns]
    elif len(original.columns) == len(cleaned.columns):
        column_pairs = list(zip(original.columns, cleaned.columns))
    else:
        column_pairs = [(c, c) for c in original.columns if c in cleaned.columns]

    for idx in sorted(original_idx & cleaned_idx, key=str):
        for before_col, after_col in column_pairs:
            before = original.at[idx, before_col]
            after = cleaned.at[idx, after_col]
            before_na = bool(pd.isna(before))
            after_na = bool(pd.isna(after))
            same = (before_na and after_na) or (not before_na and not after_na and str(before) == str(after))
            if not same:
                out.append({
                    "Source row": str(idx),
                    "Column": str(before_col),
                    "Before": "" if before_na else str(before)[:500],
                    "After": "" if after_na else str(after)[:500],
                    "Change type": "Cell changed",
                })
    return pd.DataFrame(out, columns=cols)


# ---------------------------------------------------------------------------
# 4. Unified Cleaning Pipeline (All-in-one Data Cleaning Engine)
# ---------------------------------------------------------------------------

def clean_dataframe(source: pd.DataFrame, profile_name="Clean Dataset", custom=None):
    """Unified data cleaning engine.
    
    Executes standard hygiene (column normalization, empty-row removal,
    whitespace trimming, type inference, deduplication), configurable missing
    value imputation, outlier management, and issue review findings.
    
    Returns: (cleaned_dataframe, logs_dataframe, original_dataframe, issues_dataframe)
    """
    original = source.copy()
    data = source.copy()
    logs = []

    def log(action, count, details):
        logs.append({
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Action": action,
            "Count": int(count),
            "Details": details,
        })

    # Default settings for comprehensive cleaning
    settings = {
        "normalize_columns": True,
        "remove_empty": True,
        "trim_text": True,
        "normalize_case": False,
        "remove_duplicates": True,
        "convert_numeric": True,
        "convert_dates": True,
        "fill_missing": False,
        "missing_strategy": "Leave missing values unchanged",
        "fuzzy_standardize": False,
        "outlier_strategy": "Flag only",
        "validation_rules": [],
    }
    # Backward compatibility for any profiles
    if profile_name in ("Advanced Clean", "Deep Clean"):
        settings.update({"normalize_case": True})
    if custom:
        settings.update(custom)

    # 1. Remove empty rows
    if settings.get("remove_empty", True):
        before = len(data)
        data = data.dropna(how="all")
        log("Removed empty rows", before - len(data), "Rows where all cells were empty.")

    # 2. Normalize column headers
    if settings.get("normalize_columns", True):
        before = list(data.columns)
        data = norm_cols(data)
        changed = sum(str(a) != str(b) for a, b in zip(before, data.columns))
        log("Normalized column names", changed, "Standardized spaces and punctuation to snake_case.")

    # 3. Trim whitespace in text fields
    if settings.get("trim_text", True):
        changed = 0
        for column in data.select_dtypes(include=["object", "string"]).columns:
            before = data[column].astype("string")
            after = before.str.strip().replace("", pd.NA)
            changed += int((before.fillna("<NA>") != after.fillna("<NA>")).sum())
            data[column] = after
        log("Trimmed text values", changed, "Removed leading/trailing spaces and converted blanks to missing.")

    # 4. Standardize text capitalization (if enabled)
    if settings.get("normalize_case", False):
        changed = 0
        for column in data.select_dtypes(include=["object", "string"]).columns:
            before = data[column].astype("string")
            after = before.map(
                lambda value: value.title() if pd.notna(value) and "@" not in str(value)
                else (str(value).lower() if pd.notna(value) and "@" in str(value) else value)
            )
            changed += int((before.fillna("<NA>") != after.fillna("<NA>")).sum())
            data[column] = after
        log("Standardized text capitalization", changed, "Title case for general text and lowercase for email-like values.")

    # 5. Type detection & conversion: Numeric
    if settings.get("convert_numeric", True):
        converted = []
        for column in data.select_dtypes(include=["object", "string"]).columns:
            series = data[column].astype("string").str.strip().str.replace(r"[₹$€£,\s]", "", regex=True)
            mask = series.notna() & series.ne("")
            if mask.sum():
                numeric = pd.to_numeric(series, errors="coerce")
                if numeric[mask].notna().mean() >= 0.85:
                    data[column] = numeric
                    converted.append(str(column))
        log("Converted numeric-looking columns", len(converted), ", ".join(converted) if converted else "No suitable columns found.")

    # 6. Type detection & conversion: Dates
    if settings.get("convert_dates", True):
        converted = []
        for column in data.select_dtypes(include=["object", "string"]).columns:
            if any(key in str(column).lower() for key in ["date", "time", "dob", "created", "updated", "joining"]):
                converted_dates = pd.to_datetime(data[column], errors="coerce", dayfirst=True)
                mask = data[column].notna() & data[column].astype("string").str.strip().ne("")
                if mask.sum() and converted_dates[mask].notna().mean() >= 0.70:
                    data[column] = converted_dates
                    converted.append(str(column))
        log("Converted date-like columns", len(converted), ", ".join(converted) if converted else "No suitable columns found.")

    # 7. Deduplicate exact matching rows
    if settings.get("remove_duplicates", True):
        before = len(data)
        data = data.drop_duplicates()
        log("Removed exact duplicates", before - len(data), "Kept the first occurrence of each duplicate row.")

    # 8. Missing value handling & imputation
    if settings.get("fill_missing", False):
        strategy = settings.get("missing_strategy", "Fill numeric median / text mode")
        if strategy == "Remove rows with missing values":
            before = len(data)
            data = data.dropna()
            log("Removed rows with missing values", before - len(data), "Rows containing any blank value removed.")
        elif strategy == "Fill numeric median / text mode":
            count = 0
            for column in data.columns:
                if not data[column].isna().any():
                    continue
                if pd.api.types.is_numeric_dtype(data[column]):
                    value = data[column].median()
                else:
                    modes = data[column].mode(dropna=True)
                    value = modes.iloc[0] if not modes.empty else pd.NA
                if pd.notna(value):
                    count += int(data[column].isna().sum())
                    data[column] = data[column].fillna(value)
            log("Filled missing values", count, "Numeric columns: median; other columns: mode.")
        elif strategy in ("KNN imputation (numeric columns)", "Iterative imputation (numeric columns)"):
            numeric_columns = list(data.select_dtypes(include=["number"]).columns)
            eligible = [col for col in numeric_columns if not data[col].isna().all()]
            missing_count = int(data[eligible].isna().sum().sum()) if eligible else 0
            if eligible and missing_count:
                try:
                    if strategy.startswith("KNN"):
                        from sklearn.impute import KNNImputer
                        imputer = KNNImputer(n_neighbors=min(5, max(1, len(data) - 1)))
                    else:
                        from sklearn.experimental import enable_iterative_imputer  # noqa: F401
                        from sklearn.impute import IterativeImputer
                        imputer = IterativeImputer(max_iter=10, random_state=42)
                    data[eligible] = imputer.fit_transform(data[eligible])
                    for column in data.columns:
                        if column not in numeric_columns and data[column].isna().any():
                            modes = data[column].mode(dropna=True)
                            if not modes.empty:
                                data[column] = data[column].fillna(modes.iloc[0])
                    log(strategy, missing_count, "Advanced imputation applied to numeric columns; non-numeric filled with mode.")
                except ImportError as exc:
                    raise RuntimeError("Install scikit-learn to use KNN or Iterative imputation.") from exc
            else:
                log(strategy, 0, "No eligible numeric missing values were found.")

    # 9. Outlier treatment (if configured)
    outlier_strategy = settings.get("outlier_strategy", "Flag only")
    if outlier_strategy in ("Cap using IQR bounds", "Remove outlier rows"):
        changed = 0
        if outlier_strategy == "Cap using IQR bounds":
            for column in data.select_dtypes(include=["number"]).columns:
                values = data[column].dropna()
                if len(values) < 8:
                    continue
                q1, q3 = values.quantile(.25), values.quantile(.75)
                iqr = q3 - q1
                if pd.isna(iqr) or iqr <= 0:
                    continue
                lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                mask = data[column].notna() & ((data[column] < lower) | (data[column] > upper))
                changed += int(mask.sum())
                data.loc[mask, column] = data.loc[mask, column].clip(lower, upper)
        else:
            row_mask = pd.Series(False, index=data.index)
            for column in data.select_dtypes(include=["number"]).columns:
                values = data[column].dropna()
                if len(values) < 8:
                    continue
                q1, q3 = values.quantile(.25), values.quantile(.75)
                iqr = q3 - q1
                if pd.notna(iqr) and iqr > 0:
                    row_mask |= data[column].notna() & ((data[column] < q1 - 1.5 * iqr) | (data[column] > q3 + 1.5 * iqr))
            changed = int(row_mask.sum())
            data = data.loc[~row_mask].copy()
        log("Outlier treatment", changed, outlier_strategy)

    # 10. Issue Detection & Validation
    issues = issue_frame(data)
    validation = validate_dataframe(data, settings.get("validation_rules", []))
    if not validation.empty:
        populated = validation[validation["Row number"].astype(str).ne("")]
        for (column, rule), group in populated.groupby(["Column", "Rule"]):
            issues.loc[len(issues)] = {
                "Category": "Schema validation",
                "Column": column,
                "Count": len(group),
                "Details": f"{rule}: {group['Issue'].iloc[0]}",
                "Suggested action": "Review row-level validation report",
                "Review status": "Pending",
            }
    log("Generated issue findings", len(issues), "Includes missingness, duplicates, outliers, business-rule warnings, and schema validation.")

    return data, pd.DataFrame(logs), original, issues


# ---------------------------------------------------------------------------
# 5. Local Audit Trail Persistence (SQLite)
# ---------------------------------------------------------------------------

def audit_db_path() -> Path:
    folder = Path.home() / ".cleansheet"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "audit.db"


def write_audit(event, source, profile_name, rows_before, rows_after, status="Completed", details=""):
    """Persist a lightweight local audit trail in SQLite."""
    with sqlite3.connect(audit_db_path()) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            event TEXT NOT NULL, source TEXT, profile TEXT, rows_before INTEGER,
            rows_after INTEGER, status TEXT, details TEXT)""")
        conn.execute(
            "INSERT INTO audit_log(timestamp,event,source,profile,rows_before,rows_after,status,details) VALUES(?,?,?,?,?,?,?,?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                str(event),
                str(source or ""),
                str(profile_name or ""),
                int(rows_before or 0),
                int(rows_after or 0),
                str(status),
                str(details or ""),
            ),
        )
        conn.commit()


def read_audit(limit=500) -> pd.DataFrame:
    """Read local audit log."""
    with sqlite3.connect(audit_db_path()) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT NOT NULL,
            event TEXT NOT NULL, source TEXT, profile TEXT, rows_before INTEGER,
            rows_after INTEGER, status TEXT, details TEXT)""")
        rows = conn.execute(
            "SELECT timestamp,event,source,profile,rows_before,rows_after,status,details FROM audit_log ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
    return pd.DataFrame(rows, columns=["Timestamp", "Event", "Source", "Profile", "Rows before", "Rows after", "Status", "Details"])


# ---------------------------------------------------------------------------
# 6. Excel Reporting
# ---------------------------------------------------------------------------

def write_excel_report(path, cleaned, logs, original, issues, validation_rules=None):
    """Write complete report workbook atomically."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    temporary = target.with_name(f".{target.stem}.{stamp}.tmp{target.suffix or '.xlsx'}")
    try:
        with pd.ExcelWriter(temporary, engine="openpyxl", datetime_format="yyyy-mm-dd") as writer:
            cleaned.to_excel(writer, index=False, sheet_name="Cleaned Data")
            logs.to_excel(writer, index=False, sheet_name="Cleaning Log")
            column_summary(cleaned).to_excel(writer, index=False, sheet_name="Column Summary")
            (issues if issues is not None else pd.DataFrame()).to_excel(writer, index=False, sheet_name="Issue Review")
            validate_dataframe(cleaned, validation_rules or []).to_excel(writer, index=False, sheet_name="Validation Report")
            build_change_report(original, cleaned).to_excel(writer, index=False, sheet_name="Change Review")
            pd.DataFrame([
                {"Metric": "Source quality score", "Value": quality_score(original)},
                {"Metric": "Cleaned quality score", "Value": quality_score(cleaned)},
            ]).to_excel(writer, index=False, sheet_name="Quality Score")
        temporary.replace(target)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        except Exception:
            pass
        raise


# Backward-compatibility alias
clean_level_1_2 = clean_dataframe

__all__ = [
    "norm_cols",
    "profile",
    "quality_score",
    "read_data",
    "column_summary",
    "clean_dataframe",
    "clean_level_1_2",
    "issue_frame",
    "validate_dataframe",
    "build_change_report",
    "write_excel_report",
    "write_audit",
    "read_audit",
]
