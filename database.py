import sqlite3
import os
from datetime import datetime
from config import DATABASE_PATH

def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Таблица лидов (пользователей)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            birthday TEXT, -- Формат DD.MM
            pd_consent INTEGER DEFAULT 0, -- Согласие на обработку ПД
            consent_date TIMESTAMP, -- Дата согласия
            module TEXT,
            city TEXT,
            object_type TEXT,
            details TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица контент-плана (устаревшая, но оставим для совместимости)
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

    # Новая таблица: Умный календарь (Медиа-Хаб)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS smart_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rubric TEXT,
            title TEXT,
            body_tg TEXT,
            body_vk TEXT,
            body_zen TEXT,
            body_landing TEXT,
            image_url TEXT,
            status TEXT DEFAULT 'draft', -- draft, generated, approved, scheduled, published
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

def save_lead(user_id, username, full_name, phone, module, city, object_type, details, source, pd_consent=1, consent_date=None):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO leads (user_id, username, full_name, phone, module, city, object_type, details, source, pd_consent, consent_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, full_name, phone, module, city, object_type, details, source, pd_consent, consent_date))
    conn.commit()
    conn.close()

def add_content_draft(title, body, platform='both'):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO content_plan (title, body, platform) VALUES (?, ?, ?)', (title, body, platform))
    conn.commit()
    conn.close()

def add_smart_post(rubric, title, body_tg, body_vk, body_zen, body_landing, image_url=None):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO smart_calendar (rubric, title, body_tg, body_vk, body_zen, body_landing, image_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (rubric, title, body_tg, body_vk, body_zen, body_landing, image_url))
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id

def get_latest_news(limit=3):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT title, body_landing, created_at FROM smart_calendar
        WHERE status = 'published' ORDER BY created_at DESC LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def optimize_db():
    """Сжатие базы данных для освобождения места"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.execute("VACUUM")
    conn.close()
    print(f"Database {DATABASE_PATH} optimized.")

def get_birthday_users(day_month):
    """day_month: string "DD.MM" """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, full_name FROM leads WHERE birthday = ?", (day_month,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_user_birthday(user_id, birthday):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET birthday = ? WHERE user_id = ?", (birthday, user_id))
    conn.commit()
    conn.close()

def get_all_leads(limit=50):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM leads WHERE created_at >= datetime('now', 'start of day')")
    leads_today = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM smart_calendar WHERE status = 'published'")
    active_posts = cursor.fetchone()[0]
    conn.close()
    return {
        "leadsToday": leads_today,
        "activePosts": active_posts,
        "conversion": "15%" # Заглушка, можно считать реально
    }

def get_pending_content():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM content_plan WHERE status = 'draft'")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_scheduled_posts():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, body_tg, body_vk, body_zen, body_landing, image_url
        FROM smart_calendar
        WHERE status = 'scheduled' AND scheduled_at <= CURRENT_TIMESTAMP
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_smart_post_status(post_id, status):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE smart_calendar SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    conn.close()

def get_all_smart_posts(limit=20):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM smart_calendar ORDER BY created_at DESC LIMIT ?", (limit,))
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
