import asyncio
import json
import os
import random
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# ============================================
# ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ
# ============================================
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

if not TOKEN or not ADMIN_ID:
    raise ValueError("❌ BOT_TOKEN и ADMIN_ID должны быть в .env файле!")

# ============================================
# ЗАГРУЗКА JSON КОНФИГУРАЦИЙ
# ============================================
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_games():
    with open('games.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def load_keys_tables():
    with open('keys_tables.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Загружаем все данные
config = load_config()
GAMES = load_games()
KEYS_TABLES = load_keys_tables()
CHANNELS = config['channels']

# Инициализация бота
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ============================================
# ФАЙЛ ДЛЯ ХРАНЕНИЯ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ
# ============================================
USER_DATA_FILE = "user_data.json"

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============================================
# ФУНКЦИИ ПРОВЕРКИ ПОДПИСКИ
# ============================================
async def check_subscription(user_id: int):
    unsubscribed = []
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(channel['username'], user_id)
            if member.status not in ['creator', 'administrator', 'member']:
                unsubscribed.append(channel)
        except:
            unsubscribed.append(channel)
    return len(unsubscribed) == 0, unsubscribed

def subscription_keyboard(channels):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for ch in channels:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"{ch['emoji']} {ch['name']}", url=ch['link'])
        ])
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check_subs")
    ])
    return keyboard

# ============================================
# ФУНКЦИЯ ПОЛУЧЕНИЯ МСК ВРЕМЕНИ
# ============================================
def get_msk_time():
    return datetime.now(timezone(timedelta(hours=3)))

# ============================================
# ГЕНЕРАЦИЯ КЛЮЧА ПО ЧИСЛУ
# ============================================
def generate_key_for_day(game_id: str, day: int, user_id: int = None) -> str:
    """Генерирует ключ для указанной игры и дня"""
    
    if game_id not in KEYS_TABLES:
        return None
    
    game_keys = KEYS_TABLES[game_id]
    day_str = str(day)
    
    if day_str not in game_keys:
        return None
    
    symbols = game_keys[day_str].copy()
    random.shuffle(symbols)
    key_part = "".join(symbols)
    
    if user_id:
        return f"{user_id}:{key_part}"
    return key_part

# ============================================
# ПРОВЕРКА МОЖНО ЛИ ПОЛУЧИТЬ КЛЮЧ
# ============================================
def can_get_key_today(user_id: int, user_data: dict) -> bool:
    msk_now = get_msk_time()
    today_str = msk_now.strftime("%Y-%m-%d")
    
    user_info = user_data.get(str(user_id), {})
    last_key_date = user_info.get("last_key_date")
    
    return last_key_date != today_str

def update_user_key_date(user_id: int, game_id: str, user_data: dict):
    msk_now = get_msk_time()
    today_str = msk_now.strftime("%Y-%m-%d")
    
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    
    user_data[str(user_id)]["last_key_date"] = today_str
    user_data[str(user_id)]["last_game"] = game_id
    save_user_data(user_data)

# ============================================
# КОМАНДА /start
# ============================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    is_subscribed, unsubscribed = await check_subscription(user_id)
    
    if not is_subscribed:
        keyboard = subscription_keyboard(unsubscribed)
        channels_text = "\n".join([f"• {ch['name']}" for ch in unsubscribed])
        await message.answer(
            f"⚠️ **Подпишись на каналы:**\n\n{channels_text}\n\nПосле подписки нажми кнопку проверки.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await show_games_menu(message)

async def show_games_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for game_id, game in GAMES.items():
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{game['emoji']} {game['name']}",
                callback_data=f"game_{game_id}"
            )
        ])
    
    await message.answer(
        "🎮 **Выбери игру для генерации ключа:**\n\n"
        "⚠️ Ключ можно получить **1 раз в день** (по Московскому времени).",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============================================
# КНОПКА ПРОВЕРКИ ПОДПИСКИ
# ============================================
@dp.callback_query(lambda c: c.data == "check_subs")
async def process_check_subs(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    await callback.answer("🔍 Проверяю...")
    is_subscribed, unsubscribed = await check_subscription(user_id)
    
    if is_subscribed:
        try:
            await callback.message.delete()
        except:
            pass
        await show_games_menu(callback.message)
    else:
        keyboard = subscription_keyboard(unsubscribed)
        channels_text = "\n".join([f"• {ch['name']}" for ch in unsubscribed])
        try:
            await callback.message.edit_text(
                text=f"⚠️ **Всё ещё нужно подписаться:**\n\n{channels_text}",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except:
            pass

# ============================================
# ВЫБОР ИГРЫ
# ============================================
@dp.callback_query(lambda c: c.data and c.data.startswith("game_"))
async def process_game_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    game_id = callback.data.replace("game_", "")
    
    if game_id not in GAMES:
        await callback.answer("❌ Игра не найдена")
        return
    
    game = GAMES[game_id]
    
    # Проверяем подписку ещё раз
    is_subscribed, unsubscribed = await check_subscription(user_id)
    if not is_subscribed:
        keyboard = subscription_keyboard(unsubscribed)
        channels_text = "\n".join([f"• {ch['name']}" for ch in unsubscribed])
        await callback.message.edit_text(
            f"⚠️ **Подписка пропала:**\n\n{channels_text}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        await callback.answer()
        return
    
    # Загружаем данные пользователей
    user_data = load_user_data()
    
    # Проверяем можно ли получить ключ сегодня
    if not can_get_key_today(user_id, user_data):
        msk_now = get_msk_time()
        tomorrow = (msk_now + timedelta(days=1)).strftime("%Y-%m-%d")
        await callback.message.edit_text(
            f"❌ **Ты уже получал ключ сегодня!**\n\n"
            f"Следующий ключ можно получить после **00:00 МСК**.\n"
            f"(после наступления {tomorrow})",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    # Получаем текущий день месяца по МСК
    msk_now = get_msk_time()
    current_day = msk_now.day
    
    # Проверяем есть ли таблица ключей для этой игры
    if game_id not in KEYS_TABLES:
        await callback.message.edit_text(
            f"❌ **Для игры {game['name']} нет таблицы ключей**",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    # Проверяем есть ли ключи для этого дня
    day_str = str(current_day)
    if day_str not in KEYS_TABLES[game_id]:
        await callback.message.edit_text(
            f"❌ **Нет ключей для {current_day} числа в игре {game['name']}**",
            parse_mode="Markdown"
        )
        await callback.answer()
        return
    
    # Генерируем ключ
    key = generate_key_for_day(game_id, current_day, user_id)
    
    # Обновляем дату последнего получения
    update_user_key_date(user_id, game_id, user_data)
    
    # Отправляем ключ
    await callback.message.edit_text(
        f"✅ **Ключ для {game['name']}**\n\n"
        f"📅 Дата: {msk_now.strftime('%d.%m.%Y')}\n"
        f"🔑 Ключ: `{key}`\n\n"
        f"⚠️ Ключ действителен **только сегодня**!\n"
        f"Следующий ключ можно будет получить завтра.",
        parse_mode="Markdown"
    )
    
    # Отправляем дополнительное сообщение с инструкцией
    await callback.message.answer(
        "📌 **Как использовать ключ:**\n"
        "1. Скопируй ключ выше\n"
        "2. Вставь его в поле ввода в программе\n\n"
        "Ключ работает только сегодня!",
        parse_mode="Markdown"
    )
    
    await callback.answer("✅ Ключ сгенерирован!")

# ============================================
# КОМАНДА ДЛЯ АДМИНА
# ============================================
@dp.message(Command("getkey"))
async def cmd_getkey(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    args = message.text.split()
    if len(args) != 3:
        await message.answer("❌ Использование: /getkey ИГРА ДЕНЬ\nПример: /getkey standleopc 15")
        return
    
    game_id = args[1]
    try:
        day = int(args[2])
        if 1 <= day <= 31:
            if game_id not in KEYS_TABLES:
                await message.answer(f"❌ Игра '{game_id}' не найдена в таблицах ключей")
                return
            
            if str(day) not in KEYS_TABLES[game_id]:
                await message.answer(f"❌ Нет ключей для {day} числа в игре {game_id}")
                return
            
            key = generate_key_for_day(game_id, day)
            game_name = GAMES.get(game_id, {}).get('name', game_id)
            await message.answer(
                f"🔑 **Ключ для {game_name} ({day} число):**\n"
                f"`{key}`",
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ День должен быть от 1 до 31")
    except ValueError:
        await message.answer("❌ Введите число")

# ============================================
# ЗАПУСК
# ============================================
async def main():
    print("=" * 50)
    print("🤖 Key Generator Bot запущен!")
    msk_now = get_msk_time()
    print(f"📅 Сегодняшнее число по МСК: {msk_now.day}")
    print(f"🎮 Игр в базе: {len(GAMES)}")
    print(f"🗂️ Таблиц ключей: {len(KEYS_TABLES)}")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("=" * 50)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
