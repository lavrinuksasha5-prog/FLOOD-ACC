import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://flood-acc-production.up.railway.app/static/index.html")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить аккаунты", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("Нажми кнопку, чтобы открыть чекер:", reply_markup=kb)

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
