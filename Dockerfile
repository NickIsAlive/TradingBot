# ===============================
# Stage 1: Builder
# ===============================
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    build-essential \
    python3-dev \
    python3-pip \
    python3-venv \
    pkg-config \
    libgomp1 \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Install precompiled TA-Lib (BYPASS BROKEN SOURCE BUILD)
WORKDIR /tmp
RUN wget https://github.com/TA-Lib/ta-lib/releases/download/ta-lib-0.4.0/ta-lib-0.4.0-linux-x86_64.zip \
    && unzip ta-lib-0.4.0-linux-x86_64.zip -d /usr/local/ \
    && rm ta-lib-0.4.0-linux-x86_64.zip

# Ensure TA-Lib is correctly linked
ENV LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"

# Create and activate virtual environment
RUN python3 -m pip install virtualenv \
    && python3 -m virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir wheel setuptools \
    && pip install --no-cache-dir numpy==1.26.4 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir ta-lib

# ===============================
# Stage 2: Final Image
# ===============================
FROM --platform=linux/amd64 ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Copy prebuilt TA-Lib from builder
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/include /usr/local/include

# Ensure TA-Lib is correctly linked
ENV LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"

# Copy Python virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory and copy application files
WORKDIR /app
COPY . .

# Expose the health check port
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]