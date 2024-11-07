FROM python:3.11-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Create Python virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

# Copy only necessary files from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install only runtime dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    netcat-traditional \
    postgresql-client \
    libjpeg62-turbo \
    libpng16-16 \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Create media directory with proper permissions
RUN mkdir -p /app/media/attachments && chmod -R 777 /app/media

# Copy entrypoint script first and fix permissions
COPY entrypoint.sh /app/
RUN dos2unix /app/entrypoint.sh 
RUN chmod +x /app/entrypoint.sh

# Copy project files
COPY . /app/

CMD ["/bin/bash", "/app/entrypoint.sh"]