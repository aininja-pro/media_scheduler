FROM python:3.12-slim

# Set work directory
WORKDIR /app

# Install system dependencies - try without gcc first
# RUN apt-get update && apt-get install -y --fix-missing \
#     gcc \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
# Use shell form to allow environment variable substitution for PORT
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}