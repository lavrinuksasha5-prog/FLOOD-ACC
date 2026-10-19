import asyncio
import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_ЕСЛИ_ЛОКАЛЬНО")
# Railway выдаст домен, его нужно будет вставить сюда или в переменные окружения
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://твой-домен.up.railway.app/static/index.html")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message()
async def start(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить аккаунты", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    await message.answer("Нажми кнопку, чтобы открыть чекер:", reply_markup=kb)

async def main():
    # Запускаем FastAPI сервер в фоне
    config = uvicorn.Config("api:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
    server = uvicorn.Server(config)
    asyncio.create_task(server.serve())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
