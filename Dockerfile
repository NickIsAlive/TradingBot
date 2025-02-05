# Build stage
FROM --platform=linux/amd64 ubuntu:22.04 AS builder

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    python3-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Download and install TA-Lib
WORKDIR /tmp
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xvzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib/ \
    && ./configure --prefix=/usr \
    && make \
    && make install

# Ensure the library is in the correct location and update cache
RUN cp /usr/lib/libta_lib* /usr/lib/x86_64-linux-gnu/ \
    && ldconfig

# Create and activate virtual environment
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install virtualenv \
    && python3 -m virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set environment variables for TA-Lib installation
ENV TA_INCLUDE_PATH=/usr/include/ta-lib
ENV TA_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir numpy \
    && pip install --no-cache-dir -r requirements.txt

# Final stage
FROM --platform=linux/amd64 ubuntu:22.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Copy TA-Lib libraries and files from builder
COPY --from=builder /usr/lib/x86_64-linux-gnu/libta_lib* /usr/lib/x86_64-linux-gnu/
COPY --from=builder /usr/include/ta-lib /usr/include/ta-lib

# Set environment variables for TA-Lib
ENV TA_INCLUDE_PATH=/usr/include/ta-lib
ENV TA_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu

# Run ldconfig to update the shared library cache
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