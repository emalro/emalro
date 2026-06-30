# syntax=docker/dockerfile:1.6

# --- Stage 1: builder ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt


# --- Stage 2: runtime ---
FROM python:3.11-slim AS runtime

WORKDIR /app

# System deps for asyncpg + bcrypt
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Install prebuilt wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy app source
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# Run as non-root
RUN useradd --create-home --shell /bin/bash emalro \
    && chown -R emalro:emalro /app
USER emalro

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
