# Run PfotenRegister

Run all commands from this folder:

```bash
cd PfotenRegister
```

## Start the app

Development database:

```bash
uv run dotenv -f config_dev.env run -- python run.py
```

TTOS database:

```bash
uv run dotenv -f config_ttos.env run -- python run.py
```

The app starts at:

```text
http://127.0.0.1:5000
```

## Database migrations

Check the current migration state:

```bash
uv run dotenv -f config_dev.env run -- alembic current
uv run dotenv -f config_ttos.env run -- alembic current
```

Apply migrations:

```bash
uv run dotenv -f config_dev.env run -- alembic upgrade head
uv run dotenv -f config_ttos.env run -- alembic upgrade head
```

Create a new migration:

```bash
uv run dotenv -f config_dev.env run -- alembic revision -m "describe_change"
```

Note: `alembic.ini` still contains the migration database URL. Check it before running migrations against TTOS, because yes, databases enjoy consequences.

## Tests

Run the test suite:

```bash
uv run pytest
```

Run only unit tests:

```bash
uv run pytest tests/unit
```

Run a specific test file:

```bash
uv run pytest tests/unit/test_reports.py
```
