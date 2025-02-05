# ===============================
# Stage 1: Builder
# ===============================
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install required system dependencies, including wget
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    python3-pip \
    python3-venv \
    pkg-config \
    libgomp1 \
    curl \
    wget \
    git \
    unzip \
    autoconf \
    libtool \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib from source
WORKDIR /tmp
RUN wget -O ta-lib.tar.gz http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib.tar.gz \
    && cd ta-lib-0.4.0/ \
    && ./configure --prefix=/usr \
    && make -j$(nproc) --silent \
    && make install \
    && cd .. \
    && rm -rf ta-lib.tar.gz ta-lib-0.4.0/

# Ensure TA-Lib is linked correctly
RUN ldconfig

# Create a non-root user
RUN useradd -m trader
USER trader
WORKDIR /home/trader

# Create and activate a virtual environment
RUN python3 -m venv venv
ENV PATH="/home/trader/venv/bin:$PATH"

# Upgrade pip and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir wheel setuptools \
    && pip install --no-cache-dir numpy==1.26.4 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir ta-lib

# ===============================
# Stage 2: Final Image
# ===============================
FROM --platform=linux/amd64 ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies, including wget
RUN apt-get update && apt-get install -y \
    python3 \
    python3-venv \
    libgomp1 \
    curl \
    wget \
    git \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib from builder
COPY --from=builder /usr/lib/libta_lib.so* /usr/lib/
COPY --from=builder /usr/include/ta-lib /usr/include/ta-lib

# Ensure TA-Lib is correctly linked
RUN ldconfig

# Create a non-root user
RUN useradd -m trader
USER trader
WORKDIR /home/trader

# Copy Python virtual environment from builder
COPY --from=builder /home/trader/venv /home/trader/venv
ENV PATH="/home/trader/venv/bin:$PATH"

# Set working directory and copy application files
WORKDIR /home/trader/app
COPY --chown=trader:trader . .

# Expose the health check port
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]