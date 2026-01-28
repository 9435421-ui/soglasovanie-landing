import aiohttp
import logging
from config import VK_ACCESS_TOKEN, VK_GROUP_ID

async def post_to_vk(message: str, image_url: str = None):
    """Публикация записи на стену сообщества ВК."""
    if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
        logging.error("VK Credentials missing")
        return False

    url = "https://api.vk.com/method/wall.post"
    params = {
        "owner_id": f"-{VK_GROUP_ID}",
        "from_group": 1,
        "message": message,
        "access_token": VK_ACCESS_TOKEN,
        "v": "5.131"
    }

    if image_url:
        # В полноценной версии здесь должна быть загрузка фото на сервер ВК
        # Для начала просто постим текст
        pass

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, params=params) as resp:
                result = await resp.json()
                if "response" in result:
                    logging.info(f"VK Post success: {result['response']['post_id']}")
                    return True
                else:
                    logging.error(f"VK Post error: {result}")
                    return False
    except Exception as e:
        logging.error(f"VK API error: {e}")
        return False
