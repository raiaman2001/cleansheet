"""Regression tests for CleanSheet's actual modular engine.

Run with: python -m unittest discover -s tests -v
"""
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from clean_engine import (
    norm_cols, profile, quality_score, clean_level_1_2,
    issue_frame, validate_dataframe, build_change_report,
    write_excel_report, clean_dataframe,
)


class CleanSheetCoreTests(unittest.TestCase):
    def test_normalize_duplicate_columns(self):
        df = pd.DataFrame([[1, 2, 3]], columns=["Customer Name", "Customer Name", "Age"])
        result = norm_cols(df)
        self.assertEqual(list(result.columns), ["customer_name", "customer_name_2", "age"])

    def test_issue_detection_and_duplicate_removal(self):
        data = pd.DataFrame({
            "City": ["Gurgaon", "Gurgram", "Gurgaon", "Delhi", "Delhi", "Delhi", "Noida", "Noida", "Noida"],
            "Age": [25, 31, 140, 29, 35, 33, 28, 31, 27],
            "Amount": [100, -5, 200, 50, 75, 20, 30, 44, 61],
        })
        categories = set(issue_frame(data)["Category"])
        self.assertIn("Inconsistent categories", categories)
        self.assertIn("Business-rule warnings", categories)
        self.assertIn("Potential outliers", categories)
        duplicated = pd.concat([data, data.iloc[[0]]], ignore_index=True)
        cleaned, logs, original, issues = clean_dataframe(duplicated, "Quick Clean")
        self.assertEqual(len(cleaned), len(data))
        self.assertGreaterEqual(quality_score(data), 0)
        self.assertLessEqual(quality_score(data), 100)

    def test_validation_rules(self):
        rules = [
            {"column": "email", "rule": "email"},
            {"column": "age", "rule": "range", "min": 0, "max": 120},
            {"column": "id", "rule": "unique"},
            {"column": "status", "rule": "allowed_values", "values": ["Active", "Inactive"]},
            {"column": "name", "rule": "required"},
            {"column": "code", "rule": "regex", "pattern": r"^ORD-\d+$"},
        ]
        data = pd.DataFrame({
            "email": ["valid@example.com", "bad-email"], "age": [25, 140], "id": [1, 1],
            "status": ["Active", "Paused"], "name": ["Aman", " "], "code": ["ORD-12", "bad"]
        })
        findings = validate_dataframe(data, rules)
        self.assertEqual(len(findings), 7, findings)
        self.assertEqual(set(findings["Rule"]), {"email", "range", "unique", "allowed_values", "required", "regex"})

    def test_change_report_and_excel_export(self):
        original = pd.DataFrame({"Customer Name": [" Aman ", "Ravi"], "Age": [20, 30]})
        cleaned, logs, old, issues = clean_dataframe(original, "Quick Clean")
        changes = build_change_report(old, cleaned)
        self.assertGreaterEqual(len(changes), 1)
        self.assertIn("Cell changed", set(changes["Change type"]))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.xlsx"
            write_excel_report(output, cleaned, logs, old, issues, [])
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)
            import openpyxl
            workbook = openpyxl.load_workbook(output, read_only=True)
            self.assertTrue({"Cleaned Data", "Cleaning Log", "Column Summary", "Issue Review",
                             "Validation Report", "Change Review", "Quality Score"}.issubset(workbook.sheetnames))
            workbook.close()

    def test_outlier_capping(self):
        data = pd.DataFrame({"amount": [10, 11, 12, 10, 11, 12, 10, 1000]})
        cleaned, _, _, _ = clean_dataframe(data, "Custom Profile", {
            "normalize_columns": False, "remove_empty": False, "trim_text": False,
            "normalize_case": False, "remove_duplicates": False, "convert_numeric": False,
            "convert_dates": False, "outlier_strategy": "Cap using IQR bounds"
        })
        self.assertLess(cleaned["amount"].max(), 1000)

    def test_imputation_strategies(self):
        data = pd.DataFrame({"a": [1.0, None, 3.0, 4.0], "b": [2.0, 4.0, None, 8.0]})
        for strategy in ["KNN imputation (numeric columns)", "Iterative imputation (numeric columns)"]:
            cleaned, _, _, _ = clean_dataframe(data, "Custom Profile", {
                "remove_empty": False, "normalize_columns": False, "trim_text": False,
                "convert_numeric": False, "convert_dates": False, "fill_missing": True,
                "missing_strategy": strategy,
            })
            self.assertEqual(int(cleaned.isna().sum().sum()), 0, strategy)


if __name__ == "__main__":
    unittest.main()
