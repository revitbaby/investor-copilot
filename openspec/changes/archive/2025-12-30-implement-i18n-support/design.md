## Context
The application currently hardcodes English text in both the UI (Streamlit) and the LLM prompts. We need to support Chinese as a second language option.

## Goals
- Allow users to toggle between English (en) and Chinese (zh) at any time.
- Ensure the AI analyst produces content in the selected language.
- Keep the implementation lightweight (avoid complex gettext/babel setups if possible, given the small scope).

## Decisions
- **Decision**: Use a simple Python dictionary-based translation approach (`src/utils/i18n.py`).
    - **Rationale**: The app is small; `gettext` adds compilation steps and complexity not needed for <100 strings.
- **Decision**: Store language preference in `st.session_state["language"]`.
    - **Rationale**: Standard Streamlit pattern for session-scoped settings.
- **Decision**: Inject language instruction into LLM System Prompt.
    - **Rationale**: The LLM is capable of translation/generation in target languages natively; explicit instruction is more flexible than translating the output post-hoc.

## Risks / Trade-offs
- **Risk**: LLM might mix languages if the prompt isn't strong enough.
    - **Mitigation**: Use a clear "Output MUST be in [Language]" instruction in the system message.
- **Risk**: Hardcoded strings in code might be missed.
    - **Mitigation**: Manual sweep of `main.py` and `src/` to replace strings with `t(key)`.

## Open Questions
- Should we translate the specific financial terms (e.g., "Net Liquidity", "RRP") or keep them in English for precision? 
    - *Assumption*: Translate general terms, but keep standard acronyms (RRP, TGA, WALCL) as is, or provide bilingual labels where appropriate.

