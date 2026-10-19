import asyncio
import os
from telethon import TelegramClient, errors
from telethon.tl.functions.stories import CanSendStoryRequest
import phonenumbers
from phonenumbers import geocoder

API_ID = 123456
API_HASH = "твой_api_hash"

def get_country(phone: str) -> str:
    try:
        p = phonenumbers.parse(phone, None)
        return geocoder.description_for_number(p, "ru") or "—"
    except Exception:
        return "—"

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
        result["country"] = get_country(result["phone"])

        # Проверка FloodWait через лёгкий вызов
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
    sessions = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".session")]
    for i, sess in enumerate(sessions):
        proxy = None
        if i < len(proxies):
            proxy = ("socks5", proxies[i].split(":")[0], int(proxies[i].split(":")[1]))
        res = await check_one(sess, proxy)
        results.append(res)
        await asyncio.sleep(30)  # пауза между аккаунтами
    return results
