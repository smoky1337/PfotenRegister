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

## Guest status API (draft)

`POST /api/v1/guest-status` accepts `{"code": "GUEST-CODE"}` and requires an
independent bearer token. Browser login does not grant API access. Codes refer to
`Guest.id`, not the displayed guest number; surrounding whitespace is ignored.

Generate a token and its SHA-256 hash locally:

```bash
python - <<'PY'
import hashlib
import secrets

token = secrets.token_urlsafe(32)
print("Client token (store securely):", token)
print("GUEST_STATUS_API_TOKEN_SHA256=" + hashlib.sha256(token.encode()).hexdigest())
PY
```

Store only `GUEST_STATUS_API_TOKEN_SHA256` in the server environment or the
selected, untracked `config_*.env` file and restart the application. Store the
original token in the calling application's server-side secret configuration.
Use HTTPS outside local development; keep tokens out of frontend code and logs.
An unset or malformed hash disables access with HTTP 503. Replace the configured
hash and restart all instances to rotate or revoke a token. This draft supports
one integration token and has no rate limiting or database migration.

For a partial rollout, omit this variable on services that should not expose the
API yet. Application startup, health checks, browser login and guest management
continue to work; only the guest status API returns HTTP 503. Set the hash only
on the Cloud Run services where the API should be enabled.

Example with `GUEST_STATUS_API_TOKEN` set in the calling shell:

```bash
curl --request POST https://your-pfotenregister-host/api/v1/guest-status \
  --header "Authorization: Bearer ${GUEST_STATUS_API_TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{"code":"GUEST-CODE"}'
```

Responses contain only `exists` and `active`:

| Guest | JSON response |
| --- | --- |
| Active | `{"exists":true,"active":true}` |
| Inactive or staging | `{"exists":true,"active":false}` |
| Unknown code | `{"exists":false,"active":null}` |

These results use HTTP 200. Missing/invalid tokens return 401 with a bearer
challenge; invalid JSON or an empty, non-string, or overlong code returns 400.
Codes may contain up to 255 characters after trimming. Responses use
`Cache-Control: no-store`. Errors contain a German `error` message; internal
exception details are not returned.

Run the API tests:

```bash
uv run pytest tests/integration/test_guest_status_api.py
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
