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
    echo "❌ Error: .env file not found"
    exit 1
fi

# Check required environment variables
required_vars=(
    "ALPACA_API_KEY"
    "ALPACA_SECRET_KEY"
    "ALPACA_BASE_URL"
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_CHAT_ID"
    "MAX_POSITIONS"
    "POSITION_SIZE"
    "MAX_POSITION_PCT"
    "INITIAL_STOP_LOSS_PCT"
    "TRAILING_STOP_PCT"
    "TRAILING_GAIN_PCT"
    "MIN_PERIOD"
    "MAX_PERIOD"
    "MIN_STD"
    "MAX_STD"
    "MIN_PRICE"
    "MAX_PRICE"
    "MIN_VOLUME"
    "MIN_VOLATILITY"
    "SCREEN_INTERVAL"
    "MIN_DOLLAR_VOLUME"
    "MAX_SPREAD_PCT"
    "MIN_AVG_VOLUME"
    "VOLUME_RATIO_THRESHOLD"
    "CHECK_INTERVAL"
    "LOG_LEVEL"
    "LOG_FILE"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: $var is not set in .env file"
        exit 1
    fi
done

# Deploy or update the application
echo "📦 Deploying application..."
APP_ID=$(doctl apps list --format ID,Spec.Name --no-header | grep trading-bot | awk '{print $1}')

if [ -n "$APP_ID" ]; then
    echo "🔄 Updating existing app (ID: $APP_ID)..."
    
    # Update secrets
    echo "🔐 Updating secrets..."
    doctl apps update $APP_ID --set-secret ALPACA_API_KEY="$ALPACA_API_KEY"
    doctl apps update $APP_ID --set-secret ALPACA_SECRET_KEY="$ALPACA_SECRET_KEY"
    doctl apps update $APP_ID --set-secret TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
    doctl apps update $APP_ID --set-secret TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID"
    
    # Update app specification
    doctl apps update $APP_ID --spec .do/app.yaml
else
    echo "🆕 Creating new app..."
    # Create app with initial secrets
    doctl apps create --spec .do/app.yaml \
        --set-secret ALPACA_API_KEY="$ALPACA_API_KEY" \
        --set-secret ALPACA_SECRET_KEY="$ALPACA_SECRET_KEY" \
        --set-secret TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
        --set-secret TELEGRAM_CHAT_ID="$TELEGRAM_CHAT_ID"
fi

echo "✅ Deployment initiated!"
echo "You can monitor the deployment status in the DigitalOcean dashboard"
echo "or by running: doctl apps list"

# Wait for deployment to complete
echo "⏳ Waiting for deployment to complete..."
sleep 30

# Check deployment status
if [ -n "$APP_ID" ]; then
    STATUS=$(doctl apps get $APP_ID --format Status --no-header)
    echo "📊 Deployment status: $STATUS"
    
    if [ "$STATUS" = "running" ]; then
        echo "✅ Deployment successful!"
    else
        echo "⚠️ Deployment status is: $STATUS"
        echo "Please check the DigitalOcean dashboard for more details."
    fi
fi 