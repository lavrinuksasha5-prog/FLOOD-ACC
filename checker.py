import asyncio
import os
import random
from telethon import TelegramClient, errors
from telethon.tl.functions.stories import CanSendStoryRequest
import phonenumbers
from phonenumbers import geocoder

API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "твой_api_hash")

def get_country_code(phone: str) -> str:
    try:
        p = phonenumbers.parse(phone, None)
        return str(phonenumbers.region_code_for_number(p))
    except Exception:
        return "UNKNOWN"

# Новая функция: берем страну из логина прокси, а не из IP
def get_proxy_country_from_login(proxy_str: str) -> str:
    # Ищем в строке паттерн country-XX
    if "country-" in proxy_str:
        try:
            part = proxy_str.split("country-")[1]
            return part[:2].upper() # Вернет KZ, PT, SE и т.д.
        except:
            return "UNKNOWN"
    return "UNKNOWN"

async def check_one(session_path: str, proxy: dict | None, mode: str):
    client = TelegramClient(session_path, API_ID, API_HASH, proxy=proxy)
    result = {"session": os.path.basename(session_path), "name": "—", "phone": "—", "country": "—", "status": "OK", "wait_seconds": 0, "note": ""}
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

        if mode == "flood":
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

async def check_all(sessions_dir: str, proxies: list[str], mode: str):
    results = []
    
    # 1. Собираем страны прокси из логинов
    proxy_countries = {}
    for p in proxies:
        country = get_proxy_country_from_login(p)
        proxy_countries[p] = country

    sessions = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".session")]

    for i, sess in enumerate(sessions):
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

        # 2. Ищем прокси по стране из логина
        chosen_proxy = None
        for p_url, p_country in proxy_countries.items():
            if p_country == acc_country:
                chosen_proxy = p_url
                break
        
        if not chosen_proxy:
            results.append({"session": os.path.basename(sess), "name": me.first_name or "—", "phone": phone, "country": acc_country, "status": "SKIP", "note": "Нет прокси для этой страны"})
            continue

        # Парсим прокси в формат Telethon
        parts = chosen_proxy.split(":")
        # Если формат host:port:user:pass
        if len(parts) == 4:
            proxy_dict = ("socks5", parts[0], int(parts[1]), True, parts[2], parts[3])
        else:
            proxy_dict = ("socks5", parts[0], int(parts[1]))

        res = await check_one(sess, proxy_dict, mode)
        results.append(res)
        
        if i < len(sessions) - 1:
            sleep_time = random.randint(30, 60) if mode == "valid" else random.randint(60, 120)
            await asyncio.sleep(sleep_time)
            
    return results
