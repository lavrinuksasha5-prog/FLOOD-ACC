from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import checker, asyncio, os

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

_results = []
_running = False

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
