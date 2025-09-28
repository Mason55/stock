# Dockerfile - Multi-stage build for improved portability
# Build stage
FROM python:3.11-slim-bookworm as builder

# Set build arguments
ARG INSTALL_ML=true

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cmake \
    libgomp1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements*.txt constraints.txt ./

# Install dependencies based on build arg
RUN if [ "$INSTALL_ML" = "true" ] ; then \
        pip install --no-cache-dir -r requirements.txt -c constraints.txt ; \
    else \
        pip install --no-cache-dir -r requirements-minimal.txt -c constraints.txt ; \
    fi

# Runtime stage
FROM python:3.11-slim-bookworm as runtime

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user with proper permissions
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app
USER appuser

# Environment variables for better portability
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_TO_FILE=false
ENV OFFLINE_MODE=false

# Expose port
EXPOSE 5000

# Improved health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/api/stocks/health || exit 1

# Start application
CMD ["python", "src/app.py"]