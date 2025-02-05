#!/bin/bash

# Ensure script stops on first error
set -e

echo "🚀 Deploying Trading Bot to DigitalOcean..."

# Check if doctl is installed
if ! command -v doctl &> /dev/null; then
    echo "❌ Error: doctl is not installed!"
    echo "Please install the DigitalOcean CLI first:"
    echo "https://docs.digitalocean.com/reference/doctl/how-to/install/"
    exit 1
fi

# Check if authenticated with DigitalOcean
if ! doctl account get &> /dev/null; then
    echo "❌ Error: Not authenticated with DigitalOcean!"
    echo "Please run: doctl auth init"
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

# Deploy or update the application
echo "📦 Deploying application..."
APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | grep trading-bot | awk '{print $1}')

if [ -n "$APP_ID" ]; then
    echo "🔄 Updating existing app (ID: $APP_ID)..."
    doctl apps update $APP_ID --spec .do/app.yaml
else
    echo "🆕 Creating new app..."
    doctl apps create --spec .do/app.yaml
fi

echo "✅ Deployment initiated!"
echo "You can monitor the deployment status in the DigitalOcean dashboard"
echo "or by running: doctl apps list" 