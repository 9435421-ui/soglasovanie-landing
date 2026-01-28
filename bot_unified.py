import asyncio
import logging
import sys
import aiohttp
import csv
import io
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

from config import (BOT_TOKEN, ADMIN_ID, OPENROUTER_API_KEY,
                    LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY,
                    THREAD_ID_KOMMERCIA, THREAD_ID_DOMA)
from database import save_lead, init_db, get_daily_leads

# Логирование
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Состояния FSM
class QuizStates(StatesGroup):
    city = State()
    object_type = State()
    details = State()
    phone = State()

# Тексты
GREETING = """📋 Добро пожаловать в сервис консультаций по перепланировке ТЕРИОН!

Перед началом работы необходимо:
✅ Согласие на обработку персональных данных
✅ Согласие на принятие условий Пользовательского соглашения

Я — Антон, ИИ-консультант компании ТЕРИОН. Я помогу вам оценить риски и потенциал вашей недвижимости, мы работаем по всей России."""

ANTON_PROMPT = "Ты Антон, ИИ-консультант компании ТЕРИОН. Твоя специализация: перепланировка, согласование, оценка рисков и потенциала объектов. Отвечай кратко (до 500 символов), вежливо. Если вопрос не по теме, мягко верни пользователя к теме перепланировок."

async def ask_anton(question: str):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [
            {"role": "system", "content": ANTON_PROMPT},
            {"role": "user", "content": question}
        ]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                result = await resp.json()
                return result['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"Error calling OpenRouter: {e}")
        return "Извините, сейчас я не могу ответить. Попробуйте позже или начните расчет."

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    args = message.text.split()
    source = "direct"
    if len(args) > 1:
        source = args[1]

    await state.update_data(source=source)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пройти тест (Квиз)", callback_data="start_quiz")],
        [InlineKeyboardButton(text="Задать вопрос Антону", callback_data="ask_anton")]
    ])

    await message.answer(GREETING, reply_markup=keyboard)

@dp.callback_query(F.data == "ask_anton")
async def cb_ask_anton(callback: types.CallbackQuery):
    await callback.message.answer("Задайте ваш вопрос по перепланировке. Я постараюсь ответить максимально точно.")
    await callback.answer()

@dp.callback_query(F.data == "start_quiz")
async def cb_start_quiz(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Начнем! В каком городе находится ваш объект?")
    await state.set_state(QuizStates.city)
    await callback.answer()

@dp.message(QuizStates.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Квартира"), KeyboardButton(text="Апартаменты")],
        [KeyboardButton(text="Нежилое"), KeyboardButton(text="ИЖС")]
    ], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Тип объекта?", reply_markup=kb)
    await state.set_state(QuizStates.object_type)

@dp.message(QuizStates.object_type)
async def process_object_type(message: types.Message, state: FSMContext):
    await state.update_data(object_type=message.text)
    await message.answer("Что вы планируете изменить? (краткое описание)", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(QuizStates.details)

@dp.message(QuizStates.details)
async def process_details(message: types.Message, state: FSMContext):
    await state.update_data(details=message.text)
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Поделиться контактом", request_contact=True)]
    ], resize_keyboard=True, one_time_keyboard=True)
    await message.answer("Для связи с экспертом укажите ваш номер телефона или нажмите кнопку ниже.", reply_markup=kb)
    await state.set_state(QuizStates.phone)

@dp.message(QuizStates.phone)
async def process_phone(message: types.Message, state: FSMContext):
    phone = message.contact.phone_number if message.contact else message.text
    data = await state.get_data()

    # Сохранение в БД
    save_lead(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        phone=phone,
        module=data.get("module", "quiz"),
        city=data.get("city"),
        object_type=data.get("object_type"),
        details=data.get("details"),
        source=data.get("source", "direct")
    )

    # Уведомление в группу
    thread_id = THREAD_ID_KVARTIRY
    if data.get("object_type") == "Нежилое":
        thread_id = THREAD_ID_KOMMERCIA
    elif data.get("object_type") == "ИЖС":
        thread_id = THREAD_ID_DOMA

    lead_msg = f"🚀 Новый лид (ТЕРИОН)\n\n" \
               f"👤 Имя: {message.from_user.full_name}\n" \
               f"📞 Телефон: {phone}\n" \
               f"📍 Город: {data.get('city')}\n" \
               f"🏠 Объект: {data.get('object_type')}\n" \
               f"📝 Детали: {data.get('details')}\n" \
               f"🔗 Источник: {data.get('source')}"

    try:
        await bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, message_thread_id=thread_id, text=lead_msg)
    except Exception as e:
        logging.error(f"Error sending lead to group: {e}")

    await message.answer("✅ Спасибо! Ваша заявка принята.\n\nКоманда ТЕРИОН свяжется с вами ежедневно с 10:00 до 20:00 по Москве для обсуждения деталей и предварительного расчёта.", reply_markup=types.ReplyKeyboardRemove())

    await state.clear()

@dp.message(F.text & ~F.text.startswith('/'))
async def handle_anton_questions(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    response = await ask_anton(message.text)
    await message.answer(response)

async def send_daily_report():
    leads = get_daily_leads()
    if not leads:
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'User ID', 'Username', 'Name', 'Phone', 'Module', 'City', 'Object', 'Details', 'Source', 'Date'])
    writer.writerows(leads)

    output.seek(0)
    document = types.BufferedInputFile(output.read().encode('utf-8'), filename=f"report_{datetime.now().strftime('%Y-%m-%d')}.csv")

    try:
        await bot.send_document(chat_id=ADMIN_ID, document=document, caption=f"📊 Ежедневный отчет по лидам ТЕРИОН за {datetime.now().strftime('%d.%m.%Y')}")
    except Exception as e:
        logging.error(f"Error sending report: {e}")

async def scheduler():
    while True:
        now = datetime.now()
        if now.hour == 9 and now.minute == 0:
            await send_daily_report()
            await asyncio.sleep(60)
        await asyncio.sleep(30)

async def main():
    init_db()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
