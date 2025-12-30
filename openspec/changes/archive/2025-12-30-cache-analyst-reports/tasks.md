## 1. Core Logic
- [x] 1.1 Create `src/llm/report_manager.py` to handle saving/loading reports.
    - Schema: `{ "date": "YYYY-MM-DD", "language": "en|zh", "content": "..." }`
    - Storage: `data_cache/reports/YYYY-MM-DD_{lang}.json`
- [x] 1.2 Implement `save_report(date, lang, content)` and `load_report(date, lang)`.
- [x] 1.3 Implement `list_available_reports()` to find all dates with cached reports.

## 2. Dashboard Integration
- [x] 2.1 Add "Report History" section or modify "AI Macro Strategist Analysis" section.
- [x] 2.2 Add a date selector (default to Today) or a dropdown of available report dates.
- [x] 2.3 Logic:
    - IF date == Today AND not cached: Show "Generate" button.
    - IF date == Today AND cached: Show report + "Regenerate" button.
    - IF date != Today AND cached: Show report (read-only).
    - IF date != Today AND not cached: Show "No report available for this date."

## 3. Validation
- [x] 3.1 Verify reports are saved to disk with correct filename format.
- [x] 3.2 Verify switching languages loads the correct cached version (or prompts generation).
- [x] 3.3 Verify "Regenerate" overwrites the cache for today.
