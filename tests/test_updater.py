"""Unit tests for CleanSheet In-App Auto-Updater."""
import unittest
from updater_engine import parse_semver, UpdateCheckThread


class TestUpdaterEngine(unittest.TestCase):

    def test_semver_parsing(self):
        self.assertEqual(parse_semver("2.1.0"), (2, 1, 0))
        self.assertEqual(parse_semver("v2.2.0"), (2, 2, 0))
        self.assertEqual(parse_semver("3.0"), (3, 0, 0))
        self.assertTrue(parse_semver("2.2.0") > parse_semver("2.1.0"))
        self.assertTrue(parse_semver("2.1.1") > parse_semver("2.1.0"))
        self.assertFalse(parse_semver("2.0.9") > parse_semver("2.1.0"))


if __name__ == "__main__":
    unittest.main()

