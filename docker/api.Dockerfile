FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY api/requirements.txt api/requirements.txt
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install -r api/requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Run the API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
