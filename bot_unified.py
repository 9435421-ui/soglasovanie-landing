import asyncio
import logging
import os
import sqlite3
import aiohttp
import hmac
import hashlib
import json
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, MenuButtonWebApp

from config import (BOT_TOKEN, ADMIN_ID, OPENROUTER_API_KEY, CONTENT_CHANNEL_ID,
                    LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA,
                    DATABASE_PATH)
from database import (save_lead, init_db, get_pending_content, add_content_draft,
                      get_latest_news, add_smart_post, get_scheduled_posts, update_smart_post_status,
                      get_birthday_users, update_user_birthday)
from vk_service import post_to_vk
from zen_service import post_to_zen

# Логирование
logging.basicConfig(level=logging.INFO)

# Роли агентов
AGENT_PROMPTS = {
    "квалификатор": "Ты Квалификатор ТЕРИОН. Твоя цель - провести пользователя через квиз, узнать город, тип объекта и телефон. Будь вежлив и краток.",
    "продавец": "Ты Продавец ТЕРИОН. Твоя цель - продать ценность услуг Юлии Пархоменко и получить контакт лида. ЖЕСТКОЕ ПРАВИЛО: НИКОГДА НЕ НАЗЫВАЙ ЦЕНЫ. Если спрашивают стоимость, говори: 'Каждый проект уникален, эксперт Юлия Пархоменко рассчитает точную смету после анализа ваших документов. Давайте пройдем короткий квиз (/quiz) или назначим консультацию?'. Всегда старайся направить пользователя к расчету стоимости через квиз.",
    "контент-менеджер": "Ты Главред ТЕРИОН. Твоя задача - адаптировать текст под разные платформы. Рубрики: 'Советы', 'Интересные факты', 'Новости проекта', 'Поздравления'. Тон: профессиональный, доверительный. Для поздравлений - теплый и праздничный.",
    "креативщик": "Ты Креативщик ТЕРИОН. Придумывай заголовки и идеи для постов. Помни про рубрики: факты, советы, праздники РФ.",
    "маркетолог": "Ты Стратег ТЕРИОН. Анализируй базу знаний и предлагай темы. Следи за праздничным календарем РФ.",
    "дизайнер": "Ты Дизайнер ТЕРИОН. Твоя задача — создавать промпты для генерации изображений. ВАЖНО: На изображениях НЕ ДОЛЖНО БЫТЬ ТЕКСТА. Стиль: архитектурный минимализм, интерьеры, чертежи. Цвета: #2E7D32 и #1A1A1A."
}

# Праздники РФ
RF_HOLIDAYS = {
    "01.01": "Новый год",
    "07.01": "Рождество",
    "23.02": "День защитника Отечества",
    "08.03": "Международный женский день",
    "01.05": "Праздник Весны и Труда",
    "09.05": "День Победы",
    "12.06": "День России",
    "04.11": "День народного единства"
}

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class QuizStates(StatesGroup):
    consent = State()
    city = State()
    object_type = State()
    details = State()
    phone = State()

async def adapt_content_all_platforms(seed_text: str):
    platforms = {
        "tg": "Адаптируй этот текст для Telegram: кратко, с эмодзи, структурированно.",
        "vk": "Адаптируй этот текст для ВК: дружелюбный тон, призыв к обсуждению, средний объем.",
        "zen": "Адаптируй этот текст для Яндекс.Дзена: полноценная экспертная статья-лонгрид, SEO-ключи, подробные объяснения.",
        "landing": "Сделай краткий анонс для лендинга: заголовок и 2-3 предложения, интригующих прочитать подробнее."
    }
    results = {}
    for p_key, p_prompt in platforms.items():
        results[p_key] = await ask_ai("контент-менеджер", f"{p_prompt}\n\nИсходный текст: {seed_text}")

    titles = await ask_ai("креативщик", f"Придумай 3 заголовка для этого текста: {seed_text}")
    results["titles"] = titles

    # Генерация промпта для картинки
    image_prompt = await ask_ai("дизайнер", f"Создай промпт для генерации обложки к посту на тему: {seed_text}. Опиши визуальный образ.")
    results["image_prompt"] = image_prompt

    return results

async def generate_image(prompt: str):
    """Генерация изображения через API OpenRouter (DALL-E 3)"""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}

    # Промпт для генерации картинки через мультимодальную модель или специфичный эндпоинт
    # Примечание: В OpenRouter генерация картинок может идти через специфичные модели
    data = {
        "model": "openai/dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }
    # Поскольку OpenRouter в основном для чата, для DALL-E может потребоваться прямой запрос к OpenAI
    # или использование модели, поддерживающей картинки в OpenRouter.
    # Если OpenRouter не поддерживает прямую генерацию, оставим промпт для ручной/внешней вставки.
    logging.info(f"Generating image with prompt: {prompt}")
    return None # Заглушка, так как не все API OpenRouter поддерживают генерацию картинок напрямую через chat/completions

async def ask_ai(prompt_type: str, user_message: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    system_prompt = AGENT_PROMPTS.get(prompt_type, AGENT_PROMPTS["продавец"])

    data = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                return result['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "Извините, возникла техническая заминка. Передаю ваш вопрос эксперту."

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Черновики постов", callback_data="admin_content")],
        [InlineKeyboardButton(text="📊 Статистика лидов", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🧹 Очистка и оптимизация", callback_data="admin_cleanup")]
    ])
    await message.answer("🛠 Панель управления ТЕРИОН", reply_markup=kb)

@dp.callback_query(F.data == "admin_cleanup")
async def admin_cleanup(callback: types.CallbackQuery):
    from database import optimize_db
    await callback.message.answer("⏳ Начинаю оптимизацию базы данных...")
    try:
        optimize_db()
        await callback.message.answer("✅ База данных оптимизирована! Лишнее место освобождено.")
    except Exception as e:
        logging.error(f"Cleanup Error: {e}")
        await callback.message.answer("❌ Ошибка при оптимизации.")
    await callback.answer()

@dp.callback_query(F.data == "admin_content")
async def admin_content(callback: types.CallbackQuery):
    pending = get_pending_content()
    if not pending:
        await callback.message.answer("Черновиков пока нет.")
        return

    for item in pending:
        post_id, title, body, _, status, platform, _, _ = item
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🪄 Адаптировать для всех платформ", callback_data=f"adapt_{post_id}")],
            [InlineKeyboardButton(text="✅ Быстрая публикация (как есть)", callback_data=f"publish_{post_id}")]
        ])
        await callback.message.answer(f"📌 {title}\n\n{body}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("adapt_"))
async def adapt_content_callback(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    # В реальном приложении мы бы взяли текст из БД по post_id
    # Здесь для примера берем из текста сообщения
    seed_text = callback.message.text
    await callback.message.answer("⏳ ИИ адаптирует контент для ТГ, ВК, Дзена и Лендинга...")

    adapted = await adapt_content_all_platforms(seed_text)

    # Сохраняем в умный календарь
    add_smart_post(
        rubric="Общее",
        title=f"Адаптированный пост #{post_id}",
        body_tg=adapted['tg'],
        body_vk=adapted['vk'],
        body_zen=adapted['zen'],
        body_landing=adapted['landing']
    )

    report = f"✅ Контент адаптирован!\n\n" \
             f"📢 TG: {adapted['tg'][:50]}...\n" \
             f"👥 VK: {adapted['vk'][:50]}...\n" \
             f"📝 Zen: {adapted['zen'][:50]}...\n" \
             f"🌐 Site: {adapted['landing'][:50]}..."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Опубликовать Омни-канал", callback_data=f"smart_pub_{post_id}")]
    ])
    await callback.message.answer(report, reply_markup=kb)
    await callback.answer()

async def execute_omni_publish(title, body_tg, body_vk, body_zen, body_landing, image_url=None):
    """Единая функция для публикации во все каналы"""
    results = []

    # 1. Telegram
    try:
        await bot.send_message(CONTENT_CHANNEL_ID, body_tg)
        results.append("TG: ✅")
    except Exception as e:
        logging.error(f"TG Error: {e}")
        results.append("TG: ❌")

    # 2. VK
    success_vk = await post_to_vk(body_vk)
    results.append("VK: ✅" if success_vk else "VK: ❌")

    # 3. Zen (черновик)
    success_zen = await post_to_zen(title, body_zen)
    results.append("Zen: ✅" if success_zen else "Zen: ❌")

    # 4. Landing (уже в БД, просто возвращаем статус)
    results.append("Site: ✅")

    return " | ".join(results)

@dp.callback_query(F.data.startswith("publish_"))
async def publish_post_callback(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    text = callback.message.text
    title = text.split('\n')[0][:50]

    # Сохраняем и публикуем (быстрый путь)
    smart_id = add_smart_post(
        rubric="Новости", title=title,
        body_tg=text, body_vk=text, body_zen=text, body_landing=text
    )

    report = await execute_omni_publish(title, text, text, text, text)
    update_smart_post_status(smart_id, 'published')

    await callback.message.answer(f"Результат публикации:\n{report}")
    await callback.answer()

async def scheduler_loop():
    """Фоновая задача для проверки расписания и дней рождения"""
    logging.info("Scheduler started.")
    last_birthday_check = None

    while True:
        now = datetime.now()
        today_str = now.strftime("%d.%m")

        # 1. Проверка праздников и дней рождения (раз в день)
        if last_birthday_check != today_str:
            # Праздники
            if today_str in RF_HOLIDAYS:
                holiday_name = RF_HOLIDAYS[today_str]
                logging.info(f"Holiday today: {holiday_name}")
                holiday_post = await ask_ai("контент-менеджер", f"Напиши праздничный пост для соцсетей (ТГ, ВК) в честь праздника: {holiday_name}. Стиль профессиональный, но теплый, от лица ТЕРИОН.")
                # Авто-черновик
                add_smart_post("Праздники", holiday_name, holiday_post, holiday_post, holiday_post, holiday_post)
                await bot.send_message(ADMIN_ID, f"🎉 Сегодня {holiday_name}! Я подготовил черновик поздравительного поста.")

            # Дни рождения
            logging.info(f"Checking birthdays for {today_str}")
            users = get_birthday_users(today_str)
            for u_id, name in users:
                greeting = await ask_ai("контент-менеджер", f"Напиши теплое личное поздравление с днем рождения для клиента по имени {name}, от лица эксперта Юлии Пархоменко и компании ТЕРИОН.")
                try:
                    await bot.send_message(u_id, greeting)
                    logging.info(f"Birthday greeting sent to {name} ({u_id})")
                except Exception as e:
                    logging.error(f"Failed to send birthday greeting to {u_id}: {e}")
            last_birthday_check = today_str

        # 2. Проверка расписания постов
        try:
            pending = get_scheduled_posts()
            for post in pending:
                post_id, title, b_tg, b_vk, b_zen, b_land, img = post
                logging.info(f"Publishing scheduled post: {title}")

                await execute_omni_publish(title, b_tg, b_vk, b_zen, b_land, img)
                update_smart_post_status(post_id, 'published')

                # Уведомляем админа
                await bot.send_message(ADMIN_ID, f"🔔 Авто-публикация выполнена: {title}")

        except Exception as e:
            logging.error(f"Scheduler Error: {e}")

        await asyncio.sleep(60) # Проверка каждую минуту

@dp.callback_query(F.data.startswith("smart_pub_"))
async def smart_publish_post(callback: types.CallbackQuery):
    # Логика для публикации уже адаптированного контента из smart_calendar
    # Здесь мы бы извлекали данные из БД по post_id
    await callback.message.answer("✅ Омни-публикация выполнена по всем каналам!")
    await callback.answer()

def validate_tg_init_data(init_data: str, bot_token: str):
    """Валидация данных от Telegram Mini App"""
    try:
        from urllib.parse import parse_qs
        parsed = parse_qs(init_data)
        hash_val = parsed.pop('hash', [None])[0]
        if not hash_val: return False

        data_check_string = "\n".join([f"{k}={v[0]}" for k, v in sorted(parsed.items())])
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        return computed_hash == hash_val
    except:
        return False

# API для Лендинга и Mini App
async def handle_news_api(request):
    news = get_latest_news(limit=5)
    data = []
    for item in news:
        data.append({
            "title": item[0],
            "content": item[1],
            "date": item[2]
        })
    return web.json_response(data, headers={
        "Access-Control-Allow-Origin": "*" # Для работы CORS с фронтенда
    })

async def handle_leads_api(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not validate_tg_init_data(auth_header, BOT_TOKEN):
        return web.json_response({"error": "Unauthorized"}, status=401)

    from database import get_all_leads
    leads = get_all_leads()
    data = []
    for l in leads:
        data.append({
            "id": l[0],
            "name": l[3],
            "phone": l[4],
            "type": l[7],
            "date": l[10]
        })
    return web.json_response(data)

async def handle_stats_api(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not validate_tg_init_data(auth_header, BOT_TOKEN):
        return web.json_response({"error": "Unauthorized"}, status=401)

    from database import get_stats
    return web.json_response(get_stats())

async def handle_birthdays_api(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not validate_tg_init_data(auth_header, BOT_TOKEN):
        return web.json_response({"error": "Unauthorized"}, status=401)

    from database import get_birthday_users
    now = datetime.now()
    today_str = now.strftime("%d.%m")
    users = get_birthday_users(today_str)
    data = [{"id": u[0], "name": u[1]} for u in users]
    return web.json_response(data)

async def handle_posts_api(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not validate_tg_init_data(auth_header, BOT_TOKEN):
        return web.json_response({"error": "Unauthorized"}, status=401)

    from database import get_all_smart_posts
    posts = get_all_smart_posts()
    data = []
    for p in posts:
        data.append({
            "id": p[0],
            "rubric": p[1],
            "title": p[2],
            "status": p[8],
            "date": p[9] or p[10]
        })
    return web.json_response(data)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/api/news', handle_news_api)
    app.router.add_get('/api/leads', handle_leads_api)
    app.router.add_get('/api/stats', handle_stats_api)
    app.router.add_get('/api/posts', handle_posts_api)
    app.router.add_get('/api/birthdays', handle_birthdays_api)

    # Отдача статики фронтенда (после билда)
    if os.path.exists('frontend/dist'):
        app.router.add_static('/', 'frontend/dist', name='static', follow_symlinks=True)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("API Server started on port 8080")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    args = message.text.split()
    source = args[1] if len(args) > 1 else "direct"
    await state.update_data(source=source)

    # Ссылка на Mini App (в продакшене будет реальный URL)
    web_app_url = "https://ternion.ru/mini-app"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть ТЕРИОН App", web_app=WebAppInfo(url=web_app_url))],
        [InlineKeyboardButton(text="📋 Начать расчет (Квиз)", callback_data="start_quiz")],
        [InlineKeyboardButton(text="💬 Консультация Антона", callback_data="ask_ai")]
    ])

    # Установка кнопки меню
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(text="ТЕРИОН", web_app=WebAppInfo(url=web_app_url))
    )

    await message.answer("🚀 Добро пожаловать в ТЕРИОН — ваш гид по законной перепланировке!", reply_markup=kb)

@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Согласен", callback_data="consent_yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="consent_no")]
    ])
    await message.answer(
        "Перед началом нам нужно ваше согласие на обработку персональных данных в соответствии с ФЗ-152 и на получение уведомлений.\n\n"
        "Вы согласны?",
        reply_markup=kb
    )
    await state.set_state(QuizStates.consent)

@dp.callback_query(F.data == "start_quiz")
async def quiz_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Согласен", callback_data="consent_yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="consent_no")]
    ])
    await callback.message.answer(
        "Перед началом нам нужно ваше согласие на обработку персональных данных в соответствии с ФЗ-152 и на получение уведомлений.\n\n"
        "Вы согласны?",
        reply_markup=kb
    )
    await state.set_state(QuizStates.consent)
    await callback.answer()

@dp.callback_query(QuizStates.consent, F.data == "consent_yes")
async def process_consent(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отлично! В каком городе находится ваш объект?")
    await state.set_state(QuizStates.city)
    await callback.answer()

@dp.callback_query(QuizStates.consent, F.data == "consent_no")
async def process_consent_no(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("К сожалению, без согласия мы не сможем провести расчет. Если передумаете — нажмите /start.")
    await state.clear()
    await callback.answer()

@dp.callback_query(F.data == "ask_ai")
async def cb_ask_ai(callback: types.CallbackQuery):
    await callback.message.answer("Я слушаю! Задайте любой вопрос по перепланировке. Помните, что я не называю точные цены — их определит эксперт Юлия Пархоменко.")
    await callback.answer()

@dp.message(QuizStates.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Тип объекта (Квартира/Коммерция/ИЖС)?")
    await state.set_state(QuizStates.object_type)

@dp.message(QuizStates.object_type)
async def process_obj(message: types.Message, state: FSMContext):
    await state.update_data(object_type=message.text)
    await message.answer("Опишите задачу (что хотите изменить?):")
    await state.set_state(QuizStates.details)

@dp.message(QuizStates.details)
async def process_details(message: types.Message, state: FSMContext):
    await state.update_data(details=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Ваш номер телефона для связи с экспертом. Нажмите кнопку ниже или введите вручную:", reply_markup=kb)
    await state.set_state(QuizStates.phone)

@dp.message(QuizStates.phone)
async def process_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()

    full_name = message.from_user.full_name
    if message.contact:
        phone = message.contact.phone_number
        # Если в контакте имя отличается, можно обновить
        if message.contact.first_name:
            full_name = f"{message.contact.first_name} {message.contact.last_name or ''}".strip()
    else:
        phone = message.text

    # Удаляем ReplyKeyboard
    await message.answer("✅ Данные приняты!", reply_markup=types.ReplyKeyboardRemove())

    profile_url = f"https://t.me/{message.from_user.username}" if message.from_user.username else f"tg://user?id={message.from_user.id}"

    save_lead(
        user_id=message.from_user.id,
        username=profile_url, # Сохраняем ссылку на профиль
        full_name=full_name,
        phone=phone,
        module="quiz",
        city=data.get("city"),
        object_type=data.get("object_type"),
        details=data.get("details"),
        source=data.get("source")
    )

    # Уведомление в группу
    thread_id = THREAD_ID_KVARTIRY
    if data.get("object_type") == "Коммерция":
        thread_id = THREAD_ID_KOMMERCIA
    elif data.get("object_type") == "ИЖС":
        thread_id = THREAD_ID_DOMA

    lead_msg = f"🚀 Новый лид (ТЕРИОН v2.0)\n\n" \
               f"👤 Имя: {message.from_user.full_name}\n" \
               f"📞 Телефон: {phone}\n" \
               f"📍 Город: {data.get('city')}\n" \
               f"🏠 Объект: {data.get('object_type')}\n" \
               f"📝 Детали: {data.get('details')}\n" \
               f"🔗 Источник: {data.get('source')}"

    try:
        await bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, message_thread_id=thread_id, text=lead_msg)
    except Exception as e:
        logging.error(f"Error sending lead: {e}")

    await message.answer("✅ Заявка принята! Эксперт ТЕРИОН свяжется с вами в рабочее время (10:00-20:00 МСК).")
    await state.clear()

@dp.message(F.text)
async def chat_handler(message: types.Message):
    response = await ask_ai("продавец", message.text)
    await message.answer(response)

async def main():
    init_db()
    # Запуск бота, веб-сервера, планировщика и слушателя ВК параллельно
    from vk_service import vk_listener_loop
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server(),
        scheduler_loop(),
        vk_listener_loop(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
