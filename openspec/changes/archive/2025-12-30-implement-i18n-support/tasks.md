## 1. Foundation
- [x] 1.1 Create `src/utils/i18n.py` module to handle translation dictionaries and language state.
- [x] 1.2 Define English and Chinese translation maps for existing UI static text.

## 2. Dashboard Integration
- [x] 2.1 Add language selection radio button/dropdown to the Streamlit sidebar.
- [x] 2.2 Update Streamlit UI components (titles, labels, captions) to use the i18n lookup function.
- [x] 2.3 Store selected language in `st.session_state`.

## 3. LLM Agent Update
- [x] 3.1 Update `MacroAnalyst.__init__` or `generate_report` to accept a `language` argument.
- [x] 3.2 Modify the system prompt in `src/llm/analyst.py` to include a language instruction (e.g., "Output your response in {language}").
- [x] 3.3 Pass the selected language from the dashboard to the `MacroAnalyst`.

## 4. Validation
- [x] 4.1 Verify UI text switches correctly between English and Chinese.
- [x] 4.2 Verify LLM generates reports in the selected language.
