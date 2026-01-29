#!/bin/bash

# =================================================================
# Скрипт очистки сервера ТЕРИОН v2.0
# Удаляет старого бота, логи и оптимизирует текущее пространство
# =================================================================

# 1. Пути (настройте под ваш сервер)
PROJECT_DIR=$(pwd)
BACKUP_DIR="./backups"
DB_PATH="$PROJECT_DIR/database/terion.db"

echo "🚀 Начинаю очистку сервера..."

# 2. Создаем бэкап старого кода (на всякий случай)
mkdir -p $BACKUP_DIR
if [ -d "$PROJECT_DIR/old_bot" ]; then
    echo "📦 Архивирую старого бота..."
    tar -czf $BACKUP_DIR/old_bot_backup_$(date +%F).tar.gz -C $PROJECT_DIR old_bot
    echo "✅ Бэкап создан в $BACKUP_DIR"

    echo "🗑 Удаляю старого бота..."
    rm -rf $PROJECT_DIR/old_bot
fi

# 3. Очистка временных файлов
echo "🧹 Удаляю кэш Python (__pycache__)..."
find $PROJECT_DIR -type d -name "__pycache__" -exec rm -rf {} +

echo "🧹 Очищаю старые логи..."
find $PROJECT_DIR -name "*.log" -type f -delete

# 4. Оптимизация базы данных
if [ -f "$DB_PATH" ]; then
    echo "⚙️ Оптимизирую базу данных (VACUUM)..."
    python3 -c "import sqlite3; conn = sqlite3.connect('$DB_PATH'); conn.execute('VACUUM'); conn.close(); print('DB Optimized.')"
fi

# 5. Проверка места
echo -e "\n📊 Свободное место на диске:"
df -h /

echo -e "\n📂 Размер папки проекта:"
du -sh $PROJECT_DIR

echo -e "\n✨ Очистка завершена! Сервер готов к новому проекту."
