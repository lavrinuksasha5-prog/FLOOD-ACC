from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import checker, asyncio, os, shutil, zipfile

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

_results = []
_running = False

@app.post("/upload/proxies")
async def upload_proxies(proxies: str = Form(...)):
    with open("proxies.txt", "w") as f:
        f.write(proxies)
    return {"status": "ok"}

@app.post("/upload/sessions")
async def upload_sessions(file: UploadFile = File(...)):
    os.makedirs("sessions", exist_ok=True)
    zip_path = f"temp_{file.filename}"
    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall("sessions")
    os.remove(zip_path)
    # Возвращаем список файлов
    files = [f for f in os.listdir("sessions") if f.endswith(".session") or os.path.isdir(os.path.join("sessions", f))]
    return {"status": "ok", "sessions": files}

@app.get("/check")
async def run_check():
    global _results, _running
    if _running:
        return {"status": "busy"}
    _running = True
    proxies = []
    if os.path.exists("proxies.txt"):
        with open("proxies.txt") as f:
            proxies = [l.strip() for l in f if l.strip()]
    _results = await checker.check_all("sessions", proxies)
    _running = False
    return {"status": "done", "count": len(_results)}

@app.get("/results")
async def get_results():
    return JSONResponse(_results)
