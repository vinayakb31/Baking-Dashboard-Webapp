FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy app code
COPY . .

# Install dependencies explicitly
# We upgrade pip first to ensure compatibility, then install gunicorn and other requirements
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir gunicorn
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Cloud Run and Render
ENV PORT 8080

# Use the full path for gunicorn to avoid "not found" errors
CMD exec /usr/local/bin/gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 --log-level=debug cookies_webapp:app
