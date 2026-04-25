from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from auth import check_auth
from logging_config import get_logger
from routers import config, papers, preview, publish, templates

logger = get_logger(__name__)

app = FastAPI(title="Pressroom")

# Mount static files for the web UI
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

# Include API routers
app.include_router(config.router)
app.include_router(papers.router)
app.include_router(preview.router)
app.include_router(publish.router)
app.include_router(templates.router)

# Log application startup
logger.info("Pressroom application started")


@app.get("/", response_class=HTMLResponse)
async def index(_: str = Depends(check_auth)):
    """Serve the main web UI."""
    return HTMLResponse(Path("/app/static/index.html").read_text())


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for container orchestration and monitoring.
    
    Returns 200 OK with JSON status when the application is healthy.
    Used by Docker healthcheck and load balancers.
    
    SPEC REFERENCE: §13 "API Endpoints" — /api/health
             §14 "Deployment" — Docker health check integration
    
    RESPONSE FORMAT:
    {
        "status": "ok",
        "version": "1.0.0",
        "github_connected": true/false,
        "papers_count": 5
    }
    """
    # TODO: probe GitHub API and set this to True/False based on the result
    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": "1.0.0",
            "github_connected": None,  # None = not yet checked; False = confirmed down
        }
    )
