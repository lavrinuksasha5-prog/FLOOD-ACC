import asyncio
import os
import random
from telethon import TelegramClient, errors, functions
import phonenumbers

API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "твой_api_hash")

MAX_CONCURRENT_TASKS = 10  # 10 аккаунтов ебашат одновременно
USERS_PER_ACCOUNT = 10     # По 10 юзеров на аккаунт

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

async def check_one(session_path: str, proxy: dict | None, usernames_list: list):
    client = TelegramClient(session_path, API_ID, API_HASH, proxy=proxy)
    result = {"session": os.path.basename(session_path), "name": "—", "phone": "—", "country": "—", "status": "OK", "wait_seconds": 0, "note": ""}
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            result["status"] = "DEAD"
            result["note"] = "Не авторизована"
            return result

        me = await client.get_me()
        result["name"] = me.first_name or me.username or "—"
        result["phone"] = f"+{me.phone}" if me.phone else "—"
        result["country"] = get_country_code(result["phone"])

        test_users = random.sample(usernames_list, min(USERS_PER_ACCOUNT, len(usernames_list)))
        
        checked_count = 0
        for target_user in test_users:
            try:
                await client(functions.contacts.ResolveUsernameRequest(username=target_user))
                checked_count += 1
                
                # 🔥 ЗАДЕРЖКА ОТ 30 ДО 61 СЕКУНДЫ
                if checked_count < len(test_users):
                    delay = random.uniform(30.0, 61.0)
                    await asyncio.sleep(delay)
                    
            except errors.FloodWaitError as e:
                result["status"] = "FLOOD"
                result["wait_seconds"] = e.seconds
                result["note"] = f"Флуд на {checked_count + 1}-м юзере (@{target_user})"
                break
            except errors.PeerFloodError:
                result["status"] = "PEER_FLOOD"
                result["note"] = f"Запрет на поиск (на {checked_count + 1}-м юзере)"
                break
            except Exception as e:
                result["note"] = f"Ошибка на {checked_count + 1}-м: {type(e).__name__}"
                break 
        
        if result["status"] == "OK":
            result["note"] = f"Успешно найдено {checked_count} юзеров"

    except errors.AuthKeyUnregisteredError:
        result["status"] = "DEAD"
        result["note"] = "AuthKey недействителен"
    except Exception as e:
        result["status"] = "ERROR"
        result["note"] = f"{type(e).__name__}: {e}"
    finally:
        await client.disconnect()
    return result

async def worker(queue, proxies_pool, usernames_list, semaphore, update_callback):
    while True:
        sess = await queue.get()
        if sess is None:
            break
            
        async with semaphore:
            try:
                temp_client = TelegramClient(sess, API_ID, API_HASH)
                await temp_client.connect()
                if not await temp_client.is_user_authorized():
                    res = {"session": os.path.basename(sess), "status": "DEAD", "name": "—", "phone": "—", "country": "—", "wait_seconds": 0, "note": "Не авторизована"}
                    await update_callback(res)
                    await temp_client.disconnect()
                    continue
                
                me = await temp_client.get_me()
                phone = f"+{me.phone}" if me.phone else ""
                acc_country = get_country_code(phone)
                await temp_client.disconnect()

                chosen_proxy = None
                for p_url, p_country in proxies_pool.items():
                    if p_country == acc_country:
                        chosen_proxy = p_url
                        break
                
                if not chosen_proxy:
                    res = {"session": os.path.basename(sess), "name": me.first_name or "—", "phone": phone, "country": acc_country, "status": "SKIP", "note": "Нет прокси", "wait_seconds": 0}
                    await update_callback(res)
                    continue

                parts = chosen_proxy.split(":")
                proxy_dict = ("http", parts[0], int(parts[1]), True, parts[2], parts[3]) if len(parts) == 4 else ("http", parts[0], int(parts[1]))

                res = await check_one(sess, proxy_dict, usernames_list)
                await update_callback(res)

            except Exception as e:
                res = {"session": os.path.basename(sess), "status": "ERROR", "name": "—", "phone": "—", "country": "—", "note": str(e), "wait_seconds": 0}
                await update_callback(res)
            finally:
                queue.task_done()

async def check_all(sessions_dir: str, proxies: list[str], mode: str, update_callback):
    proxies_pool = {}
    for p in proxies:
        proxies_pool[p] = get_proxy_country_from_login(p)

    usernames_list = []
    if os.path.exists("usernames.txt"):
        with open("usernames.txt", "r", encoding="utf-8") as f:
            usernames_list = [line.strip().replace("@", "") for line in f if line.strip()]
    
    if not usernames_list:
        usernames_list = ["durov"]

    sessions = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".session")]
    queue = asyncio.Queue()
    
    for sess in sessions:
        queue.put_nowait(sess)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    workers = []
    for _ in range(MAX_CONCURRENT_TASKS):
        task = asyncio.create_task(worker(queue, proxies_pool, usernames_list, semaphore, update_callback))
        workers.append(task)

    await queue.join()
    for _ in range(len(workers)):
        await queue.put(None)
    await asyncio.gather(*workers)

    return True
