# Testing Guide

## Setup

Using uv:
```bash
uv sync --extra test
```

Using pip:
```bash
pip install -r requirements.txt -r requirements-test.txt
```

## Running Tests

```bash
pytest
```

With coverage:
```bash
pytest --cov=app --cov-report=term-missing
```

## Environment

- Tests use an in-memory SQLite database by default.
- GCS is disabled in tests.
- If you need to point tests at a different database, pass a custom `SQLALCHEMY_DATABASE_URI` via `create_app` in a local fixture.

## Legacy Tests

Existing tests are kept under `tests/legacy` and are excluded from default runs.
