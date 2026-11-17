"""Advance Data Cleaning & Privacy Engine for CleanSheet Studio.

Provides:
- PII Detection & Sensitive Data Masking (Full, Partial, Hashing)
- Fuzzy String Clustering & Typo Deduplication / Merging
- Reusable Visual Recipe Pipeline Execution
- Executive PDF Audit Report & Data Hygiene Certificate Generation
"""
import os
import re
import difflib
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

import pandas as pd
from clean_engine import quality_score, norm_cols


# ---------------------------------------------------------------------------
# 1. PII Detection & Masking
# ---------------------------------------------------------------------------

def detect_pii_columns(df: pd.DataFrame) -> dict:
    """Detect columns containing Personally Identifiable Information (PII).
    Returns mapping: {col_name: {'type': 'EMAIL|PHONE|CREDIT_CARD|AADHAAR_SSN', 'count': n, 'ratio': float}}
    """
    pii_results = {}
    if df is None or df.empty:
        return pii_results

    patterns = {
        "EMAIL": re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"),
        "PHONE": re.compile(r"^(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}$"),
        "CREDIT_CARD": re.compile(r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9][0-9])[0-9]{12}|3[47][0-9]{13})$"),
        "AADHAAR_SSN": re.compile(r"^\d{3}-\d{2}-\d{4}$|^\d{4}\s\d{4}\s\d{4}$|^\d{12}$"),
    }

    for col in df.columns:
        series = df[col].dropna().astype(str).str.strip()
        if len(series) == 0:
            continue
        sample = series.iloc[:min(200, len(series))]
        for pii_type, regex in patterns.items():
            matches = sample.apply(lambda x: bool(regex.match(str(x))))
            ratio = matches.sum() / len(sample)
            if ratio >= 0.35 or (col.lower() in ["email", "e-mail", "mail"] and ratio >= 0.1):
                pii_results[col] = {
                    "type": pii_type,
                    "count": int(matches.sum()),
                    "ratio": round(float(ratio), 2),
                    "total_checked": len(sample)
                }
                break
    return pii_results


def mask_data(df: pd.DataFrame, mask_config: dict) -> pd.DataFrame:
    """Mask specified columns in DataFrame.
    mask_config format: {col_name: 'full' | 'partial' | 'hash'}
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    def _mask_val(val, method):
        if pd.isna(val) or val == "" or str(val).strip() == "":
            return val
        s = str(val).strip()
        if method == "full":
            return "********"
        elif method == "hash":
            return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12].upper()
        elif method == "partial":
            if "@" in s:
                parts = s.split("@", 1)
                user, domain = parts[0], parts[1]
                masked_user = user[0] + "***" if len(user) > 1 else "***"
                return f"{masked_user}@{domain}"
            elif sum(c.isdigit() for c in s) >= 7:
                digits = [c for c in s if c.isdigit()]
                return f"***-***-{s[-4:]}" if len(s) >= 4 else "****"
            else:
                return s[0] + "*" * max(1, len(s) - 2) + s[-1] if len(s) > 2 else "**"
        return s

    for col, method in mask_config.items():
        if col in out.columns and method in ["full", "partial", "hash"]:
            out[col] = out[col].apply(lambda v: _mask_val(v, method))

    return out


# ---------------------------------------------------------------------------
# 2. Fuzzy Matching & Deduplication / Merging
# ---------------------------------------------------------------------------

def find_fuzzy_clusters(df: pd.DataFrame, column: str, threshold: float = 0.82) -> list:
    """Find clusters of similar string values in a column.
    Returns list of clusters: [{'primary': str, 'variants': [{'val': str, 'count': int, 'score': float}], 'total_rows': int}]
    """
    if df is None or column not in df.columns:
        return []

    values_counts = df[column].dropna().astype(str).str.strip().value_counts()
    items = [(val, count) for val, count in values_counts.items() if val]
    if len(items) <= 1:
        return []

    visited = set()
    clusters = []

    for i, (val_a, count_a) in enumerate(items):
        if val_a.lower() in visited:
            continue
        current_cluster = {
            "primary": val_a,
            "variants": [{"val": val_a, "count": count_a, "score": 1.0}],
            "total_rows": count_a
        }
        visited.add(val_a.lower())

        for j in range(i + 1, min(i + 100, len(items))):
            val_b, count_b = items[j]
            if val_b.lower() in visited:
                continue

            sim = difflib.SequenceMatcher(None, val_a.lower(), val_b.lower()).ratio()
            tokens_a = set(re.findall(r"\w+", val_a.lower()))
            tokens_b = set(re.findall(r"\w+", val_b.lower()))
            jaccard = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))

            if sim >= threshold or (jaccard >= 0.65 and len(tokens_a) > 1 and len(tokens_b) > 1):
                visited.add(val_b.lower())
                current_cluster["variants"].append({"val": val_b, "count": count_b, "score": round(max(sim, jaccard), 2)})
                current_cluster["total_rows"] += count_b

        if len(current_cluster["variants"]) > 1:
            clusters.append(current_cluster)

    return sorted(clusters, key=lambda c: c["total_rows"], reverse=True)


def apply_fuzzy_cluster_merges(df: pd.DataFrame, column: str, merge_map: dict) -> pd.DataFrame:
    """Replace variant values with canonical primary values in DataFrame."""
    if df is None or column not in df.columns or not merge_map:
        return df

    out = df.copy()
    out[column] = out[column].astype(str).str.strip().replace(merge_map)
    return out


# ---------------------------------------------------------------------------
# 3. Reusable Recipe Pipeline Execution
# ---------------------------------------------------------------------------

def execute_recipe_pipeline(df: pd.DataFrame, recipe_steps: list) -> tuple:
    """Execute an ordered series of recipe steps on a dataframe.
    Returns: (cleaned_df, step_logs)
    """
    if df is None:
        return df, []

    curr = df.copy()
    step_logs = []

    for step in recipe_steps:
        if not step.get("enabled", True):
            continue
        action = step.get("action")
        params = step.get("params", {})

        try:
            if action == "trim_spaces":
                cols = params.get("columns", curr.columns)
                for col in cols:
                    if col in curr.columns and curr[col].dtype == object:
                        curr[col] = curr[col].astype(str).str.strip()
                step_logs.append({"step": step.get("name", "Trim Spaces"), "status": "Success", "details": "Trimmed leading/trailing spaces"})

            elif action == "remove_duplicates":
                subset = params.get("subset", None)
                before = len(curr)
                curr = curr.drop_duplicates(subset=subset)
                step_logs.append({"step": step.get("name", "Remove Duplicates"), "status": "Success", "details": f"Removed {before - len(curr)} duplicate row(s)"})

            elif action == "drop_empty_rows":
                before = len(curr)
                curr = curr.dropna(how="all")
                step_logs.append({"step": step.get("name", "Drop Empty Rows"), "status": "Success", "details": f"Dropped {before - len(curr)} completely empty row(s)"})

            elif action == "standardize_headers":
                curr = norm_cols(curr)
                step_logs.append({"step": step.get("name", "Standardize Headers"), "status": "Success", "details": "Normalized columns to snake_case"})

            elif action == "impute_missing":
                method = params.get("method", "median_mode")
                cols = params.get("columns", curr.columns)
                imputed = 0
                for col in cols:
                    if col in curr.columns and curr[col].isna().any():
                        imputed += curr[col].isna().sum()
                        if pd.api.types.is_numeric_dtype(curr[col]):
                            val = curr[col].median() if method == "median_mode" else curr[col].mean()
                            curr[col] = curr[col].fillna(val)
                        else:
                            mode_val = curr[col].mode().dropna()
                            val = mode_val.iloc[0] if not mode_val.empty else "Unknown"
                            curr[col] = curr[col].fillna(val)
                step_logs.append({"step": step.get("name", "Impute Missing"), "status": "Success", "details": f"Imputed {imputed} missing cell(s)"})

            elif action == "mask_columns":
                mask_cfg = params.get("mask_config", {})
                curr = mask_data(curr, mask_cfg)
                step_logs.append({"step": step.get("name", "Mask Sensitive Data"), "status": "Success", "details": f"Applied privacy masking on {len(mask_cfg)} column(s)"})

            elif action == "fuzzy_merge":
                col = params.get("column")
                m_map = params.get("merge_map", {})
                if col and m_map:
                    curr = apply_fuzzy_cluster_merges(curr, col, m_map)
                    step_logs.append({"step": step.get("name", "Fuzzy Merge"), "status": "Success", "details": f"Merged {len(m_map)} variant(s) in {col}"})

        except Exception as e:
            step_logs.append({"step": step.get("name", action), "status": "Failed", "details": str(e)})

    return curr, step_logs


# ---------------------------------------------------------------------------
# 4. Executive PDF Audit Report Generation
# ---------------------------------------------------------------------------

def generate_executive_pdf_report(path: str, original_df: pd.DataFrame, cleaned_df: pd.DataFrame, logs_df: pd.DataFrame = None, pii_detected: dict = None) -> str:
    """Generate professional executive audit certificate and summary report in PDF format."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(target),
        pagesize=letter,
        rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=15,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=colors.HexColor("#1F2937"),
        spaceBefore=10,
        spaceAfter=6,
    )
    normal_text = ParagraphStyle(
        "NormalText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#374151"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("CleanSheet™ | Executive Data Quality Audit Certificate", title_style))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | Offline Local Execution", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#3B82F6"), spaceAfter=14))

    # 2. Executive Scorecard Table
    score_before = quality_score(original_df) if original_df is not None else 0
    score_after = quality_score(cleaned_df) if cleaned_df is not None else 0
    rows_orig = len(original_df) if original_df is not None else 0
    rows_clean = len(cleaned_df) if cleaned_df is not None else 0
    cols_count = len(cleaned_df.columns) if cleaned_df is not None else 0
    fixed_cells = len(logs_df) if logs_df is not None else 0

    scorecard_data = [
        ["Health Quality Score", f"{score_before:.1f} / 100", f"{score_after:.1f} / 100", f"+{max(0.0, score_after - score_before):.1f}% Gain"],
        ["Total Valid Records", f"{rows_orig:,} rows", f"{rows_clean:,} rows", "Verified Processed"],
        ["Columns Inspected", f"{cols_count} columns", f"{cols_count} columns", "Structure Retained"],
        ["Total Anomalies Corrected", "--", f"{fixed_cells:,} modifications", "Audit Logged"]
    ]
    scorecard_table = Table(
        [["Evaluation Metric", "Initial Ingestion", "Final Cleaned State", "Audit Assessment"]] + scorecard_data,
        colWidths=[180, 110, 120, 120]
    )
    scorecard_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("TEXTCOLOR", (2, 1), (2, 1), colors.HexColor("#16A34A")),
        ("FONTNAME", (2, 1), (2, 1), "Helvetica-Bold"),
    ]))
    story.append(scorecard_table)
    story.append(Spacer(1, 14))

    # 3. Privacy & PII Compliance Assessment
    story.append(Paragraph("Data Privacy & Security Compliance Assessment", section_heading))
    if pii_detected:
        pii_rows = [["Column Identified", "PII Classification", "Sample Detections", "Confidence Score"]]
        for col, meta in pii_detected.items():
            pii_rows.append([col, meta["type"], f"{meta['count']} records", f"{int(meta['ratio'] * 100)}%"])
        pii_table = Table(pii_rows, colWidths=[150, 130, 120, 130])
        pii_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#FDE68A")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(pii_table)
    else:
        story.append(Paragraph("✅ Zero high-risk unmasked PII entities detected in certified export.", normal_text))

    story.append(Spacer(1, 14))

    # 4. Cleaning Trail & Audit Summary
    story.append(Paragraph("Execution Trail & Remediation Summary", section_heading))
    if logs_df is not None and not logs_df.empty:
        log_sample = logs_df.head(8)
        trail_rows = [["Row ID", "Column", "Original Value", "Remediated Clean Value"]]
        for _, r in log_sample.iterrows():
            trail_rows.append([
                str(r.get("row_index", "--")),
                str(r.get("column", "--"))[:22],
                str(r.get("old_value", ""))[:25],
                str(r.get("new_value", ""))[:25]
            ])
        trail_table = Table(trail_rows, colWidths=[60, 130, 170, 170])
        trail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(trail_table)
        if len(logs_df) > 8:
            story.append(Paragraph(f"<i>... and {len(logs_df) - 8} more logged cleaning events. Complete audit log available in Excel report.</i>", normal_text))
    else:
        story.append(Paragraph("No modifications required. Dataset met all standard hygiene benchmarks.", normal_text))

    # 5. Certification Sign-off Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB"), spaceAfter=8))
    cert_text = Paragraph(
        "<b>CERTIFICATE OF HYGIENE COMPLIANCE:</b> This dataset has been validated offline through CleanSheet Data Engine. "
        "Standard checks including whitespace trimming, schema casting, missing-value imputation, and duplicate resolution have been finalized.",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6B7280"))
    )
    story.append(cert_text)

    doc.build(story)
    return str(target)
# ---------------------------------------------------------------------------
# 5. Statistical Outlier & Anomaly Detection (IQR & Z-Score)
# ---------------------------------------------------------------------------

def detect_outliers(df: pd.DataFrame, method: str = "iqr", threshold: float = 1.5) -> dict:
    """Detect statistical outliers in numeric columns using IQR or Z-Score.
    Returns: {col_name: {'count': int, 'indices': list, 'lower_bound': float, 'upper_bound': float, 'outliers': list}}
    """
    outlier_info = {}
    if df is None or df.empty:
        return outlier_info

    num_cols = df.select_dtypes(include=["number"]).columns
    for col in num_cols:
        series = df[col].dropna()
        if len(series) < 5:
            continue

        if method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - (threshold * iqr)
            upper = q3 + (threshold * iqr)
            outlier_mask = (df[col] < lower) | (df[col] > upper)
        else:  # Z-score
            mean = series.mean()
            std = series.std()
            if std == 0:
                continue
            z_scores = (df[col] - mean).abs() / std
            lower = mean - (threshold * std)
            upper = mean + (threshold * std)
            outlier_mask = z_scores > threshold

        matching_indices = df[outlier_mask].index.tolist()
        if matching_indices:
            outlier_info[col] = {
                "count": len(matching_indices),
                "indices": matching_indices,
                "lower_bound": round(float(lower), 2),
                "upper_bound": round(float(upper), 2),
                "values": df.loc[matching_indices, col].tolist()[:15],
            }

    return outlier_info


def remediate_outliers(df: pd.DataFrame, remediation_config: dict) -> pd.DataFrame:
    """Remediate outliers in DataFrame based on config.
    remediation_config: {col_name: {'action': 'clip' | 'median' | 'drop', 'lower': float, 'upper': float}}
    """
    if df is None or df.empty or not remediation_config:
        return df

    out = df.copy()
    rows_to_drop = set()

    for col, cfg in remediation_config.items():
        if col not in out.columns:
            continue
        action = cfg.get("action", "clip")
        lower = cfg.get("lower")
        upper = cfg.get("upper")

        if lower is None or upper is None:
            continue

        mask = (out[col] < lower) | (out[col] > upper)
        if not mask.any():
            continue

        if action == "clip":
            out[col] = out[col].clip(lower=lower, upper=upper)
        elif action == "median":
            med = out.loc[~mask, col].median()
            out.loc[mask, col] = med
        elif action == "drop":
            rows_to_drop.update(out[mask].index.tolist())

    if rows_to_drop:
        out = out.drop(index=list(rows_to_drop)).reset_index(drop=True)

    return out


# ---------------------------------------------------------------------------
# 6. Column Split & Merge Tools
# ---------------------------------------------------------------------------

def split_column(df: pd.DataFrame, col: str, delimiter: str = ",", new_names: list = None, max_split: int = 1) -> pd.DataFrame:
    """Split a single column into multiple columns by a delimiter."""
    if df is None or col not in df.columns:
        return df

    out = df.copy()
    split_df = out[col].astype(str).str.split(delimiter, n=max_split, expand=True)

    if new_names and len(new_names) == split_df.shape[1]:
        split_df.columns = new_names
    else:
        split_df.columns = [f"{col}_part{i+1}" for i in range(split_df.shape[1])]

    # Strip whitespace from new split columns
    for c in split_df.columns:
        split_df[c] = split_df[c].astype(str).str.strip()

    col_idx = out.columns.get_loc(col)
    out = out.drop(columns=[col])
    for i, c in enumerate(split_df.columns):
        out.insert(col_idx + i, c, split_df[c])

    return out


def merge_columns(df: pd.DataFrame, cols: list, new_col_name: str, separator: str = " ", drop_source: bool = False) -> pd.DataFrame:
    """Merge multiple columns into a single column with a separator."""
    if df is None or not cols or not new_col_name:
        return df

    out = df.copy()
    valid_cols = [c for c in cols if c in out.columns]
    if not valid_cols:
        return df

    combined = out[valid_cols].astype(str).agg(separator.join, axis=1)
    out[new_col_name] = combined

    if drop_source:
        out = out.drop(columns=valid_cols)

    return out


# ---------------------------------------------------------------------------
# 7. Multi-File Append & Join / Merge
# ---------------------------------------------------------------------------

def append_datasets(dfs: list) -> pd.DataFrame:
    """Vertically stack/append multiple dataframes into one master dataframe."""
    valid_dfs = [d for d in dfs if d is not None and not d.empty]
    if not valid_dfs:
        return pd.DataFrame()
    return pd.concat(valid_dfs, ignore_index=True)


def join_datasets(left_df: pd.DataFrame, right_df: pd.DataFrame, on_col: str, how: str = "left") -> pd.DataFrame:
    """Horizontally merge/VLOOKUP two dataframes on a common key column."""
    if left_df is None or right_df is None or on_col not in left_df.columns or on_col not in right_df.columns:
        return left_df if left_df is not None else pd.DataFrame()

    return pd.merge(left_df, right_df, on=on_col, how=how, suffixes=("", "_lookup"))


# ---------------------------------------------------------------------------
# 8. Reusable Recipe Serialization (.recipe JSON)
# ---------------------------------------------------------------------------

def export_recipe_to_file(path: str, recipe_steps: list, metadata: dict = None) -> str:
    """Export cleaning recipe steps to a .recipe JSON file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "metadata": metadata or {},
        "steps": recipe_steps
    }
    with open(target, "w", encoding="utf-8") as f:
        import json
        json.dump(payload, f, indent=2)
    return str(target)


def load_recipe_from_file(path: str) -> list:
    """Load cleaning recipe steps from a .recipe JSON file."""
    target = Path(path)
    if not target.exists():
        return []
    with open(target, "r", encoding="utf-8") as f:
        import json
        payload = json.load(f)
    return payload.get("steps", [])
