from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from starlette.requests import Request as _Request
from auth import check_auth
from logging_config import get_logger, RequestIDMiddleware
from exceptions import PressroomException
import logging as _logging
import shutil
from routers import config, papers, preview, publish, templates, prompts, auth as auth_router, status as status_router
from routers.publish import _limiter
from database import init_db
from config import validate_config, validate_api_keys, IDEAS_WORKBENCH_REPO, TEMP_DIR
from github import gh_list, WORKBENCH_HEADERS

# ── Root logger setup (spec §13.1) ───────────────────────────────────────────
# Configure once at startup so every module's logger inherits JSON formatting.
# Individual modules call get_logger(__name__) which attaches to this root.
_logging.getLogger("pressroom").setLevel(_logging.INFO)

logger = get_logger(__name__)

# ── Startup validation ────────────────────────────────────────────────────────
# Fail fast if required environment variables are missing or tokens look wrong.
validate_config(["IDEAS_WORKBENCH_GIT_TOKEN", "PRESSROOM_PUBS_GIT_TOKEN",
                 "IDEAS_WORKBENCH_REPO", "PRESSROOM_PUBS_REPO"])
validate_api_keys()

# ── Temp directory cleanup (spec §18) ────────────────────────────────────────
# PDF temp files under /tmp/pressroom/ are never deleted during a run, so they
# accumulate across preview calls.  Wipe on startup so disk usage stays bounded.
# Files are regenerated on demand — nothing here is persistent state.
_tmp = TEMP_DIR  # Path("/tmp/pressroom") from config
if _tmp.exists():
    shutil.rmtree(_tmp, ignore_errors=True)
_tmp.mkdir(parents=True, exist_ok=True)

# Initialize database at startup
init_db()

app = FastAPI(title="Pressroom")

# Attach the rate limiter state and its 429 error handler to the app so that
# @_limiter.limit() decorators on route functions work correctly.
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(PressroomException)
async def pressroom_exception_handler(_request: _Request, exc: PressroomException):
    """
    Convert any PressroomException subclass into a structured JSON error response.

    All custom exceptions carry an error_code, http_status, and optional details
    dict — this handler surfaces them consistently so the frontend always receives:
        {"error": {"code": "...", "message": "...", "details": {...}}}

    SPEC REFERENCE: exceptions.py error response format
    """
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": {
                "code":    exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )

# Mount static files for the web UI
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

# Include API routers
app.include_router(auth_router.router)
app.include_router(status_router.router)
app.include_router(config.router)
app.include_router(papers.router)
app.include_router(preview.router)
app.include_router(publish.router)
app.include_router(templates.router)
app.include_router(prompts.router)

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
        "github_connected": true/false
    }
    """
    # Probe GitHub by listing the root of ideas-workbench.
    # gh_list returns [] on 404 but raises on auth/network errors,
    # so any non-empty list or an empty-but-successful response means connected.
    github_connected = False
    try:
        await gh_list(IDEAS_WORKBENCH_REPO, "", headers=WORKBENCH_HEADERS)
        github_connected = True
    except Exception:
        # Log but don't crash the health endpoint — callers need the 200 to know
        # the app itself is up even when GitHub is temporarily unreachable.
        logger.warning("Health check: GitHub connectivity probe failed")

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok",
            "version": "1.0.0",
            "github_connected": github_connected,
        }
    )
