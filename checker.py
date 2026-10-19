import asyncio
import os
import random
import aiohttp
from telethon import TelegramClient, errors
from telethon.tl.functions.stories import CanSendStoryRequest
import phonenumbers
from phonenumbers import geocoder

API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "твой_api_hash")

# Функция для определения страны аккаунта
def get_country_code(phone: str) -> str:
    try:
        p = phonenumbers.parse(phone, None)
        return str(phonenumbers.region_code_for_number(p)) # Вернет PT для Португалии и т.д.
    except Exception:
        return "UNKNOWN"

# Функция для получения страны по IP прокси
async def get_proxy_country(proxy_str: str) -> str:
    # proxy_str в формате host:port:user:pass или socks5://host:port
    host = proxy_str.split(":")[0].replace("socks5://", "").replace("http://", "")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://ip-api.com/json/{host}") as resp:
                data = await resp.json()
                return data.get("countryCode", "UNKNOWN")
    except Exception:
        return "UNKNOWN"

async def check_one(session_path: str, proxy: dict | None):
    client = TelegramClient(session_path, API_ID, API_HASH, proxy=proxy)
    result = {
        "session": os.path.basename(session_path),
        "name": "—",
        "phone": "—",
        "country": "—",
        "status": "OK",
        "wait_seconds": 0,
        "note": ""
    }
    try:
        await client.connect()
        if not await client.is_user_authorized():
            result["status"] = "DEAD"
            result["note"] = "Сессия не авторизована"
            return result

        me = await client.get_me()
        result["name"] = me.first_name or me.username or "—"
        result["phone"] = f"+{me.phone}" if me.phone else "—"
        result["country"] = get_country_code(result["phone"])

        # Проверка FloodWait
        try:
            await client(CanSendStoryRequest(peer=me))
        except errors.FloodWaitError as e:
            result["status"] = "FLOOD"
            result["wait_seconds"] = e.seconds
        except errors.rpcerrorlist.StorySendFloodWeeklyError as e:
            result["status"] = "FLOOD_WEEKLY"
            result["wait_seconds"] = e.seconds
        except errors.rpcerrorlist.StorySendFloodMonthlyError as e:
            result["status"] = "FLOOD_MONTHLY"
            result["wait_seconds"] = e.seconds
        except Exception as e:
            result["note"] = f"canSendStory: {type(e).__name__}"

    except errors.AuthKeyUnregisteredError:
        result["status"] = "DEAD"
        result["note"] = "AuthKey недействителен"
    except Exception as e:
        result["status"] = "ERROR"
        result["note"] = f"{type(e).__name__}: {e}"
    finally:
        await client.disconnect()
    return result

async def check_all(sessions_dir: str, proxies: list[str]):
    results = []
    
    # 1. Заранее узнаем, из каких стран наши прокси
    proxy_countries = {}
    for p in proxies:
        country = await get_proxy_country(p)
        proxy_countries[p] = country
        await asyncio.sleep(1) # пауза чтобы ip-api не забанил

    # 2. Находим все сессии
    sessions = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".session")]

    for i, sess in enumerate(sessions):
        # Получаем телефон из сессии без подключения к сети, чтобы узнать страну
        temp_client = TelegramClient(sess, API_ID, API_HASH)
        await temp_client.connect()
        if not await temp_client.is_user_authorized():
            results.append({"session": os.path.basename(sess), "status": "DEAD", "note": "Не авторизована"})
            await temp_client.disconnect()
            continue
        
        me = await temp_client.get_me()
        phone = f"+{me.phone}" if me.phone else ""
        acc_country = get_country_code(phone)
        await temp_client.disconnect()

        # Ищем подходящий прокси
        chosen_proxy = None
        for p_url, p_country in proxy_countries.items():
            if p_country == acc_country:
                chosen_proxy = p_url
                break
        
        if not chosen_proxy:
            results.append({
                "session": os.path.basename(sess), 
                "name": me.first_name or "—", 
                "phone": phone, 
                "country": acc_country, 
                "status": "SKIP", 
                "note": "Нет прокси для этой страны (защита от бана)"
            })
            continue

        # Форматируем прокси для Telethon
        if "socks5://" in chosen_proxy:
            parts = chosen_proxy.replace("socks5://", "").split(":")
            proxy_dict = ("socks5", parts[0], int(parts[1]), True, parts[2], parts[3]) if len(parts) == 4 else ("socks5", parts[0], int(parts[1]))
        else:
             parts = chosen_proxy.split(":")
             proxy_dict = ("socks5", parts[0], int(parts[1]), True, parts[2], parts[3]) if len(parts) == 4 else ("socks5", parts[0], int(parts[1]))

        # 3. Запускаем проверку с правильной задержкой
        res = await check_one(sess, proxy_dict)
        results.append(res)
        
        # Безопасная задержка: от 60 до 120 секунд
        if i < len(sessions) - 1:
            sleep_time = random.randint(60, 120)
            await asyncio.sleep(sleep_time)
            
    return results
