# syntax=docker/dockerfile:1

FROM python:3.12-slim AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip pip install .

FROM python:3.12-slim
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CACHE_SERVICE_DATABASE_URL=sqlite+aiosqlite:////data/cache.db
RUN useradd --create-home --uid 1000 app && mkdir /data && chown app:app /data
COPY --from=build /opt/venv /opt/venv
USER app
WORKDIR /home/app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
# One worker: SQLite has a single writer and in-flight transformer calls are shared per process.
CMD ["uvicorn", "--factory", "cache_service.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
