import aiohttp
import logging
from config import ZEN_TOKEN # Предполагается наличие токена в .env

async def post_to_zen(title, body):
    """
    Публикация статьи в Дзен (черновик).
    Примечание: Требуется OAuth-токен и ID канала.
    """
    if not ZEN_TOKEN:
        logging.warning("Zen Token not found. Skipping Zen publication.")
        return False

    url = "https://api.zen.yandex.ru/api/v3/publisher/publications"
    headers = {
        "Authorization": f"Bearer {ZEN_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "type": "article",
        "title": title,
        "body": body, # Дзен принимает специфичный формат (разметку), здесь упрощенно
        "status": "draft"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                if resp.status in [200, 201]:
                    logging.info("Zen Draft created successfully.")
                    return True
                else:
                    logging.error(f"Zen API Error: {await resp.text()}")
                    return False
    except Exception as e:
        logging.error(f"Zen Integration Error: {e}")
        return False
