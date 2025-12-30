import os
import json
from datetime import datetime
from typing import Optional, List, Dict

class ReportManager:
    def __init__(self, cache_dir: str = "data_cache/reports"):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def _get_filename(self, date: str, lang: str) -> str:
        """
        Generate filename from date and language.
        Format: YYYY-MM-DD_{lang}.json
        """
        return os.path.join(self.cache_dir, f"{date}_{lang}.json")

    def save_report(self, date: str, lang: str, content: str, context_data: Optional[Dict] = None) -> None:
        """
        Save a generated report to disk.
        """
        data = {
            "date": date,
            "language": lang,
            "content": content,
            "context_data": context_data,
            "timestamp": datetime.now().isoformat()
        }
        
        filename = self._get_filename(date, lang)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_report(self, date: str, lang: str) -> Optional[Dict]:
        """
        Load a report from disk if it exists.
        """
        filename = self._get_filename(date, lang)
        if not os.path.exists(filename):
            return None
            
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading report {filename}: {e}")
            return None

    def list_available_reports(self) -> List[Dict[str, str]]:
        """
        List all available reports.
        Returns list of dicts: {"date": "YYYY-MM-DD", "language": "en"}
        """
        reports = []
        if not os.path.exists(self.cache_dir):
            return reports

        for filename in os.listdir(self.cache_dir):
            if not filename.endswith(".json"):
                continue
                
            # Parse filename: YYYY-MM-DD_lang.json
            try:
                name_part = filename[:-5] # remove .json
                parts = name_part.split('_')
                if len(parts) >= 2:
                    date_str = parts[0]
                    lang = parts[1]
                    reports.append({"date": date_str, "language": lang})
            except Exception:
                continue
                
        # Sort by date descending
        reports.sort(key=lambda x: x["date"], reverse=True)
        return reports

