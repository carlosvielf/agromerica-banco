##############################################
# Multi-stage Dockerfile for Agromerica API
# - builder stage: builds wheels for Python deps to maximize cache and avoid recompiles
# - final stage: minimal runtime image with a non-root user
# Notes:
#  * We generate wheels in the builder so that final image installation is faster
#  * Keep model files (best.pt) in the image OR mount them at runtime via volume
#  * .dockerignore is used to avoid copying large runtime artifacts (results/uploads)
##############################################

# --------------------
# Stage 1: builder
# --------------------
FROM python:3.10-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive

# Install build tools required to produce wheels for some packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    wget \
    ca-certificates \
    git \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
    ffmpeg \
    libsndfile1 \
    libatlas3-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels

# Copy only requirements first to maximize layer cache when source code changes
COPY requirements.txt .

# Use pip to build wheels for all requirements into /wheels
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt


# --------------------
# Stage 2: runtime
# --------------------
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV PATH="/root/.local/bin:${PATH}"

# Create a non-root user and group for running the app
RUN groupadd -r appgroup && useradd -r -g appgroup -m -u 1000 appuser

# Install runtime OS deps (minimal set)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgomp1 \
    ffmpeg \
    libsndfile1 \
    libatlas3-base \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built wheels from builder and install packages from them.
COPY --from=builder /wheels /wheels
COPY requirements.txt .

# Install Python deps from local wheels to avoid recompiling heavy packages.
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application code after installing dependencies (helps cache)
# .dockerignore prevents copying large runtime artifacts like results/uploads
COPY . /app

# Ensure upload/result folders exist and are writable by the non-root user
RUN mkdir -p /app/static/uploads /app/static/results && \
    chown -R appuser:appgroup /app/static/uploads /app/static/results /app/models /app

# Default env vars (overridable at runtime)
ENV PORT=5052
ENV WORKERS=2

# Document exposed port (binds to ${PORT})
EXPOSE ${PORT}

# Switch to non-root user
USER appuser

# Use gunicorn as the production WSGI server
# - gthread worker-class is a reasonable default for IO-bound workloads
# - WORKERS should be tuned in production (e.g. 2-4 per CPU core depending on memory)
ENTRYPOINT ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers ${WORKERS} --worker-class gthread app:app"]
