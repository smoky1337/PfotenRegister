# Test Guidelines

## Structure
- `tests/unit`: pure logic and helper functions
- `tests/integration`: database + Flask client, no external services
- `tests/e2e`: high-level smoke flows

## Naming
- Files: `test_<area>_<behavior>.py`
- Tests: `test_<behavior>_expected_<result>`

## Rules
- Keep tests deterministic; use `freezegun` for dates.
- Use factories for data creation; never rely on pre-existing records.
- Avoid network calls; mock external services.
- Assert both status codes and key response content.
- Keep tests focused: one behavior per test.

## Fixtures
- Prefer function-scoped fixtures unless setup is expensive.
- Avoid global state and order dependencies.
