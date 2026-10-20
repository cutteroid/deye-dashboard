# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory in container
WORKDIR /app

# Set environment variables
# Prevent Python from writing pyc files and buffering stdout/stderr
# TZ: outage schedules are in Kyiv local time; the container would otherwise run on UTC
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Kyiv

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY app.py .
COPY inverters/ ./inverters/
COPY telegram_bot.py .
COPY poems.py .
COPY outage_providers/ ./outage_providers/
COPY templates/ ./templates/
COPY static/ ./static/
COPY locales/ ./locales/
COPY storage.py .
COPY air_alerts.py .
COPY smart_meter.py .
COPY setup.py .
COPY discover_inverter.py .

# Create a non-root user for security.
# .env lives in the mounted data volume so config saved from the UI persists.
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/data && \
    ln -s /app/data/.env /app/.env && \
    chown -R appuser:appuser /app
USER appuser

# Expose port (Flask default + dashboard)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/api/data', timeout=5)"

# Run the Flask application
CMD ["python", "app.py"]
