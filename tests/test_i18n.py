import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.i18n import t, set_language, get_current_language, init_i18n, TRANSLATIONS
import streamlit as st

class TestI18n(unittest.TestCase):
    def setUp(self):
        # Mock streamlit session state
        if not hasattr(st, "session_state"):
            st.session_state = {}
        st.session_state["language"] = "en"

    def test_translation_en(self):
        set_language("en")
        self.assertEqual(t("title"), "Macro Liquidity AI Analyst")
        self.assertEqual(t("settings"), "Settings")

    def test_translation_zh(self):
        set_language("zh")
        self.assertEqual(t("title"), "宏观流动性 AI 分析师")
        self.assertEqual(t("settings"), "设置")

    def test_missing_key(self):
        set_language("en")
        self.assertEqual(t("non_existent_key"), "non_existent_key")

    def test_get_current_language(self):
        set_language("zh")
        self.assertEqual(get_current_language(), "zh")

if __name__ == '__main__':
    unittest.main()

