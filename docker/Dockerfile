# Zarnitsa API container — runtime image
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data

# Install package
RUN uv pip install --system --no-cache-dir -e ".[offline]"

EXPOSE 8000

ENV ZARNITSA_HOST=0.0.0.0
ENV ZARNITSA_PORT=8000

CMD ["zarnitsa", "serve"]
