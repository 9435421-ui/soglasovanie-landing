#!/bin/bash
SERVER_IP="176.124.219.183"
SERVER_USER="root"
REMOTE_DIR="/root/PARKHOMENKO_BOT"
if [ -z "$SERVER_PASS" ]; then
    echo "❌ SERVER_PASS not set"
    exit 1
fi
echo "🚀 Syncing files..."
sshpass -p "$SERVER_PASS" rsync -avz --exclude '.git' --exclude 'database/*.db' --exclude '.env' --exclude '__pycache__' ./ $SERVER_USER@$SERVER_IP:$REMOTE_DIR
echo "🛠 Remote setup..."
sshpass -p "$SERVER_PASS" ssh $SERVER_USER@$SERVER_IP << EOF
    cd $REMOTE_DIR
    python3 migrate_db.py || true
    pm2 restart terion-bot
EOF
echo "✨ Done."
