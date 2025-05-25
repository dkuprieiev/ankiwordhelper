#!/bin/bash
set -e

# Docker entrypoint script for Anki Telegram Bot

echo "Starting Anki Telegram Bot..."

# Check if required environment variables are set
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN is not set!"
    exit 1
fi

if [ -z "$AUTH_CODE" ]; then
    echo "WARNING: AUTH_CODE is not set. Generating a random one..."
    export AUTH_CODE=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
    echo "Generated AUTH_CODE: $AUTH_CODE"
    echo "Please save this code to authenticate with the bot!"
fi

# Wait for services to be ready
echo "Waiting for Ollama service..."
while ! curl -s http://ollama:11434/api/tags > /dev/null; do
    sleep 2
done
echo "Ollama is ready!"

echo "Waiting for Anki service..."
while ! curl -s http://anki:8765 > /dev/null; do
    sleep 2
done
echo "Anki is ready!"

# Start the bot
echo "Starting bot..."
exec python main.py