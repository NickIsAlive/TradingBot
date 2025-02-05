#!/bin/bash

# Exit on error
set -e

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "doctl is not installed. Please install it first:"
    echo "brew install doctl  # For macOS"
    echo "Then authenticate with: doctl auth init"
    exit 1
fi

# Check if authenticated with DigitalOcean
if ! doctl account get &> /dev/null; then
    echo "Please authenticate with DigitalOcean first:"
    echo "doctl auth init"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Check required environment variables
required_vars=("ALPACA_API_KEY" "ALPACA_SECRET_KEY" "TELEGRAM_BOT_TOKEN" "TELEGRAM_CHAT_ID")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set in .env file"
        exit 1
    fi
done

# Create app if it doesn't exist
if ! doctl apps list | grep -q "trading-bot"; then
    echo "Creating new app on DigitalOcean..."
    doctl apps create --spec .do/app.yaml
else
    echo "Updating existing app..."
    APP_ID=$(doctl apps list --format ID --no-header | head -n 1)
    doctl apps update $APP_ID --spec .do/app.yaml
fi

echo "Deployment configuration complete!"
echo "Visit https://cloud.digitalocean.com/apps to monitor your deployment" 