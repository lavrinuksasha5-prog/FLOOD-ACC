import asyncio
import uvicorn
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

# Берем токен из переменных окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Ссылка на твою Mini App (лучше тоже вынести в переменные окружения Railway)
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
    # Railway передает свой порт в переменную PORT. 
    # Если её нет (локальный запуск), используем 8080.
    port = int(os.getenv("PORT", 8080))
    
    # Настраиваем uvicorn
    config = uvicorn.Config("api:app", host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    
    # Запускаем веб-сервер в фоне
    asyncio.create_task(server.serve())
    
    # Запускаем бота
    print(f"Бот запущен. Веб-сервер слушает порт {port}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
