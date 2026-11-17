"""Unit test suite for CleanSheet advance features:
- PII Detection & Sensitive Data Masking
- Fuzzy String Clustering & Typo Deduplication
- Reusable Recipe Pipeline Execution
- Executive PDF Audit Report Generation
"""
import unittest
import os
from pathlib import Path
import pandas as pd

from advance_engine import (
    detect_pii_columns,
    mask_data,
    find_fuzzy_clusters,
    apply_fuzzy_cluster_merges,
    execute_recipe_pipeline,
    generate_executive_pdf_report
)


class TestAdvanceFeatures(unittest.TestCase):
    def setUp(self):
        self.sample_df = pd.DataFrame({
            "client_name": ["Acme Corp", "Acme Corporation", "Global Tech", "Global Tech Inc."],
            "contact_email": ["contact@acme.com", "sales@acme.org", "info@global.net", "support@global.io"],
            "contact_phone": ["+91 9876543210", "+1-555-019-2834", "9876543210", "555-019-2834"],
            "credit_limit": [50000, 75000, 120000, 90000]
        })

    def test_pii_detection(self):
        pii = detect_pii_columns(self.sample_df)
        self.assertIn("contact_email", pii)
        self.assertEqual(pii["contact_email"]["type"], "EMAIL")

    def test_data_masking(self):
        # Partial mask on email, full mask on phone
        masked = mask_data(self.sample_df, {"contact_email": "partial", "contact_phone": "full"})
        self.assertTrue(masked["contact_email"].iloc[0].endswith("@acme.com"))
        self.assertTrue("*" in masked["contact_email"].iloc[0])
        self.assertEqual(masked["contact_phone"].iloc[0], "********")

    def test_fuzzy_clustering_and_merge(self):
        clusters = find_fuzzy_clusters(self.sample_df, "client_name", threshold=0.7)
        self.assertGreaterEqual(len(clusters), 1)
        
        # Test merge
        primary = clusters[0]["primary"]
        variants = [v["val"] for v in clusters[0]["variants"] if v["val"] != primary]
        if variants:
            merge_map = {variants[0]: primary}
            merged = apply_fuzzy_cluster_merges(self.sample_df, "client_name", merge_map)
            self.assertNotIn(variants[0], merged["client_name"].values)

    def test_recipe_pipeline(self):
        steps = [
            {"id": "s1", "name": "Trim", "action": "trim_spaces", "enabled": True},
            {"id": "s2", "name": "Mask Email", "action": "mask_columns", "params": {"mask_config": {"contact_email": "partial"}}, "enabled": True}
        ]
        cleaned, logs = execute_recipe_pipeline(self.sample_df, steps)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["status"], "Success")

    def test_executive_pdf_generation(self):
        pdf_path = Path("test_cert.pdf")
        out = generate_executive_pdf_report(
            str(pdf_path),
            self.sample_df,
            self.sample_df,
            pd.DataFrame([{"row_index": 1, "column": "client_name", "old_value": "Acme Corp", "new_value": "Acme Corporation"}]),
            {"contact_email": {"type": "EMAIL", "count": 4, "ratio": 1.0}}
        )
        self.assertTrue(pdf_path.exists())
        self.assertGreater(pdf_path.stat().st_size, 500)
        pdf_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

