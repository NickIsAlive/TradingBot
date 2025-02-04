# Mean Reversion Trading Bot

A fully automated trading bot that implements a mean reversion strategy using Bollinger Bands for US stocks via the Alpaca API. The bot includes real-time trade execution, risk management, and Telegram notifications.

## Features

- Mean reversion strategy using Bollinger Bands
- Real-time market data processing
- Automated trade execution via Alpaca API
- Risk management with stop-loss and take-profit
- Telegram notifications for trades and errors
- Comprehensive logging
- Market hours awareness

## Prerequisites

- Python 3.9 or higher
- Alpaca trading account (paper or live)
- Telegram bot token and chat ID
- TA-Lib installed on your system

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd trading-bot
```

2. Install TA-Lib (system dependency):

For macOS:
```bash
brew install ta-lib
```

For Ubuntu:
```bash
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit the `.env` file with your credentials and settings:
```
# Alpaca API Credentials
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Parameters
SYMBOLS=AAPL,MSFT,GOOGL
BOLLINGER_PERIOD=20
BOLLINGER_STD=2
STOP_LOSS_PCT=0.05
TAKE_PROFIT_PCT=0.05
POSITION_SIZE=0.1
```

## Usage

Run the bot:
```bash
python main.py
```

The bot will:
1. Check if the market is open
2. Process each configured symbol every 5 minutes
3. Calculate Bollinger Bands and generate trading signals
4. Execute trades based on the signals
5. Manage risk with stop-loss and take-profit orders
6. Send notifications via Telegram for all trades and errors
7. Log all activities to both console and file

## Risk Management

The bot implements the following risk management features:
- Stop-loss: Exits position if price drops 5% below entry
- Take-profit: Exits position if price rises 5% above entry
- Position sizing: Uses configured percentage of portfolio per trade
- Market hours: Only trades during US market hours

## Logging

Logs are written to `trading_bot.log` and include:
- Trade executions
- Signal generations
- Error messages
- Market status updates

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This trading bot is for educational purposes only. Use it at your own risk. The authors are not responsible for any financial losses incurred from using this software. 