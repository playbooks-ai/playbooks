# Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements files first
COPY website/api/requirements.txt api/requirements.txt
COPY python/requirements.txt python/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r api/requirements.txt \
    && pip install --no-cache-dir -r python/requirements.txt

# Development stage
FROM builder as development

# Copy the application code
COPY website/api api/
COPY python python/

ENV PYTHONPATH=/app
ENV ENVIRONMENT=development

CMD ["python", "-m", "api.main"]

# Production stage
FROM python:3.11-slim as production

WORKDIR /app

# Copy only the necessary files from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /app/api /app/api
COPY --from=builder /app/python /app/python

ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

CMD ["python", "-m", "api.main"]
