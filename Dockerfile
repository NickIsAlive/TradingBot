# Build stage
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Add universe repository and install build dependencies
RUN apt-get update && apt-get install -y software-properties-common \
    && add-apt-repository universe \
    && apt-get update && apt-get install -y \
    build-essential \
    wget \
    python3-dev \
    python3-pip \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Download and install TA-Lib
WORKDIR /tmp
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# Update library path
RUN echo "/usr/local/lib" > /etc/ld.so.conf.d/talib.conf && ldconfig

# Create and activate virtual environment
RUN python3 -m pip install virtualenv \
    && python3 -m virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip in virtual environment
RUN pip install --upgrade pip

# Set environment variables for ta-lib
ENV TA_INCLUDE_PATH=/usr/local/include
ENV TA_LIBRARY_PATH=/usr/local/lib

# Install Python packages with specific numpy version
COPY requirements.txt .
RUN pip install --no-cache-dir wheel setuptools \
    && pip install --no-cache-dir numpy==1.26.4 \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir ta-lib==0.4.28

# Final stage
FROM --platform=linux/amd64 ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m pip install --upgrade pip

# Copy TA-Lib files from builder
COPY --from=builder /usr/local/lib/libta_lib* /usr/local/lib/
COPY --from=builder /usr/local/include/ta-lib /usr/local/include/ta-lib

# Update library path in final stage
RUN echo "/usr/local/lib" > /etc/ld.so.conf.d/talib.conf && ldconfig

# Set environment variables
ENV TA_INCLUDE_PATH=/usr/local/include
ENV TA_LIBRARY_PATH=/usr/local/lib
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip in virtual environment
RUN pip install --upgrade pip

# Set working directory and copy application files
WORKDIR /app
COPY . .

# Expose the health check port
EXPOSE 8000

# Run the application
CMD ["python3", "main.py"] 