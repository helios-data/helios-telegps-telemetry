FROM python:3.13 AS builder

ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY --from=ghcr.io/astral-sh/uv:0.9.2 /uv /uvx /bin/

WORKDIR /app

# Copy dependency files and SDK; resolve without installing the project itself
COPY pyproject.toml ./
COPY helios-python-sdk/ ./helios-python-sdk/
RUN uv sync --no-install-project

# Copy source and do the final install
COPY src/ ./src/
RUN uv sync

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM python:3.13-slim

# direwolf pulls in libasound2 and its own dependencies automatically
RUN apt-get update && apt-get install -y --no-install-recommends \
    direwolf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.9.2 /uv /uvx /bin/
COPY --from=builder /app /app

COPY direwolf.conf /etc/direwolf/direwolf.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Defaults — override via env at runtime
ENV KISS_HOST=localhost
ENV KISS_PORT=8001
ENV AUDIO_DEVICE=auto
ENV MYCALL=VE7OKT

EXPOSE 5000

ENTRYPOINT ["/entrypoint.sh"]
CMD []
