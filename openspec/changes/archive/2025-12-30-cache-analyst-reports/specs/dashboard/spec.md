## ADDED Requirements
### Requirement: Report History
The dashboard MUST allow users to view previously generated analysis reports.

#### Scenario: View Past Report
- **WHEN** the user selects a past date from the report history selector
- **THEN** the system loads and displays the cached report for that date and current language
- **AND** hides the "Generate" button

### Requirement: Report Persistence
The dashboard MUST cache generated reports to prevent redundant API calls.

#### Scenario: Load Cached Report
- **WHEN** the dashboard loads
- **IF** a report exists for the current date and language
- **THEN** it is displayed automatically
- **AND** a "Regenerate" button is available

