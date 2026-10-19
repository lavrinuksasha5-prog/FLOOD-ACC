from fastapi import FastAPI, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import checker, asyncio, os, shutil, zipfile

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

_results = {}
_running = False

@app.post("/upload/proxies")
async def upload_proxies(proxies: str = Form(...)):
    with open("proxies.txt", "w") as f: f.write(proxies)
    return {"status": "ok"}

@app.post("/upload/sessions")
async def upload_sessions(file: UploadFile = File(...)):
    if os.path.exists("sessions"): shutil.rmtree("sessions", ignore_errors=True)
    os.makedirs("sessions", mode=0o777, exist_ok=True)
    zip_path = f"temp_{file.filename}"
    with open(zip_path, "wb") as buffer: shutil.copyfileobj(file.file, buffer)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref: zip_ref.extractall("sessions")
    os.remove(zip_path)
    os.system("chmod -R 777 sessions")
    
    # При новой загрузке ZIP очищаем результаты
    global _results
    _results = {}
    
    files = [f for f in os.listdir("sessions") if f.endswith(".session")]
    return {"status": "ok", "sessions": len(files)}

@app.post("/upload/usernames_file")
async def upload_usernames_file(file: UploadFile = File(...)):
    content = await file.read()
    with open("usernames.txt", "wb") as f: f.write(content)
    return {"status": "ok"}

@app.post("/upload/usernames")
async def upload_usernames(usernames: str = Form(...)):
    with open("usernames.txt", "w", encoding="utf-8") as f: f.write(usernames)
    return {"status": "ok"}

async def run_check_background(mode: str):
    global _results, _running
    _results = {}  # Всегда с чистого листа при запуске
    _running = True
    proxies = []
    if os.path.exists("proxies.txt"):
        with open("proxies.txt") as f: proxies = [l.strip() for l in f if l.strip()]
    try:
        async def update_result(res):
            _results[res["session"]] = res
        await checker.check_all("sessions", proxies, mode, update_result)
    except Exception as e:
        print(f"Ошибка в фоне: {e}")
    finally:
        _running = False

@app.get("/check")
async def run_check(background_tasks: BackgroundTasks, mode: str = Query("flood")):
    global _running
    if _running: return {"status": "busy"}
    background_tasks.add_task(run_check_background, mode)
    return {"status": "started"}

@app.get("/results")
async def get_results():
    return JSONResponse({"running": _running, "results": list(_results.values())})
