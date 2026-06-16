# Lighthouse Analytics — Production Docker Image
#
# Build:
#   docker build -t lighthouse-analytics .
#
# Run:
#   docker run -p 5001:5001 -v $(pwd)/saas/data:/app/saas/data lighthouse-analytics
#
# Or use docker-compose for the full stack.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Lighthouse Analytics"
LABEL org.opencontainers.image.description="Codebase Health Monitor — SaaS Platform"
LABEL org.opencontainers.image.version="0.3.0"

WORKDIR /app

# Install system deps only if needed (git for CHM analysis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY saas/requirements.txt /app/saas/
RUN pip install --no-cache-dir -r /app/saas/requirements.txt

# Install CHM CLI
COPY product/ /app/product/
RUN pip install --no-cache-dir /app/product/

# Copy SaaS app
COPY saas/ /app/saas/

# Copy website for static serving
COPY website/ /app/website/

# Create data directory
RUN mkdir -p /app/saas/data

EXPOSE 5001

ENV PORT=5001
ENV HOST=0.0.0.0
ENV FLASK_DEBUG=0

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health')" || exit 1

CMD ["python", "/app/saas/server.py"]
