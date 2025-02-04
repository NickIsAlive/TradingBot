#!/bin/bash

# Ensure script stops on first error
set -e

echo "🔨 Building Trading Bot..."

# Create necessary directories
mkdir -p logs

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Build and start containers
echo "🐳 Building Docker containers..."
docker compose build --no-cache

echo "🚀 Starting services..."
docker compose up -d

echo "📝 Checking logs..."
docker compose logs -f 