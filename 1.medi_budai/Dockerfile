# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads output logs

# Set proper permissions
RUN chmod 755 uploads output logs

# Create non-root user for security
RUN useradd -m -u 1000 medibudai && chown -R medibudai:medibudai /app
USER medibudai

# Expose port
EXPOSE 5000

# Environment variables with defaults
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5000
ENV FLASK_ENV=production
ENV FLASK_DEBUG=False
ENV GUNICORN_WORKERS=4
ENV GUNICORN_THREADS=2
ENV GUNICORN_TIMEOUT=180

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Start the application with Gunicorn (production WSGI server).
# --threads lets each worker handle several concurrent slow requests
# (this app calls the OpenAI API per file, which is I/O bound) without
# needing one OS process per in-flight request.
# Shell form is used so the ENV vars above are expanded at container start.
CMD gunicorn \
    --bind 0.0.0.0:${FLASK_PORT} \
    --workers ${GUNICORN_WORKERS} \
    --threads ${GUNICORN_THREADS} \
    --timeout ${GUNICORN_TIMEOUT} \
    --access-logfile - \
    --error-logfile - \
    wsgi:application
