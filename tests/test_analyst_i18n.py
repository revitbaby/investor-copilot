import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.llm.analyst import MacroAnalyst

class TestAnalystI18n(unittest.TestCase):
    @patch('src.llm.analyst.ChatOpenAI')
    def test_generate_report_passes_language(self, mock_chat_openai):
        # Mock LLM and Chain
        mock_llm_instance = MagicMock()
        mock_chat_openai.return_value = mock_llm_instance
        
        analyst = MacroAnalyst()
        # Mock the chain
        analyst.chain = MagicMock()
        
        context = {"test": "data"}
        
        # Test English default
        analyst.generate_report(context, language="en")
        args, _ = analyst.chain.invoke.call_args
        self.assertEqual(args[0]['language'], "English")
        
        # Test Chinese
        analyst.generate_report(context, language="zh")
        args, _ = analyst.chain.invoke.call_args
        self.assertEqual(args[0]['language'], "Chinese (Simplified)")

if __name__ == '__main__':
    unittest.main()

