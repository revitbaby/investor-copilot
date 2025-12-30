import unittest
import os
import json
import shutil
import sys
from datetime import datetime

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm.report_manager import ReportManager

class TestReportManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = "tests/data_cache/reports"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        self.manager = ReportManager(cache_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_and_load_report(self):
        date = "2025-01-01"
        lang = "en"
        content = "# Test Report"
        context = {"test": "data"}
        
        self.manager.save_report(date, lang, content, context)
        
        loaded = self.manager.load_report(date, lang)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["content"], content)
        self.assertEqual(loaded["language"], lang)
        self.assertEqual(loaded["date"], date)
        self.assertEqual(loaded["context_data"], context)

    def test_list_reports(self):
        self.manager.save_report("2025-01-01", "en", "Content 1")
        self.manager.save_report("2025-01-02", "zh", "Content 2")
        
        reports = self.manager.list_available_reports()
        self.assertEqual(len(reports), 2)
        
        # Verify sorting (descending date)
        self.assertEqual(reports[0]["date"], "2025-01-02")
        self.assertEqual(reports[0]["language"], "zh")

    def test_load_non_existent(self):
        loaded = self.manager.load_report("2099-01-01", "en")
        self.assertIsNone(loaded)

if __name__ == '__main__':
    unittest.main()

