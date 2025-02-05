# Use a minimal base image
FROM ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
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
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

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
    && pip install --no-cache-dir -r requirements.txt

# Set working directory and copy application files
WORKDIR /home/trader/app
COPY --chown=trader:trader . .

# Expose the health check port
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"]