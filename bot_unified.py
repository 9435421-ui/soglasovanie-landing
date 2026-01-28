import asyncio
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import (BOT_TOKEN, ADMIN_ID, OPENROUTER_API_KEY, CONTENT_CHANNEL_ID,
                    LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA)
from database import save_lead, init_db, get_pending_content, add_content_draft
from vk_service import post_to_vk

# Логирование
logging.basicConfig(level=logging.INFO)

# Роли агентов
AGENT_PROMPTS = {
    "квалификатор": "Ты Квалификатор ТЕРИОН. Твоя цель - провести пользователя через квиз, узнать город, тип объекта и телефон. Будь вежлив и краток.",
    "продавец": "Ты Продавец ТЕРИОН. Твоя цель - продать ценность услуг Юлии Пархоменко. ЖЕСТКОЕ ПРАВИЛО: НИКОГДА НЕ НАЗЫВАЙ ЦЕНЫ. Если спрашивают стоимость, говори: 'Каждый проект уникален, эксперт Юлия Пархоменко рассчитает точную смету после анализа ваших документов. Давайте назначим консультацию?'.",
    "контент-менеджер": "Ты Главред ТЕРИОН. Твоя задача - готовить посты для ТГ и ВК на основе экспертных данных. Стиль: профессиональный, доверительный, без 'воды'.",
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
            [InlineKeyboardButton(text="✅ Опубликовать везде", callback_data=f"publish_{post_id}")]
        ])
        await callback.message.answer(f"📌 {title}\n\n{body}", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data.startswith("publish_"))
async def publish_post(callback: types.CallbackQuery):
    post_id = callback.data.split("_")[1]
    text = callback.message.text

    try:
        await bot.send_message(CONTENT_CHANNEL_ID, text)
        await callback.message.answer("✅ Опубликовано в Telegram")
    except Exception as e:
        logging.error(f"TG Channel Error: {e}")

    success_vk = await post_to_vk(text)
    if success_vk:
        await callback.message.answer("✅ Опубликовано в VK")

    await callback.answer()

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
