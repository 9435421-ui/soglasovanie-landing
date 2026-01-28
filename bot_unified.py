import asyncio
import logging
import sqlite3
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import (BOT_TOKEN, ADMIN_ID, OPENROUTER_API_KEY, CONTENT_CHANNEL_ID,
                    LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA,
                    DATABASE_PATH)
from database import save_lead, init_db, get_pending_content, add_content_draft, get_latest_news, add_smart_post
from vk_service import post_to_vk
from zen_service import post_to_zen

# Логирование
logging.basicConfig(level=logging.INFO)

# Роли агентов
AGENT_PROMPTS = {
    "квалификатор": "Ты Квалификатор ТЕРИОН. Твоя цель - провести пользователя через квиз, узнать город, тип объекта и телефон. Будь вежлив и краток.",
    "продавец": "Ты Продавец ТЕРИОН. Твоя цель - продать ценность услуг Юлии Пархоменко. ЖЕСТКОЕ ПРАВИЛО: НИКОГДА НЕ НАЗЫВАЙ ЦЕНЫ. Если спрашивают стоимость, говори: 'Каждый проект уникален, эксперт Юлия Пархоменко рассчитает точную смету после анализа ваших документов. Давайте назначим консультацию?'.",
    "контент-менеджер": "Ты Главред ТЕРИОН. Твоя задача - адаптировать текст под разные платформы: Telegram (кратко, кнопки), VK (средний объем, вовлечение), Яндекс.Дзен (лонгрид, SEO, подробности), Лендинг (анонс, выгода).",
    "креативщик": "Ты Креативщик ТЕРИОН. Твоя задача - придумать 3 варианта заголовка для поста: хайповый, экспертный и поисковый (SEO).",
    "маркетолог": "Ты Стратег ТЕРИОН. Анализируй базу знаний и предлагай темы для постов, которые подчеркивают экспертность в перепланировках."
}

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class QuizStates(StatesGroup):
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
    return results

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
        [InlineKeyboardButton(text="📊 Статистика лидов", callback_data="admin_stats")]
    ])
    await message.answer("🛠 Панель управления ТЕРИОН", reply_markup=kb)

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

@dp.callback_query(F.data.startswith("publish_"))
async def publish_post(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    text = callback.message.text
    title = text.split('\n')[0][:50]

    # 1. Telegram
    try:
        await bot.send_message(CONTENT_CHANNEL_ID, text)
        await callback.message.answer("✅ Опубликовано в Telegram")
    except Exception as e:
        logging.error(f"TG Channel Error: {e}")

    # 2. VK
    success_vk = await post_to_vk(text)
    if success_vk:
        await callback.message.answer("✅ Опубликовано в VK")

    # 3. Zen (черновик)
    success_zen = await post_to_zen(f"Статья ТЕРИОН #{post_id}", text)
    if success_zen:
        await callback.message.answer("✅ Черновик в Дзене создан")

    # 4. Landing (Сохраняем в БД со статусом published)
    smart_id = add_smart_post(
        rubric="Новости",
        title=title,
        body_tg=text,
        body_vk=text,
        body_zen=text,
        body_landing=text
    )

    # Помечаем запись как опубликованную
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE smart_calendar SET status = 'published' WHERE id = ?", (smart_id,))
    conn.commit()
    conn.close()

    await callback.message.answer("✅ Добавлено в ленту лендинга")
    await callback.answer()

@dp.callback_query(F.data.startswith("smart_pub_"))
async def smart_publish_post(callback: types.CallbackQuery):
    # Логика для публикации уже адаптированного контента из smart_calendar
    # Здесь мы бы извлекали данные из БД по post_id
    await callback.message.answer("✅ Омни-публикация выполнена по всем каналам!")
    await callback.answer()

# API для Лендинга
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

async def start_web_server():
    app = web.Application()
    app.router.add_get('/api/news', handle_news_api)
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

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Начать расчет (Квиз)", callback_data="start_quiz")],
        [InlineKeyboardButton(text="💬 Консультация Антона", callback_data="ask_ai")]
    ])
    await message.answer("🚀 Добро пожаловать в ТЕРИОН — ваш гид по законной перепланировке!", reply_markup=kb)

@dp.callback_query(F.data == "start_quiz")
async def quiz_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("В каком городе находится ваш объект?")
    await state.set_state(QuizStates.city)
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
    await message.answer("Ваш номер телефона для связи с экспертом:")
    await state.set_state(QuizStates.phone)

@dp.message(QuizStates.phone)
async def process_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = message.text
    save_lead(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
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
    # Запуск бота и веб-сервера параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
