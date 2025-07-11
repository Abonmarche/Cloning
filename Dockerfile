# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by arcgis library
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libgdal-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create json_files directory for output
RUN mkdir -p json_files

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Cloud Run sets the PORT environment variable
# Default to 8080 if not set
ENV PORT=8080

# Use gunicorn as the production WSGI server
# --bind 0.0.0.0:$PORT - Bind to all interfaces on the PORT
# --workers 1 - Start with 1 worker (can be increased if needed)
# --threads 8 - Use 8 threads per worker
# --timeout 0 - No timeout for long-running cloning operations
# --access-logfile - - Log to stdout
# --error-logfile - - Log errors to stderr
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 --access-logfile - --error-logfile - web_interface.app:app