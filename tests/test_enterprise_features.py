"""Unit tests for enterprise-grade features in CleanSheet.
Tests string standardization, smart date parsing, address/pincode extraction,
casing formats, deep diagnostics, SQL execution & export, and data lineage tracker.
"""
import unittest
import os
import sqlite3
import pandas as pd
import numpy as np

from enterprise_engine import (
    normalize_phone_numbers,
    parse_mixed_dates,
    extract_address_components,
    apply_case_format,
    generate_deep_profile,
    detect_redundant_columns,
    execute_sql_query,
    export_to_sql_table,
    ingest_json_data,
    process_large_csv_in_chunks,
    save_protected_excel,
    DataLineageTracker
)


class TestEnterpriseFeatures(unittest.TestCase):

    def test_phone_normalization(self):
        s = pd.Series(["9876543210", "+91 98765 43210", "98765-43210", "12345", "None"])
        norm, stats = normalize_phone_numbers(s, default_country_code="+91", format_style="E164")
        self.assertEqual(stats["valid_standardized"], 3)
        self.assertEqual(norm.iloc[0], "+919876543210")
        self.assertEqual(norm.iloc[1], "+919876543210")

    def test_smart_date_parser(self):
        dates = pd.Series(["2023-01-15", "15/01/2023", "Jan 15, 2023", "invalid date", None])
        parsed, stats = parse_mixed_dates(dates, output_format="%Y-%m-%d")
        self.assertEqual(stats["successfully_converted"], 3)
        self.assertEqual(parsed.iloc[0], "2023-01-15")
        self.assertEqual(parsed.iloc[1], "2023-01-15")
        self.assertEqual(parsed.iloc[2], "2023-01-15")

    def test_address_pincode_extractor(self):
        addrs = pd.Series([
            "Flat 402, MG Road, Bengaluru 560001, Karnataka",
            "12/A Park Street, Kolkata - 700016",
            "No pin code here"
        ], name="address")
        res = extract_address_components(addrs)
        self.assertEqual(res["address_pincode"].iloc[0], "560001")
        self.assertEqual(res["address_pincode"].iloc[1], "700016")
        self.assertEqual(res["address_pincode"].iloc[2], "")

    def test_case_formatting(self):
        s = pd.Series(["hello world", "JANE DOE", "data_science_project"])
        self.assertEqual(apply_case_format(s, "title").iloc[0], "Hello World")
        self.assertEqual(apply_case_format(s, "upper").iloc[0], "HELLO WORLD")
        self.assertEqual(apply_case_format(s, "lower").iloc[1], "jane doe")
        self.assertEqual(apply_case_format(s, "snake").iloc[0], "hello_world")

    def test_deep_diagnostics_and_redundancy(self):
        df = pd.DataFrame({
            "col_a": [1, 2, 3, 4, 5],
            "col_dup": [1, 2, 3, 4, 5],  # duplicate
            "col_collinear": [2, 4, 6, 8, 10],  # collinear with col_a
            "col_random": [10, 50, 20, 80, 90]
        })
        profile = generate_deep_profile(df)
        self.assertEqual(profile["summary"]["total_rows"], 5)
        self.assertEqual(profile["summary"]["total_columns"], 4)
        self.assertIn("col_a", profile["columns"])

        red = detect_redundant_columns(df)
        self.assertTrue(len(red) >= 1)
        self.assertTrue(any(r["col_a"] == "col_a" and r["col_b"] == "col_dup" for r in red))

    def test_sql_ingest_and_export(self):
        test_db = "test_enterprise_temp.db"
        try:
            conn = sqlite3.connect(test_db)
            test_df = pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"], "score": [95.5, 88.0, 76.5]})
            test_df.to_sql("students", conn, if_exists="replace", index=False)
            conn.close()

            # Test execution / ingestion
            df_read = execute_sql_query(test_db, "SELECT * FROM students WHERE score > 80")
            self.assertEqual(len(df_read), 2)
            self.assertEqual(len(df_read.columns), 3)

            # Test export to new table
            rows_written = export_to_sql_table(df_read, test_db, "top_students", if_exists="replace")
            self.assertEqual(rows_written, 2)

            conn = sqlite3.connect(test_db)
            verify_df = pd.read_sql("SELECT * FROM top_students", conn)
            conn.close()
            self.assertEqual(len(verify_df), 2)
        finally:
            if os.path.exists(test_db):
                try:
                    os.remove(test_db)
                except Exception:
                    pass

    def test_lineage_tracker(self):
        tracker = DataLineageTracker()
        tracker.record_step("Initial Import", "Read CSV", 0, 100, "Imported file.csv")
        tracker.record_step("Clean", "Remove Blanks", 100, 95, "Dropped 5 blank rows")

        hist = tracker.get_lineage()
        self.assertEqual(len(hist), 2)
        self.assertEqual(hist[0]["stage"], "Initial Import")
        self.assertEqual(hist[1]["stage"], "Clean")
        self.assertEqual(hist[1]["delta"], -5)

    def test_json_ingest_and_flatten(self):
        json_sample = '{"status": "ok", "items": [{"id": 101, "name": "Prod A", "details": {"color": "red"}}, {"id": 102, "name": "Prod B", "details": {"color": "blue"}}]}'
        df = ingest_json_data(json_sample)
        self.assertEqual(len(df), 2)
        self.assertIn("details.color", df.columns)

    def test_protected_excel(self):
        test_file = "test_protected_sample.xlsx"
        try:
            df = pd.DataFrame({"col_a": [1, 2], "col_b": ["secret1", "secret2"]})
            out = save_protected_excel(df, test_file, password="testpassword123")
            self.assertTrue(os.path.exists(out))
        finally:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except Exception:
                    pass

    def test_chunk_streaming(self):
        csv_in = "test_chunk_in.csv"
        csv_out = "test_chunk_out.csv"
        try:
            df = pd.DataFrame({"id": list(range(100)), "val": ["test"] * 100})
            df.to_csv(csv_in, index=False)
            res = process_large_csv_in_chunks(csv_in, csv_out, chunk_size=25)
            self.assertEqual(res["chunks_processed"], 4)
            self.assertEqual(res["rows_cleaned"], 100)
            self.assertTrue(os.path.exists(csv_out))
        finally:
            for f in [csv_in, csv_out]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass


if __name__ == "__main__":
    unittest.main()
