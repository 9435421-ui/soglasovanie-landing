#!/bin/bash
PROJECT_DIR=$(pwd)
BACKUP_DIR="./backups"
DB_PATH="$PROJECT_DIR/database/terion.db"
echo "🚀 Начинаю очистку сервера..."
mkdir -p $BACKUP_DIR
if [ -d "$PROJECT_DIR/old_bot" ]; then
    tar -czf $BACKUP_DIR/old_bot_backup_$(date +%F).tar.gz -C $PROJECT_DIR old_bot
    rm -rf $PROJECT_DIR/old_bot
fi
find $PROJECT_DIR -type d -name "__pycache__" -exec rm -rf {} +
find $PROJECT_DIR -name "*.log" -type f -delete
if [ -f "$DB_PATH" ]; then
    python3 -c "import sqlite3; conn = sqlite3.connect('$DB_PATH'); conn.execute('VACUUM'); conn.close(); print('DB Optimized.')"
fi
echo -e "\n✨ Очистка завершена!"
