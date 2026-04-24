from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from auth import check_auth
from routers import config, papers, preview, publish, templates

app = FastAPI(title="Pressroom")

app.mount("/static", StaticFiles(directory="/app/static"), name="static")

app.include_router(config.router)
app.include_router(papers.router)
app.include_router(preview.router)
app.include_router(publish.router)
app.include_router(templates.router)


@app.get("/", response_class=HTMLResponse)
async def index(_: str = Depends(check_auth)):
    return HTMLResponse(Path("/app/static/index.html").read_text())
