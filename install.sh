#!/bin/bash
set -e

echo "=== X Media Downloader Installer ==="

python3 --version || { echo "Python 3 required"; exit 1; }

pip3 install -r requirements.txt

if [ ! -f config.yaml ]; then
    cp config.example.yaml config.yaml
    echo "Created config.yaml -- please edit it!"
fi

if [ ! -f twitter-cookies.txt ]; then
    echo ""
    echo "=== Cookie Setup ==="
    python3 setup-cookie.py
fi

echo ""
echo "Done! Next steps:"
echo "  1. Edit config.yaml with your Telegram bot_token and chat_id"
echo "  2. Test run: python3 -m src.main"
