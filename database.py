import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            module TEXT,
            city TEXT,
            object_type TEXT,
            details TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_lead(user_id, username, full_name, phone, module, city, object_type, details, source):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO leads (user_id, username, full_name, phone, module, city, object_type, details, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, full_name, phone, module, city, object_type, details, source))
    conn.commit()
    conn.close()

def get_daily_leads():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    # Получаем лиды за последние 24 часа
    cursor.execute("SELECT * FROM leads WHERE created_at >= datetime('now', '-1 day')")
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("База данных инициализирована.")
