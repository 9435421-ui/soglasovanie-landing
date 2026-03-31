import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

# VK
VK_ACCESS_TOKEN = os.getenv("VK_ACCESS_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
ZEN_TOKEN = os.getenv("ZEN_TOKEN")

# AI (OpenRouter)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Channels & Groups
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", 0))
CONTENT_CHANNEL_ID = int(os.getenv("CONTENT_CHANNEL_ID", 0))

# Thread IDs
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", 2))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", 5))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", 8))
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", 88))

# DB
DATABASE_PATH = "database/terion.db"
KNOWLEDGE_BASE_PATH = "knowledge_base/"
