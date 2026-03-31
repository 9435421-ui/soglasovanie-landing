import unittest
import sqlite3
import os
from database import init_db, save_lead, get_daily_leads
from config import DATABASE_PATH

class TestBotDatabase(unittest.TestCase):
    def setUp(self):
        # Используем временную базу для тестов
        self.test_db = "database/test_bot.db"
        import database
        database.DATABASE_PATH = self.test_db
        init_db()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_save_and_get_lead(self):
        save_lead(
            user_id=123,
            username="testuser",
            full_name="Test User",
            phone="+79991234567",
            module="quiz",
            city="Moscow",
            object_type="Квартира",
            details="Хочу снести стену",
            source="quiz_land"
        )

        leads = get_daily_leads()
        self.assertEqual(len(leads), 1)
        # leads table: id(0), user_id(1), username(2), full_name(3), phone(4), birthday(5), pd_consent(6), consent_date(7), module(8), city(9)
        self.assertEqual(leads[0][1], 123)
        self.assertEqual(leads[0][4], "+79991234567")
        self.assertEqual(leads[0][9], "Moscow")

if __name__ == "__main__":
    unittest.main()
