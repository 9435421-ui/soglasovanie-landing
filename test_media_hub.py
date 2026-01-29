import sqlite3
from datetime import datetime, timedelta
from config import DATABASE_PATH

def test_insertion():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    sched_time = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute("""
        INSERT INTO smart_calendar (rubric, title, body_tg, body_vk, body_zen, body_landing, status, scheduled_at)
        VALUES ('Тест', 'Тестовый пост', 'Текст ТГ', 'Текст ВК', 'Текст Дзен', 'Текст Сайт', 'scheduled', ?)
    """, (sched_time,))
    conn.commit()
    post_id = c.lastrowid
    print(f"Inserted post ID: {post_id} with scheduled_at: {sched_time}")

    c.execute("SELECT * FROM smart_calendar WHERE id=?", (post_id,))
    row = c.fetchone()
    conn.close()
    return row

if __name__ == "__main__":
    row = test_insertion()
    if row:
        print("Verification: Post found in DB.")
    else:
        print("Verification: Post NOT found.")
