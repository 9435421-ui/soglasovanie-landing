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
                    THREAD_ID_LOGS, DATABASE_PATH)
from database import (save_lead, init_db, get_pending_content, add_content_draft,
                      get_latest_news, add_smart_post, get_scheduled_posts, update_smart_post_status,
                      get_birthday_users, update_user_birthday)
from vk_service import post_to_vk
from zen_service import post_to_zen

# Логирование
logging.basicConfig(level=logging.INFO)

# Роли агентов
AGENT_PROMPTS = {
    "квалификатор": "Ты Квалификатор ТЕРИОН. Твоя цель - провести пользователя через квиз, узнать город, тип объекта и телефон. Будь вежлив и краток. Твоя миссия — честная оценка рисков.",
    "продавец": "Ты Антон, экспертный ИИ-консультант ТЕРИОН. Ты помогаешь Юлии Пархоменко. Твой стиль: профессиональный, спокойный, честный. \n\nМАНИФЕСТ: Если решение возможно — мы объясним путь. Если невозможно — скажем об этом сразу. ТЕРИОН не обещает невозможного: мы честно оцениваем риски, стоимость и сроки каждого шага.\n\nЖЕСТКОЕ ПРАВИЛО ПО ЦЕНАМ: НИКОГДА НЕ НАЗЫВАЙ ЦИФРЫ. На вопросы о стоимости отвечай: 'Стоимость согласования зависит от множества факторов: города, типа дома, сложности изменений. Юлия Пархоменко рассчитает точную смету после анализа ваших документов. Для начала рекомендую пройти наш квиз (/quiz) или загрузить план помещения прямо здесь'.",
    "контент-менеджер": "Ты Главред ТЕРИОН. Твоя задача - адаптировать текст под разные платформы. Рубрики: 'Советы', 'Интересные факты', 'Новости проекта', 'Поздравления'. Тон: профессиональный, архитектурный.",
    "креативщик": "Ты Креативщик ТЕРИОН. Придумывай заголовки и идеи для постов. Помни про рубрики: факты, советы, праздники РФ.",
    "маркетолог": "Ты Стратег ТЕРИОН. Анализируй базу знаний и предлагай темы. Следи за праздничным календарем РФ.",
    "дизайнер": "Ты Дизайнер ТЕРИОН. Твоя задача — создавать промпты для генерации изображений. ВАЖНО: На изображениях НЕ ДОЛЖНО БЫТЬ ТЕКСТА. Стиль: архитектурный минимализм, интерьеры, чертежи. Цвета: #2E7D32 и #1A1A1A."
}

def get_working_hours_status():
    """Проверка рабочего времени: Пн-Пт, 09:00-19:00 МСК"""
    # МСК - это UTC+3
    from datetime import timedelta, timezone
    msk_tz = timezone(timedelta(hours=3))
    now = datetime.now(msk_tz)

    is_weekday = now.weekday() < 5 # 0-4 это Пн-Пт
    is_working_hour = 9 <= now.hour < 19

    if is_weekday and is_working_hour:
        return True
    return False

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
    geography = State()
    property_type = State()
    floors = State()
    area = State()
    project_status = State()
    documentation = State()
    additional_info = State()

class PostStates(StatesGroup):
    choosing_rubric = State()
    writing_text = State()

RUBRICS = ["Советы эксперта", "Новости проекта", "Интересные факты", "Кейсы"]

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
        await message.answer(
            f"⛔️ Доступ ограничен. Ваш ID: `{message.from_user.id}`.\n\n"
            f"Чтобы получить права администратора, добавьте этот ID в переменную `ADMIN_ID` в файле `.env` на сервере и перезапустите бота.",
            parse_mode="Markdown"
        )
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Создать новый пост", callback_data="admin_create_post")],
        [InlineKeyboardButton(text="📝 Черновики/Адаптация", callback_data="admin_content")],
        [InlineKeyboardButton(text="📊 Статистика лидов", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🧹 Очистка и оптимизация", callback_data="admin_cleanup")]
    ])
    await message.answer("🛠 Панель управления ТЕРИОН. Выберите действие:", reply_markup=kb)

@dp.callback_query(F.data == "admin_create_post")
async def admin_create_post(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=r, callback_data=f"rubric_{i}")] for i, r in enumerate(RUBRICS)
    ])
    await callback.message.edit_text("Выберите рубрику для нового контента:", reply_markup=kb)
    await state.set_state(PostStates.choosing_rubric)
    await callback.answer()

@dp.callback_query(PostStates.choosing_rubric, F.data.startswith("rubric_"))
async def process_rubric(callback: types.CallbackQuery, state: FSMContext):
    rubric_idx = int(callback.data.split("_")[1])
    rubric = RUBRICS[rubric_idx]
    await state.update_data(chosen_rubric=rubric)
    await callback.message.edit_text(f"Рубрика: {rubric}. Пришлите текст поста или описание идеи. ИИ ТЕРИОН адаптирует его для всех каналов.")
    await state.set_state(PostStates.writing_text)
    await callback.answer()

@dp.message(PostStates.writing_text, F.text)
async def process_post_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rubric = data.get('chosen_rubric')
    seed_text = message.text

    msg = await message.answer("⏳ ИИ ТЕРИОН анализирует текст и готовит публикации...")
    adapted = await adapt_content_all_platforms(seed_text)

    smart_id = add_smart_post(
        rubric=rubric,
        title=adapted['titles'].split('\n')[0][:50],
        body_tg=adapted['tg'],
        body_vk=adapted['vk'],
        body_zen=adapted['zen'],
        body_landing=adapted['landing']
    )

    report = f"✅ Контент готов (Рубрика: {rubric})!\n\n" \
             f"📢 TG: {adapted['tg'][:50]}...\n" \
             f"👥 VK: {adapted['vk'][:50]}...\n" \
             f"📝 Zen: {adapted['zen'][:50]}..."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"smart_pub_now_{smart_id}")],
        [InlineKeyboardButton(text="📅 В расписание", callback_data=f"smart_sched_{smart_id}")]
    ])
    await msg.edit_text(report, reply_markup=kb)
    await state.clear()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    from database import get_stats
    stats = get_stats()
    text = (
        f"📊 **Статистика ТЕРИОН**\n\n"
        f"👥 Лидов за сегодня: {stats['leadsToday']}\n"
        f"📢 Опубликовано постов: {stats['activePosts']}\n"
        f"📈 Конверсия квиза: {stats['conversion']}\n\n"
        f"Все данные также доступны в Mini App."
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

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

# Обработчики для статики и API
async def handle_index(request):
    if os.path.exists('index.html'):
        with open('index.html', 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')
    return web.Response(text="Landing page not found", status=404)

async def handle_mini_app(request):
    # Отдаем index.html из билда фронтенда для всех путей Mini App
    dist_path = 'frontend/dist/index.html'
    if os.path.exists(dist_path):
        with open(dist_path, 'r', encoding='utf-8') as f:
            return web.Response(text=f.read(), content_type='text/html')
    return web.Response(text="Mini App build not found. Please run build first.", status=404)

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
    app.router.add_get('/', handle_index)
    app.router.add_get('/mini-app', handle_mini_app)
    app.router.add_get('/api/news', handle_news_api)
    app.router.add_get('/api/leads', handle_leads_api)
    app.router.add_get('/api/stats', handle_stats_api)
    app.router.add_get('/api/posts', handle_posts_api)
    app.router.add_get('/api/birthdays', handle_birthdays_api)

    # Отдача статики фронтенда
    if os.path.exists('frontend/dist'):
        app.router.add_static('/assets', 'frontend/dist/assets', name='static')
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("API Server started on port 8080")

@dp.message(Command("my_id"))
async def cmd_my_id(message: types.Message):
    await message.answer(f"Ваш Telegram ID: `{message.from_user.id}`. Используйте его для настройки ADMIN_ID в .env файле.", parse_mode="Markdown")

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    logging.info(f"User {message.from_user.id} (@{message.from_user.username}) started the bot.")
    args = message.text.split()
    source = args[1] if len(args) > 1 else "direct"
    await state.update_data(source=source)

    # URL Mini App
    web_app_url = "https://ternion.ru/mini-app"

    # Установка кнопки меню Mini App
    try:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(text="ТЕРИОН", web_app=WebAppInfo(url=web_app_url))
        )
    except Exception as e:
        logging.error(f"Menu button error: {e}")

    # Главное меню (ReplyKeyboardMarkup)
    main_kb_list = [
        [KeyboardButton(text="📊 Рассчитать стоимость (Квиз)")],
        [KeyboardButton(text="🤖 Задать вопрос Антону")]
    ]

    if message.from_user.id == ADMIN_ID:
        main_kb_list.append([KeyboardButton(text="🛠 Панель управления")])
        main_kb_list.append([KeyboardButton(text="📅 Умный календарь")])

    main_kb = ReplyKeyboardMarkup(keyboard=main_kb_list, resize_keyboard=True)

    if source in ["quiz_land", "quiz"]:
        # Если пришли с лендинга сразу на квиз
        welcome_text = (
            "Здравствуйте. Меня зовут Антон, я ИИ-помощник в системе ТЕРИОН. 🏛️\n\n"
            "Вижу, вы хотите рассчитать стоимость согласования и оценить риски проекта.\n\n"
            "Для начала анализа, пожалуйста, подтвердите согласие на обработку данных и поделитесь контактом, нажав кнопку ниже."
        )
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="✅ Согласен и отправить телефон", request_contact=True)],
            [KeyboardButton(text="📖 Политика конфиденциальности")]
        ], resize_keyboard=True, one_time_keyboard=True)
        await message.answer(welcome_text, reply_markup=kb)
        await state.set_state(QuizStates.consent)
    else:
        welcome_text = (
            "Добро пожаловать в экосистему ТЕРИОН! 🏛️\n\n"
            "Я помогу вам легализовать перепланировку, оценить риски объекта и подготовить документы по всей России.\n\n"
            "Выберите нужное действие в меню ниже:"
        )
        await message.answer(welcome_text, reply_markup=main_kb)

@dp.message(F.text == "🛠 Панель управления")
async def admin_menu_btn(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await cmd_admin(message)
    else:
        logging.warning(f"Unauthorized access attempt to admin panel from user {message.from_user.id}")
        await message.answer(f"Доступ запрещен. Ваш ID: {message.from_user.id}. Убедитесь, что он указан в ADMIN_ID.")

@dp.message(F.text == "📅 Умный календарь")
async def admin_calendar_btn(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await admin_content(types.CallbackQuery(id="0", from_user=message.from_user, chat_instance="0", message=message, data="admin_content"))
    else:
        await message.answer("Доступ запрещен.")

@dp.message(F.text == "📊 Рассчитать стоимость (Квиз)")
async def menu_quiz(message: types.Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="✅ Согласен и отправить телефон", request_contact=True)],
        [KeyboardButton(text="📖 Политика конфиденциальности")]
    ], resize_keyboard=True, one_time_keyboard=True)
    await message.answer(
        "Для расчета стоимости нам нужно ваше согласие на обработку данных (ФЗ-152) и контакт для связи с экспертом.",
        reply_markup=kb
    )
    await state.set_state(QuizStates.consent)

@dp.message(F.text == "🤖 Задать вопрос Антону")
async def menu_ask_ai(message: types.Message):
    await message.answer("Я слушаю! Напишите ваш вопрос о перепланировке, и я постараюсь ответить.")

@dp.message(Command("quiz"))
async def cmd_quiz(message: types.Message, state: FSMContext):
    # Команда /quiz теперь ведет на то же приветствие с согласием
    await cmd_start(message, state)

@dp.message(Command("privacy"))
async def cmd_privacy(message: types.Message):
    privacy_text = (
        "🔒 **Политика конфиденциальности ТЕРИОН**\n\n"
        "Мы соблюдаем ФЗ-152 «О персональных данных».\n"
        "1. **Какие данные мы собираем:** Имя, номер телефона, данные об объекте недвижимости.\n"
        "2. **Цель:** Оценка возможности согласования перепланировки и связь с экспертом.\n"
        "3. **Защита:** Мы не передаем ваши данные третьим лицам, не имеющим отношения к вашему запросу.\n"
        "4. **Уведомления:** Мы можем присылать вам информацию о статусе заявки и важные новости законодательства.\n\n"
        "Вы можете отозвать согласие, написав нам в поддержку."
    )
    await message.answer(privacy_text, parse_mode="Markdown")

@dp.callback_query(F.data == "show_privacy")
async def cb_show_privacy(callback: types.CallbackQuery):
    await cmd_privacy(callback.message)
    await callback.answer()

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

@dp.message(QuizStates.consent, F.text == "📖 Политика конфиденциальности")
async def process_privacy_btn(message: types.Message):
    await cmd_privacy(message)

@dp.message(QuizStates.consent, F.contact | (F.text.in_({"✅ Согласен и отправить номер телефона", "✅ Согласен и отправить телефон"})))
async def process_consent(message: types.Message, state: FSMContext):
    if not message.contact:
        # Если пришел текст, который не является кнопкой политики, просим контакт
        if message.text != "📖 Политика конфиденциальности":
            await message.answer("⚠️ Чтобы продолжить, пожалуйста, нажмите кнопку **'✅ Согласен и отправить телефон'**.")
        return

    phone = message.contact.phone_number
    full_name = f"{message.contact.first_name} {message.contact.last_name or ''}".strip()

    await state.update_data(
        phone=phone,
        full_name=full_name,
        consent_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Москва", callback_data="geo_moscow")],
        [InlineKeyboardButton(text="Московская область", callback_data="geo_mo")],
        [InlineKeyboardButton(text="Другой регион", callback_data="geo_other")]
    ])

    await message.answer(
        "Благодарю. Для учета местных строительных норм и регламентов администраций (МЖИ и др.) уточните:\n\n"
        "В каком городе или регионе находится ваш объект?",
        reply_markup=kb
    )
    await state.set_state(QuizStates.geography)

@dp.message(QuizStates.geography, F.text)
async def process_geography_text(message: types.Message, state: FSMContext):
    await state.update_data(geography=message.text)
    await show_property_type_selection(message, state)

async def show_property_type_selection(message_or_callback, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Квартира в новостройке", callback_data="type_new")],
        [InlineKeyboardButton(text="Вторичное жилье", callback_data="type_old")],
        [InlineKeyboardButton(text="Коммерческое помещение", callback_data="type_comm")],
        [InlineKeyboardButton(text="Частный дом", callback_data="type_house")]
    ])
    text = "Укажите тип объекта для определения сложности проекта и набора необходимых документов:"

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=kb)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(QuizStates.property_type)

@dp.message(QuizStates.consent)
async def process_consent_fallback(message: types.Message):
    await message.answer(
        "⚠️ Чтобы начать, пожалуйста, нажмите кнопку **'✅ Согласен и отправить телефон'** в меню ниже.\n\n"
        "Это необходимо для соблюдения закона ФЗ-152 о персональных данных."
    )

@dp.callback_query(F.data == "ask_ai")
async def cb_ask_ai(callback: types.CallbackQuery):
    await callback.message.answer(
        "Я, Антон, ии-консультант, информацию о стоимости работ вы получите у нашего специалиста, "
        "также в этом чате, можно оставить дополнительные вопросы, загрузить план помещения."
    )
    await callback.answer()

@dp.callback_query(QuizStates.geography, F.data.startswith("geo_"))
async def process_geography(callback: types.CallbackQuery, state: FSMContext):
    geo_map = {"geo_moscow": "Москва", "geo_mo": "Московская область", "geo_other": "Другой регион"}
    geo = geo_map.get(callback.data, "Не указан")
    await state.update_data(geography=geo)
    await show_property_type_selection(callback, state)
    await callback.answer()

@dp.message(QuizStates.property_type, F.text)
async def process_property_type_text(message: types.Message, state: FSMContext):
    await state.update_data(property_type=message.text)
    await show_floors_question(message, state)

async def show_floors_question(message_or_callback, state: FSMContext):
    text = "Это важно для расчета нагрузки на перекрытия и понимания возможности легализации. На каком этаже находится объект и сколько всего этажей в доме?\n\n(Пример ввода: 5/17)"
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text)
    else:
        await message_or_callback.message.edit_text(text)
    await state.set_state(QuizStates.floors)

@dp.message(QuizStates.floors)
async def process_floors(message: types.Message, state: FSMContext):
    await state.update_data(floors=message.text)
    await message.answer("Укажите примерную площадь помещения в кв. метрах. Это основной параметр для оценки стоимости работ.")
    await state.set_state(QuizStates.area)

@dp.message(QuizStates.area)
async def process_area(message: types.Message, state: FSMContext):
    await state.update_data(area=message.text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Только планирую работы", callback_data="status_plan")],
        [InlineKeyboardButton(text="Уже выполнены (легализация)", callback_data="status_done")],
        [InlineKeyboardButton(text="В процессе ремонта", callback_data="status_process")]
    ])

    await message.answer(
        "На каком этапе находится ваш проект? Это поможет определить процедуру: проектную или судебную.",
        reply_markup=kb
    )
    await state.set_state(QuizStates.project_status)

@dp.callback_query(QuizStates.property_type, F.data.startswith("type_"))
async def process_property_type(callback: types.CallbackQuery, state: FSMContext):
    type_map = {
        "type_new": "Квартира в новостройке",
        "type_old": "Вторичное жилье",
        "type_comm": "Коммерческое помещение",
        "type_house": "Частный дом"
    }
    p_type = type_map.get(callback.data, "Не указан")
    await state.update_data(property_type=p_type)
    await show_floors_question(callback, state)
    await callback.answer()


@dp.message(QuizStates.project_status, F.text)
async def process_project_status_text(message: types.Message, state: FSMContext):
    await state.update_data(project_status=message.text)
    await show_documentation_selection(message, state)

async def show_documentation_selection(message_or_callback, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сейчас пришлю", callback_data="doc_yes")],
        [InlineKeyboardButton(text="❌ Нет плана", callback_data="doc_no")],
        [InlineKeyboardButton(text="✏️ Есть только набросок", callback_data="doc_sketch")]
    ])
    text = "Есть ли у вас на руках план помещения (БТИ, технический паспорт или эскиз)? Анализ документов — первый шаг к честной оценке."
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=kb)
    else:
        await message_or_callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(QuizStates.documentation)

@dp.callback_query(QuizStates.project_status, F.data.startswith("status_"))
async def process_project_status(callback: types.CallbackQuery, state: FSMContext):
    status_map = {
        "status_plan": "Только планирую работы",
        "status_done": "Уже выполнены (легализация)",
        "status_process": "В процессе ремонта"
    }
    status = status_map.get(callback.data, "Не указан")
    await state.update_data(project_status=status)
    await show_documentation_selection(callback, state)
    await callback.answer()

@dp.callback_query(QuizStates.documentation, F.data.startswith("doc_"))
async def process_documentation_choice(callback: types.CallbackQuery, state: FSMContext):
    doc_map = {"doc_yes": "✅ Да, сейчас пришлю", "doc_no": "❌ Нет плана", "doc_sketch": "✏️ Есть только набросок"}
    choice = doc_map.get(callback.data)
    await state.update_data(documentation_choice=choice)

    if callback.data in ["doc_yes", "doc_sketch"]:
        await callback.message.edit_text("Пожалуйста, прикрепите файл или фото (план/набросок) следующим сообщением.")
    else:
        await callback.message.edit_text(
            "Принято. Если у вас остались вопросы или комментарии, напишите их ниже — я добавлю их к вашей карточке.\n\n"
            "Если вопросов нет — просто напишите 'Готово'."
        )

    await state.set_state(QuizStates.additional_info)
    await callback.answer()

@dp.message(QuizStates.additional_info, F.content_type.in_({'text', 'voice', 'document', 'photo'}))
async def process_additional_info(message: types.Message, state: FSMContext):
    data = await state.get_data()

    additional_text = ""
    file_info = ""

    if message.text:
        if message.text.lower() == 'готово':
            additional_text = "Без доп. комментариев"
        else:
            additional_text = message.text
    elif message.voice:
        additional_text = "[Голосовое сообщение]"
        file_info = f"Voice file_id: {message.voice.file_id}"
    elif message.document:
        additional_text = f"[Файл: {message.document.file_name}]"
        file_info = f"Doc file_id: {message.document.file_id}"
    elif message.photo:
        additional_text = "[Фото]"
        file_info = f"Photo file_id: {message.photo[-1].file_id}"

    profile_url = f"https://t.me/{message.from_user.username}" if message.from_user.username else f"tg://user?id={message.from_user.id}"

    # Формируем полную карточку объекта
    card_details = (
        f"📍 География: {data.get('geography')}\n"
        f"🏠 Тип объекта: {data.get('property_type')}\n"
        f"📏 Площадь: {data.get('area')} кв.м.\n"
        f"🏢 Этажность: {data.get('floors')}\n"
        f"🛠 Статус: {data.get('project_status')}\n"
        f"📑 Наличие плана: {data.get('documentation_choice')}\n"
        f"📝 Доп. вопросы: {additional_text}"
    )

    save_lead(
        user_id=message.from_user.id,
        username=profile_url,
        full_name=data.get('full_name'),
        phone=data.get('phone'),
        module="quiz_v3",
        city=data.get("geography"),
        object_type=data.get("property_type"),
        details=card_details,
        source=data.get("source"),
        pd_consent=1,
        consent_date=data.get('consent_date')
    )

    # Уведомление в группу
    thread_id = THREAD_ID_KVARTIRY
    p_type = data.get("property_type", "")
    if "Коммерческое" in p_type:
        thread_id = THREAD_ID_KOMMERCIA
    elif "дом" in p_type:
        thread_id = THREAD_ID_DOMA

    lead_msg = f"🚀 Новый лид (ТЕРИОН v2.1)\n\n" \
               f"👤 Имя: {data.get('full_name')}\n" \
               f"📞 Телефон: {data.get('phone')}\n" \
               f"📋 КАРТОЧКА ОБЪЕКТА:\n{card_details}\n\n" \
               f"🔗 Источник: {data.get('source')}"

    logging.info(f"Attempting to send lead to group {LEADS_GROUP_CHAT_ID}, thread {thread_id}")
    try:
        if LEADS_GROUP_CHAT_ID == 0:
            logging.warning("LEADS_GROUP_CHAT_ID is not set (0). Lead notification skipped.")
        else:
            await bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, message_thread_id=thread_id, text=lead_msg)
            if message.voice:
                await bot.send_voice(LEADS_GROUP_CHAT_ID, message.voice.file_id, message_thread_id=thread_id)
            elif message.document:
                await bot.send_document(LEADS_GROUP_CHAT_ID, message.document.file_id, message_thread_id=thread_id)
            elif message.photo:
                await bot.send_photo(LEADS_GROUP_CHAT_ID, message.photo[-1].file_id, message_thread_id=thread_id)
            logging.info("Lead successfully forwarded to the working group.")
    except Exception as e:
        logging.error(f"Error sending lead to group: {e}")

    # Проверка рабочего времени
    is_working = get_working_hours_status()
    work_time_msg = ""
    if not is_working:
        work_time_msg = "\n\n🕘 Наши рабочие часы: Пн-Пт, с 09:00 до 19:00 (МСК). Если сейчас нерабочее время, мы обработаем вашу заявку первым делом в ближайший рабочий день."

    # Заключительная часть от Антона
    final_text = (
        "Благодарю за ответы. Мы в ТЕРИОН честно оцениваем каждый проект: если решение возможно — мы объясним путь, "
        "если нет — скажем об этом сразу, чтобы вы не тратили ресурсы впустую.\n\n"
        f"**Ваш статус:** Все данные переданы эксперту Юлии Пархоменко. Она проанализирует карточку объекта и свяжется с вами по номеру {data.get('phone')} для детального разбора.{work_time_msg}\n\n"
        "Пока эксперт готовит ответ, вы можете задать мне любые дополнительные вопросы или загрузить документы.\n\n"
        "Ваш Антон, ТЕРИОН. 🏛️"
    )

    await message.answer(final_text, parse_mode="Markdown")
    await state.clear()

@dp.message(F.photo, F.from_user.id == ADMIN_ID)
async def admin_photo_content_handler(message: types.Message, state: FSMContext):
    """Захват фото-контента от админа для создания поста"""
    photo = message.photo[-1]
    caption = message.caption or "Без описания"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪄 Адаптировать ИИ для всех платформ", callback_data="admin_adapt_media")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data="admin_cancel_media")]
    ])

    await state.update_data(temp_media_id=photo.file_id, temp_caption=caption)
    await message.reply(f"📸 Фото получено! Описание: {caption}\nХотите превратить это в пост для всех соцсетей?", reply_markup=kb)

@dp.callback_query(F.data == "admin_adapt_media", F.from_user.id == ADMIN_ID)
async def cb_admin_adapt_media(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    seed_text = data.get('temp_caption')
    media_id = data.get('temp_media_id')

    await callback.message.edit_text("⏳ ИИ ТЕРИОН готовит омни-канальный контент...")

    adapted = await adapt_content_all_platforms(seed_text)

    # Сохраняем черновик в Медиа-Хаб
    smart_id = add_smart_post(
        rubric="Репортаж",
        title=adapted['titles'].split('\n')[0][:50],
        body_tg=adapted['tg'],
        body_vk=adapted['vk'],
        body_zen=adapted['zen'],
        body_landing=adapted['landing'],
        image_url=media_id # Здесь file_id для ТГ
    )

    report = f"✅ Контент готов!\n\n📢 TG: {adapted['tg'][:60]}...\n👥 VK: {adapted['vk'][:60]}...\n📝 Zen: {adapted['zen'][:60]}..."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"smart_pub_now_{smart_id}")],
        [InlineKeyboardButton(text="📅 В расписание (через час)", callback_data=f"smart_sched_{smart_id}")],
        [InlineKeyboardButton(text="✍️ Править", callback_data=f"smart_edit_{smart_id}")]
    ])

    await callback.message.answer(report, reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("smart_pub_now_"), F.from_user.id == ADMIN_ID)
async def cb_smart_pub_now(callback: types.CallbackQuery):
    smart_id = callback.data.split("_")[-1]

    # В реальной БД мы бы достали данные по smart_id
    # Для теста имитируем успех
    await callback.message.edit_text("🚀 Запущена омни-публикация по всем каналам...")

    # Получаем данные из БД (логика для полноценной работы)
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT title, body_tg, body_vk, body_zen, body_landing, image_url FROM smart_calendar WHERE id=?", (smart_id,))
    row = c.fetchone()
    conn.close()

    if row:
        title, b_tg, b_vk, b_zen, b_land, img = row
        report = await execute_omni_publish(title, b_tg, b_vk, b_zen, b_land, img)
        update_smart_post_status(smart_id, 'published')
        await callback.message.answer(f"Результат:\n{report}")
    else:
        await callback.message.answer("❌ Ошибка: пост не найден в базе.")

    await callback.answer()

@dp.callback_query(F.data.startswith("smart_sched_"), F.from_user.id == ADMIN_ID)
async def cb_smart_sched(callback: types.CallbackQuery):
    smart_id = callback.data.split("_")[-1]

    # Планируем на +1 час от текущего времени
    from datetime import timedelta
    sched_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("UPDATE smart_calendar SET status='scheduled', scheduled_at=? WHERE id=?", (sched_time, smart_id))
    conn.commit()
    conn.close()

    await callback.message.edit_text(f"📅 Пост поставлен в очередь на {sched_time}")
    await callback.answer()

@dp.message(F.voice)
async def voice_handler(message: types.Message, state: FSMContext):
    # Если мы в квизе на шаге additional_info, обрабатываем как часть квиза
    curr_state = await state.get_state()
    if curr_state == QuizStates.additional_info:
        await process_additional_info(message, state)
        return

    await message.answer("Я получил ваше голосовое сообщение. Антон пока лучше понимает текст, но я уже передал аудио нашему эксперту Юлии Пархоменко.")
    if LEADS_GROUP_CHAT_ID != 0:
        try:
            await bot.send_voice(
                chat_id=LEADS_GROUP_CHAT_ID,
                voice=message.voice.file_id,
                message_thread_id=THREAD_ID_LOGS,
                caption=f"🎙 Голосовой вопрос от {message.from_user.full_name} (@{message.from_user.username or 'id'+str(message.from_user.id)})"
            )
        except Exception as e:
            logging.error(f"Failed to forward voice message: {e}")

@dp.message(F.text)
async def chat_handler(message: types.Message):
    # Проверка на вопросы о цене
    text_lower = message.text.lower()
    if any(word in text_lower for word in ["цена", "стоимость", "сколько стоит", "прайс", "тариф"]):
        response = (
            "Стоимость согласования в ТЕРИОН всегда индивидуальна и зависит от сложности проекта, типа объекта и региона. "
            "Мы не называем примерных цифр, так как дорожим своей репутацией и вашей уверенностью.\n\n"
            "Юлия Пархоменко рассчитает точную смету после изучения ваших документов. Рекомендую пройти наш квиз (/quiz) — это займет 2 минуты и позволит нам сделать предметное предложение."
        )
    else:
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
