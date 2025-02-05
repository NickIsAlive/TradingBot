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

# Download and install TA-Lib
WORKDIR /tmp
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.4.0-src.tar.gz

# Update library cache and set up environment
ENV LD_LIBRARY_PATH=/usr/lib:/usr/local/lib:$LD_LIBRARY_PATH
RUN ldconfig

# Create and activate virtual environment
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install virtualenv \
    && python3 -m virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir wheel setuptools numpy \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --global-option=build_ext --global-option="-L/usr/lib/" --global-option="-L/usr/local/lib/" ta-lib

# Final stage
FROM --platform=linux/amd64 ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    python3-dev \
    python3 \
    libgomp1 \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib in final stage
WORKDIR /tmp
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# Set up environment and update library cache
ENV LD_LIBRARY_PATH=/usr/lib:/usr/local/lib:$LD_LIBRARY_PATH
RUN ldconfig

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