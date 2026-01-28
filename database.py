import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Таблица лидов
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

    # Таблица контент-плана
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            body TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'draft', -- draft, approved, published
            platform TEXT, -- tg, vk, both
            scheduled_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица разведчика (парсинг)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scouting_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform_user_id TEXT,
            platform TEXT,
            group_name TEXT,
            activity_type TEXT,
            scouted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def add_content_draft(title, body, platform='both'):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO content_plan (title, body, platform) VALUES (?, ?, ?)', (title, body, platform))
    conn.commit()
    conn.close()

def get_pending_content():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM content_plan WHERE status = 'draft'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_daily_leads():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE created_at >= datetime('now', '-1 day')")
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("База данных ТЕРИОН v2.0 инициализирована.")
