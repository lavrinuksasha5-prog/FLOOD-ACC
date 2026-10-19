import asyncio
import os
import random
from telethon import TelegramClient, errors
from telethon.tl.functions.stories import CanSendStoryRequest
import phonenumbers
from phonenumbers import geocoder

API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "твой_api_hash")

# Сколько аккаунтов проверяем ОДНОВРЕМЕННО (чтобы сервер не упал)
MAX_CONCURRENT_TASKS = 30

def get_country_code(phone: str) -> str:
    try:
        p = phonenumbers.parse(phone, None)
        return str(phonenumbers.region_code_for_number(p))
    except Exception:
        return "UNKNOWN"

def get_proxy_country_from_login(proxy_str: str) -> str:
    if "country-" in proxy_str:
        try:
            return proxy_str.split("country-")[1][:2].upper()
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
                await client( eCanSendStoryRequest(peer=me))
            except errors.FloodWaitError as. e:
                resultseconds["status"] = "FLOOD"
                result["wait_seconds"] = e.seconds
            except errors.rpcerrorlist.StorySendFloodWeeklyError as e:
                result["status"] = "FLOOD_WEEKLY"
                result["wait_seconds"] =
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

# Воркер, который берет задачи из очереди и выполняет их
async def worker(queue, proxies_pool, results_list, mode, semaphore):
    while True:
        sess = await queue.get()
        if sess is None:
            break
            
        async with semaphore: # Ограничитель параллельности (30 штук)
            try:
                # Определяем страну аккаунта
                temp_client = TelegramClient(sess, API_ID, API_HASH)
                await temp_client.connect()
                if not await temp_client.is_user_authorized():
                    results_list.append({"session": os.path.basename(sess), "status": "DEAD", "note": "Не авторизована"})
                    await temp_client.disconnect()
                    queue.task_done()
                    continue
                
                me = await temp_client.get_me()
                phone = f"+{me.phone}" if me.phone else ""
                acc_country = get_country_code(phone)
                await temp_client.disconnect()

                # Ищем прокси для страны
                chosen_proxy = None
                for p_url, p_country in proxies_pool.items():
                    if p_country == acc_country:
                        chosen_proxy = p_url
                        break
                
                if not chosen_proxy:
                    results_list.append({"session": os.path.basename(sess), "name": me.first_name or "—", "phone": phone, "country": acc_country, "status": "SKIP", "note": "Нет прокси"})
                    queue.task_done()
                    continue

                # Парсим прокси
                parts = chosen_proxy.split(":")
                proxy_dict = ("socks5", parts[0], int(parts[1]), True, parts[2], parts[3]) if len(parts) == 4 else ("socks5", parts[0], int(parts[1]))

                # Проверяем
                res = await check_one(sess, proxy_dict, mode)
                results_list.append(res)
                
                # Небольшая пауза между запросами внутри потока, чтобы не спамить жестко
                await asyncio.sleep(1) 

            except Exception as e:
                results_list.append({"session": os.path.basename(sess), "status": "ERROR", "note": str(e)})
            finally:
                queue.task_done()

async def check_all(sessions_dir: str, proxies: list[str], mode: str):
    results = []
    
    proxies_pool = {}
    for p in proxies:
        proxies_pool[p] = get_proxy_country_from_login(p)

    sessions = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".session")]
    queue = asyncio.Queue()
    
    for sess in sessions:
        queue.put_nowait(sess)

    # Создаем ограничитель (не более 30 одновременных проверок)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    # Запускаем воркеры
    workers = []
    for _ in range(MAX_CONCURRENT_TASKS):
        task = asyncio.create_task(worker(queue, proxies_pool, results, mode, semaphore))
        workers.append(task)

    # Ждем завершения всех задач
    await queue.join()

    for _ in range(len(workers)):
        await queue.put(None)
    await asyncio.gather(*workers)

    return results
