import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import sqlite3

# ============= НАСТРОЙКИ (ЗАМЕНИТЬ!) =============
BOT_TOKEN = "8488749521:AAHqJYO0TzuXUmKoZiW7o_Y1eNi2CKV0BfI"  # ← ВСТАВЬ СВОЙ ТОКЕН ОТ @BotFather
ADMIN_ID = 7773148577  # ← ВСТАВЬ СВОЙ TELEGRAM ID (можно узнать у @userinfobot)
# ==================================================

# === Инициализация бота ===
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# === FSM для сбора новости ===
class NewsStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    broadcast_message = State()

# === Работа с БД (SQLite) ===
def init_db():
    with sqlite3.connect("bot.db") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT
            )
        """)
        conn.commit()

def add_user(user_id: int, username: str, full_name: str):
    with sqlite3.connect("bot.db") as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name)
        )
        conn.commit()

def get_all_user_ids():
    with sqlite3.connect("bot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        return [row[0] for row in cursor.fetchall()]

# === Клавиатуры ===
def get_start_keyboard(user_id: int):
    buttons = [[KeyboardButton(text="Предложить новость")]]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="Отправить оповещение")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=False)

def get_news_type_keyboard():
    buttons = [
        [KeyboardButton(text="Только текст")],
        [KeyboardButton(text="Текст + Картинка")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

# === Приветствие (как ты просил) ===
START_MESSAGE = """Привет,

Сюда можно прислать любую новость: фото или видео, все самое интересное кидать только в этот канал!
💁🏻‍♂️Обязательно пишите адрес, где что произошло."""

# === Красивое оформление новости для админа ===
def format_news_for_admin(user_data, text: str = None, has_photo: bool = False):
    username = user_data['username']
    full_name = user_data['full_name']
    user_id = user_data['user_id']

    # Кликабельная ссылка на пользователя
    if username:
        user_link = f'<a href="https://t.me/{username}">@{username}</a>'
    else:
        user_link = f'<a href="tg://user?id={user_id}">Пользователь</a>'

    header = "📬 <b>Новая предложенная новость</b>"
    divider = "────────────────────────"
    user_info = f"👤 <b>От:</b> {user_link} (<code>{user_id}</code>)"
    if full_name:
        user_info += f" | <i>{full_name}</i>"

    news_text = f"📝 <b>Текст:</b>\n{i(text)}" if text else "📝 <b>Текст:</b> (отсутствует)"
    media_info = "🖼️ <b>Фото:</b> Да" if has_photo else "🖼️ <b>Фото:</b> Нет"

    return (
        f"{header}\n"
        f"{divider}\n"
        f"{user_info}\n"
        f"{divider}\n"
        f"{news_text}\n"
        f"{divider}\n"
        f"{media_info}\n"
        f"🔚 <i>Конец новости</i>"
    )

# === Обработчики ===
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name

    add_user(user_id, username, full_name)
    await message.answer(
        START_MESSAGE,
        reply_markup=get_start_keyboard(user_id)
    )

@dp.message(F.text == "Предложить новость")
async def propose_news(message: Message, state: FSMContext):
    await state.set_state(NewsStates.waiting_for_text)
    await message.answer(
        "Выберите тип новости:",
        reply_markup=get_news_type_keyboard()
    )

@dp.message(F.text == "Только текст")
async def text_only(message: Message, state: FSMContext):
    await state.update_data(news_type="text_only")
    await state.set_state(NewsStates.waiting_for_text)
    await message.answer(
        "Отправьте текст своей новости.\n\nНе забудьте указать <b>адрес</b>!",
        reply_markup=None
    )

@dp.message(F.text == "Текст + Картинка")
async def text_and_photo(message: Message, state: FSMContext):
    await state.update_data(news_type="text_photo")
    await state.set_state(NewsStates.waiting_for_text)
    await message.answer(
        "Сначала отправьте <b>текст</b> своей новости.\n\nНе забудьте указать <b>адрес</b>!",
        reply_markup=None
    )

@dp.message(NewsStates.waiting_for_text, F.text)
async def get_news_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    data = await state.get_data()
    news_type = data.get("news_type")

    if news_type == "text_only":
        user_data = {
            "user_id": message.from_user.id,
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
        }
        admin_message = format_news_for_admin(user_data, text=message.text, has_photo=False)
        await bot.send_message(ADMIN_ID, admin_message)
        await message.answer("✅ Новость отправлена! Спасибо за вклад.")
        await state.clear()
    elif news_type == "text_photo":
        await state.set_state(NewsStates.waiting_for_photo)
        await message.answer("Теперь отправьте <b>фото</b> к новости.")

@dp.message(NewsStates.waiting_for_text)
async def invalid_text(message: Message):
    await message.answer("Пожалуйста, отправьте текст новости.")

@dp.message(NewsStates.waiting_for_photo, F.photo)
async def get_news_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("text", "(текст отсутствует)")
    photo_id = message.photo[-1].file_id

    user_data = {
        "user_id": message.from_user.id,
        "username": message.from_user.username,
        "full_name": message.from_user.full_name,
    }

    admin_message = format_news_for_admin(user_data, text=text, has_photo=True)
    await bot.send_message(ADMIN_ID, admin_message)
    await bot.send_photo(ADMIN_ID, photo_id)

    await message.answer("✅ Новость с фото отправлена! Спасибо.")
    await state.clear()

@dp.message(NewsStates.waiting_for_photo)
async def invalid_photo(message: Message):
    await message.answer("Пожалуйста, отправьте <b>фото</b>.")

@dp.message(F.text == "Отправить оповещение")
async def start_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    await state.set_state(NewsStates.broadcast_message)
    await message.answer("Отправьте сообщение для рассылки всем пользователям.")

@dp.message(NewsStates.broadcast_message)
async def broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    user_ids = get_all_user_ids()
    sent = 0
    failed = 0

    status_msg = await message.answer("📤 Рассылка начата...")

    for user_id in user_ids:
        try:
            if message.photo:
                await bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
            elif message.text:
                await bot.send_message(user_id, message.text)
            elif message.video:
                await bot.send_video(user_id, message.video.file_id, caption=message.caption)
            elif message.document:
                await bot.send_document(user_id, message.document.file_id, caption=message.caption)
            else:
                await bot.send_message(user_id, "📢 Оповещение от администратора.")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(f"✅ Рассылка завершена!\nОтправлено: {sent}\nНе удалось: {failed}")
    await state.clear()

# === Запуск бота ===
async def main():
    init_db()
    print("✅ Бот запущен и готов к работе")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
