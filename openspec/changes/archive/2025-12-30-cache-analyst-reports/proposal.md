# Change: Cache Analyst Reports

## Why
Users want to review past daily reports without regenerating them (saving LLM costs and time). The system should cache generated reports locally by date and allow selecting past dates to view.

## What Changes
- Implement a JSON-based local cache for LLM reports, keyed by date and language.
- Update the Dashboard to show a date selector for "Report Date".
- If a report exists for the selected date/language, load it. If not, show "Generate" button (only for today) or "No report found" (for past days).
- Add "Regenerate" option for today's report even if cached.

## Impact
- **Specs**: `dashboard`, `llm-agent`
- **Code**: `src/llm/report_manager.py` (new), `src/ui/app.py`.

