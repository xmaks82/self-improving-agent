FROM python:3.12-slim

WORKDIR /app

# Copy all source files first
COPY pyproject.toml .
COPY src/ src/
COPY data/ data/

# Install dependencies
RUN pip install --no-cache-dir -e .

# Create directories for persistent data
RUN mkdir -p data/logs/conversations data/logs/improvements

# Environment variables (override in docker-compose or run command)
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Copy and setup entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
