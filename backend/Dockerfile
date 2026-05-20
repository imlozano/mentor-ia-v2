# syntax=docker/dockerfile:1.7

# ----- Builder -----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.14

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# ----- Runtime -----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Parche de CVEs HIGH en setuptools/wheel vendored del base image:
#   - CVE-2026-23949 jaraco.context <6.1.0 (path traversal en tar)
#   - CVE-2026-24049 wheel <0.46.2 (RCE vía wheel malicioso)
# No son explotables en este contenedor (no procesa tars/wheels del usuario),
# pero Trivy las reporta y queremos imagen limpia. Reusamos uv del builder
# para mantener coherencia (el proyecto gestiona deps Python con uv, no pip).
COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
RUN uv pip install --system --no-cache --upgrade \
        'setuptools>=80' 'wheel>=0.46.2'

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app src ./src

USER app

EXPOSE 8000

CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
