import aiohttp
import logging
import asyncio
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

async def get_vk_user_info(user_id: int):
    """Получение имени и ссылки на профиль пользователя ВК."""
    if not VK_ACCESS_TOKEN:
        return None

    url = "https://api.vk.com/method/users.get"
    params = {
        "user_ids": user_id,
        "fields": "photo_max",
        "access_token": VK_ACCESS_TOKEN,
        "v": "5.131"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                result = await resp.json()
                if "response" in result and len(result["response"]) > 0:
                    user = result["response"][0]
                    return {
                        "full_name": f"{user['first_name']} {user['last_name']}",
                        "profile_url": f"https://vk.com/id{user_id}",
                        "photo": user.get("photo_max")
                    }
    except Exception as e:
        logging.error(f"VK Info error: {e}")
    return None

async def vk_listener_loop(bot_instance):
    """Слушатель сообщений ВК через LongPoll для захвата лидов."""
    if not VK_ACCESS_TOKEN or not VK_GROUP_ID:
        logging.warning("VK Listener: Credentials missing, skipping.")
        return

    from database import save_lead
    from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY

    logging.info("VK Listener started.")

    async with aiohttp.ClientSession() as session:
        # 1. Получаем сервер LongPoll
        lp_url = "https://api.vk.com/method/groups.getLongPollServer"
        lp_params = {"group_id": VK_GROUP_ID, "access_token": VK_ACCESS_TOKEN, "v": "5.131"}

        try:
            async with session.get(lp_url, params=lp_params) as resp:
                lp_data = await resp.json()
                if 'response' not in lp_data:
                    logging.error(f"VK LongPoll Error: {lp_data}")
                    return
                server = lp_data['response']['server']
                key = lp_data['response']['key']
                ts = lp_data['response']['ts']
        except Exception as e:
            logging.error(f"VK LongPoll Init Error: {e}")
            return

        while True:
            try:
                # В ВК LongPoll для групп используется https
                async with session.get(f"{server}?act=a_check&key={key}&ts={ts}&wait=25") as resp:
                    update = await resp.json()
                    if 'failed' in update:
                        # Обработка истечения ключа или TS
                        logging.warning(f"VK LongPoll Failed: {update}")
                        break # Проще перезапустить цикл или обновить параметры

                    ts = update['ts']

                    for event in update.get('updates', []):
                        if event['type'] == 'message_new':
                            msg = event['object']['message']
                            v_user_id = msg['from_id']
                            text = msg['text']

                            # Получаем инфо о пользователе
                            user_info = await get_vk_user_info(v_user_id)
                            full_name = user_info['full_name'] if user_info else f"VK ID {v_user_id}"
                            profile_url = user_info['profile_url'] if user_info else f"https://vk.com/id{v_user_id}"

                            # Сохраняем как лид
                            save_lead(
                                user_id=v_user_id,
                                username=profile_url,
                                full_name=full_name,
                                phone="Ожидает (VK)",
                                module="vk_direct",
                                details=text,
                                source="vk_community"
                            )

                            # Уведомляем в группу
                            lead_msg = f"👥 Новый лид из ВК\n\n" \
                                       f"👤 Имя: {full_name}\n" \
                                       f"📝 Сообщение: {text}\n" \
                                       f"🔗 Профиль: {profile_url}"

                            try:
                                await bot_instance.send_message(LEADS_GROUP_CHAT_ID, lead_msg, message_thread_id=THREAD_ID_KVARTIRY)
                            except Exception as e:
                                logging.error(f"Failed to notify TG about VK lead: {e}")
                            logging.info(f"VK Lead captured: {full_name}")

            except Exception as e:
                logging.error(f"VK LongPoll Loop Error: {e}")
                await asyncio.sleep(5)
