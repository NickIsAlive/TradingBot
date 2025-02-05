# Build stage
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies and TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    python3-dev \
    python3-pip \
    pkg-config \
    libta-lib-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install virtualenv \
    && python3 -m virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir wheel setuptools numpy \
    && pip install --no-cache-dir ta-lib \
    && pip install --no-cache-dir -r requirements.txt

# Final stage
FROM --platform=linux/amd64 ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    libgomp1 \
    libta-lib0 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory and copy application files
WORKDIR /app
COPY . .

# Expose the health check port
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"] 