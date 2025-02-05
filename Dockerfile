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

# Install TA-Lib version 0.6.4 from GitHub
WORKDIR /tmp
RUN wget https://github.com/ta-lib/ta-lib/archive/refs/tags/v0.6.4.tar.gz \
    && tar -xzf v0.6.4.tar.gz \
    && cd ta-lib-0.6.4 \
    && autoreconf -fi \  # Generate the configure script
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.6.4 v0.6.4.tar.gz

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