import os
import sys
from dotenv import load_dotenv

def check():
    print("🔍 Проверка готовности ТЕРИОН v2.0 к запуску...")

    if not os.path.exists(".env"):
        print("❌ ОШИБКА: Файл .env не найден! Создайте его из .env.example.")
        return False

    load_dotenv()

    required_keys = ["BOT_TOKEN", "OPENROUTER_API_KEY", "ADMIN_ID"]
    missing = []

    for key in required_keys:
        val = os.getenv(key)
        if not val or "your_" in val:
            missing.append(key)

    if missing:
        print(f"❌ ОШИБКА: Не заполнены ключи в .env: {', '.join(missing)}")
        return False

    print("✅ Все ключи на месте. Можно запускать!")
    return True

if __name__ == "__main__":
    if check():
        sys.exit(0)
    else:
        sys.exit(1)
