# Cache Service

FastAPI service that builds payloads from two lists of strings and caches the results of a slow
external "transformer", so each distinct string is transformed only once.

## Quick start

```bash
docker compose up --build -d
docker compose exec api cache-cli -r 3 -j '{"list_1": ["first string", "second string"], "list_2": ["other string", "last string"]}'
```

Interactive API docs: http://localhost:8000/docs

## API

| Method | Path            | Responses                                                                    |
| ------ | --------------- | ---------------------------------------------------------------------------- |
| `POST` | `/payload`      | `201` new payload, `200` identical input seen before, `422` invalid input, `502` transformer failed |
| `GET`  | `/payload/{id}` | `200` generated payload, `404` unknown id                                     |
| `GET`  | `/health`       | `200` service and database are up                                             |

```bash
curl -X POST localhost:8000/payload -H 'content-type: application/json' \
  -d '{"list_1": ["first string", "second string", "third string"], "list_2": ["other string", "another string", "last string"]}'
# {"id": "7977d6ee-…", "message": "Payload created"}

curl localhost:8000/payload/7977d6ee-…
# {"output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"}
```

## CLI

```
cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [--help]
```

Each iteration creates the payload and reads it back, writing one JSON line:

```json
{"iteration": 1, "id": "7977d6ee-…", "created": true, "output": "FIRST STRING, …", "elapsed_ms": 521.2}
```

Exit codes: `0` success, `1` service error, `2` invalid arguments or input.
`-h` means `--host`, as in the spec, so help is `--help` only.

## How it works

- A payload is identified by a SHA-256 hash of both input lists. A known hash returns the stored
  id without calling the transformer.
- Otherwise the distinct strings are looked up in the `transformations` table with one query, and
  only the misses are sent to the transformer, concurrently and with a concurrency limit.
- Concurrent requests that miss the same string share one in-flight call. Inserts use
  `ON CONFLICT DO NOTHING`, so races between requests are harmless.
- If the transformer fails, the strings that succeeded stay cached and the request returns `502`.
  A retry only transforms the rest.
- The generated output is stored with the payload, so `GET` is a single primary-key read.

## Configuration

The service and the CLI read environment variables and an optional `.env` file; see
[`.env.example`](.env.example). Service keys use the `CACHE_SERVICE_` prefix and CLI keys use
`CACHE_CLI_`. Precedence: CLI flags, then environment, then `.env`, then defaults.

## Development

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn --factory cache_service.main:create_app --reload

.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy && .venv/bin/pytest --cov
```

Unit tests cover pure logic and argument parsing. Integration tests use a real SQLite file per
test, the app over ASGI, and the CLI against a live uvicorn server. The transformer is replaced
by a spy that counts calls, which is how the tests check call minimisation.

## Assumptions and shortcuts

- Payload ids are reused for identical inputs (same lists, same order), not for identical outputs.
- Payloads are stored in the database, not as files.
- Lists must be non-empty and of equal length, with at most 1,000 items of up to 1,000 characters
  each.
- The output is joined with `", "` as specified, which is ambiguous if an input contains `", "`.
- Tables are created at startup. A production setup would use Alembic migrations.
- One uvicorn worker: SQLite has a single writer, and in-flight calls are shared per process only.
- Cache entries never expire. Changing the transformer would need a version in the cache key.
- SQLite only: the repositories use SQLite's `INSERT ... ON CONFLICT`. PostgreSQL needs the
  `postgresql` dialect insert and `asyncpg`.
- No authentication or rate limiting.
