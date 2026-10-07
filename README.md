# Cache Service

FastAPI microservice that generates payloads from two lists of strings and caches the results
of an external "transformer" service, so each distinct string is transformed only once.

## Run with Docker

```bash
cp .env.example .env    # optional
docker compose up --build -d

cache-cli -r 3 -j '{"list_1": ["first string"], "list_2": ["other string"]}'   # from the host
docker compose exec api cache-cli -j '{"list_1": ["a"], "list_2": ["b"]}'    # inside the container
```

The SQLite cache lives on the `cache-data` volume and survives restarts; `docker compose down -v`
removes it.

## Development

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env

.venv/bin/uvicorn --factory cache_service.main:create_app --reload
```

Checks:

```bash
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/mypy && .venv/bin/pytest
```
