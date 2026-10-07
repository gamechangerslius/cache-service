# Cache Service

FastAPI microservice that generates payloads from two lists of strings and caches the results
of an external "transformer" service, so each distinct string is transformed only once.

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
