import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# Группы и каналы
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", 0))
NOTIFICATIONS_CHANNEL_ID = int(os.getenv("NOTIFICATIONS_CHANNEL_ID", 0))
CONTENT_CHANNEL_ID = int(os.getenv("CONTENT_CHANNEL_ID", 0))

# Темы (Threads)
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", 0))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", 0))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", 0))

# AI
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# DB
DATABASE_PATH = "database/bot.db"
