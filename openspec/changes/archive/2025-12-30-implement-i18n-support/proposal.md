# Change: Implement Global i18n Support

## Why
Users need to access the application and generated insights in their preferred language (English or Chinese). This improves accessibility and usability for a wider audience.

## What Changes
- Adds a global language selector to the dashboard sidebar.
- Updates the LLM agent to accept a language parameter and generate reports in the selected language.
- Implements a lightweight i18n system for UI labels and static text.
- Defaults to English if no preference is selected.

## Impact
- **Specs**: `dashboard`, `llm-agent`
- **Code**: `src/llm/analyst.py`, `main.py` (or wherever the dashboard is defined), and new `src/utils/i18n.py`.

