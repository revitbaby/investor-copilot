## Context
Currently, reports are ephemeral and lost on page refresh. Users want to see historical analysis and avoid re-generating today's report if already done.

## Goals
- Persist reports to disk (`data_cache/reports/`).
- Enable browsing history.
- Reduce API costs by serving cached content.

## Decisions
- **Decision**: File-based JSON storage.
    - **Rationale**: Simple, human-readable, zero-dependency. Volume is low (1-2 files per day).
- **Decision**: Filename pattern `report_{date}_{lang}.json`.
    - **Rationale**: Easy to list and filter by language/date without parsing file content.
- **Decision**: Dashboard "Date" selector.
    - **Rationale**: Intuitive way to travel back in time.

## Risks / Trade-offs
- **Risk**: Cache invalidation if logic changes.
    - **Mitigation**: "Regenerate" button allows user to force update.
- **Risk**: Date timezone issues.
    - **Mitigation**: Use consistent UTC or server-local date for filenames (stick to `datetime.now().strftime("%Y-%m-%d")`).

## Open Questions
- Should we cache the input data (context) alongside the report?
    - *Yes*, beneficial for debugging and "why did it say that?" analysis. Add `context_data` field to JSON.

