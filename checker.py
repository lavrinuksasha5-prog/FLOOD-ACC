import asyncio
import os
import random
from telethon import TelegramClient, errors, functions
import phonenumbers

API_ID = int(os.getenv("API_ID", 123456))
API_HASH = os.getenv("API_HASH", "твой_api_hash")

MAX_CONCURRENT_TASKS = 10
USERS_PER_ACCOUNT = 10

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

async def check_one(session_path: str, proxy: dict | None, usernames_list: list, update_callback):
    client = TelegramClient(session_path, API_ID, API_HASH, proxy=proxy)
    result = {"session": os.path.basename(session_path), "name": "—", "phone": "—", "country": "—", "status": "Проверяю...", "wait_seconds": 0, "note": "0/10"}
    
    try:
        await client.connect()
        if not await client.is_user_authorized():
            result["status"] = "DEAD"
            result["note"] = "Не авторизована"
            await update_callback(result)
            return result

        me = await client.get_me()
        result["name"] = me.first_name or me.username or "—"
        result["phone"] = f"+{me.phone}" if me.phone else "—"
        result["country"] = get_country_code(result["phone"])
        await update_callback(result)

        # Берем случайные 10 из базы
        test_users = random.sample(usernames_list, min(USERS_PER_ACCOUNT, len(usernames_list)))
        checked_count = 0
        
        for target_user in test_users:
            success = False
            for attempt in range(3):
                try:
                    print(f"[{result['session']}] Ищу @{target_user} (попытка {attempt+1}/3)...")
                    await client(functions.contacts.ResolveUsernameRequest(username=target_user))
                    success = True
                    break
                except errors.FloodWaitError as e:
                    result["status"] = "FLOOD"
                    result["wait_seconds"] = e.seconds
                    result["note"] = f"Флуд на {checked_count + 1}-м"
                    await update_callback(result)
                    return result
                except errors.PeerFloodError:
                    result["status"] = "PEER_FLOOD"
                    result["note"] = f"Запрет (на {checked_count + 1}-м)"
                    await update_callback(result)
                    return result
                except (ConnectionError, TimeoutError, OSError) as e:
                    print(f"[{result['session']}] Сетевая ошибка (@{target_user}), попытка {attempt+1}/3. Ждем 3 сек...")
                    if attempt < 2:
                        await asyncio.sleep(3.0)
                except errors.rpcerrorlist.UsernameNotOccupiedError:
                    # Юзер удален, просто пропускаем
                    success = False 
                    break
                except Exception as e:
                    print(f"[{result['session']}] Ошибка @{target_user}: {type(e).__name__}")
                    success = False
                    break
            
            if success:
                checked_count += 1
                result["note"] = f"{checked_count}/{len(test_users)}"
                await update_callback(result)
                
                if checked_count >= USERS_PER_ACCOUNT:
                    break
                
                # Спим 30-61 секунду
                if checked_count < len(test_users):
                    delay = random.uniform(30.0, 61.0)
                    print(f"[{result['session']}] Сплю {int(delay)} сек...")
                    await asyncio.sleep(delay)
        
        if result["status"] == "Проверяю...":
            result["status"] = "OK"
            result["note"] = f"Найдено {checked_count}/{USERS_PER_ACCOUNT}"

    except errors.AuthKeyUnregisteredError:
        result["status"] = "DEAD"
        result["note"] = "AuthKey мертв"
    except Exception as e:
        result["status"] = "ERROR"
        result["note"] = str(e)
    finally:
        await client.disconnect()
        await update_callback(result)
    return result

async def worker(sess, proxies_pool, usernames_list, update_callback):
    try:
        temp_client = TelegramClient(sess, API_ID, API_HASH)
        await temp_client.connect()
        if not await temp_client.is_user_authorized():
            await update_callback({"session": os.path.basename(sess), "status": "DEAD", "name": "—", "phone": "—", "country": "—", "wait_seconds": 0, "note": "Не авторизована"})
            await temp_client.disconnect()
            return
        
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
            await update_callback({"session": os.path.basename(sess), "name": me.first_name or "—", "phone": phone, "country": acc_country, "status": "SKIP", "note": "Нет прокси", "wait_seconds": 0})
            return

        parts = chosen_proxy.split(":")
        proxy_dict = ("http", parts[0], int(parts[1]), True, parts[2], parts[3]) if len(parts) == 4 else ("http", parts[0], int(parts[1]))

        await check_one(sess, proxy_dict, usernames_list, update_callback)

    except Exception as e:
        await update_callback({"session": os.path.basename(sess), "status": "ERROR", "name": "—", "phone": "—", "country": "—", "note": str(e), "wait_seconds": 0})

async def check_all(sessions_dir: str, proxies: list[str], mode: str, update_callback):
    proxies_pool = {p: get_proxy_country_from_login(p) for p in proxies}

    usernames_list = []
    if os.path.exists("usernames.txt"):
        with open("usernames.txt", "r", encoding="utf-8") as f:
            usernames_list = [line.strip().replace("@", "") for line in f if line.strip()]
    if not usernames_list:
        usernames_list = ["durov"]

    sessions = [os.path.join(sessions_dir, f) for f in os.listdir(sessions_dir) if f.endswith(".session")]
    BATCH_SIZE = MAX_CONCURRENT_TASKS
    
    for i in range(0, len(sessions), BATCH_SIZE):
        batch = sessions[i:i + BATCH_SIZE]
        tasks = [asyncio.create_task(worker(sess, proxies_pool, usernames_list, update_callback)) for sess in batch]
        await asyncio.gather(*tasks)

    return True
