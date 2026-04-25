"""
routers/auth.py — Authentication endpoints for Pressroom.

Handles login (issuing JWTs) in both single-user and multi-user modes.

ENDPOINTS:
    POST /api/auth/login   — validate credentials, return JWT
    POST /api/auth/token   — save/update per-user GitHub token (multi-user mode)

SPEC REFERENCE: §9.1 "Authentication Flow"
         §12.1 "Authentication — Two Modes"
"""

import secrets

from fastapi import APIRouter, HTTPException

from auth_store import create_jwt_token
from config import APP_USER, APP_PASSWORD
from database import get_user_by_username
from auth import verify_password
from models import LoginRequest, LoginResponse, TokenUpdateRequest

router = APIRouter()


@router.post("/api/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """
    Validate credentials and return a signed JWT.

    Supports two modes (spec §12.1):

    SINGLE-USER MODE (default):
        Username and password are compared against the APP_USER / APP_PASSWORD
        environment variables using a timing-safe comparison.  On success,
        a JWT is issued with user_id equal to the username.

    MULTI-USER MODE:
        If the username is not the env-var admin, the SQLite users table is
        checked.  The stored bcrypt hash is verified with verify_password().
        On success, a JWT is issued with the row's user_id (UUID).

    RETURNS:
        {"access_token": "<jwt>", "token_type": "bearer"}

    RAISES:
        HTTP 401 if credentials are invalid in either mode.
    """
    # ── Single-user fast path ─────────────────────────────────────────────────
    # Use timing-safe comparison to prevent username/password enumeration.
    env_user_match = secrets.compare_digest(body.username.encode(), APP_USER.encode())
    env_pass_match = secrets.compare_digest(body.password.encode(), APP_PASSWORD.encode())

    if env_user_match and env_pass_match:
        token = create_jwt_token(user_id=body.username)
        return LoginResponse(access_token=token)

    # ── Multi-user path — check SQLite users table ────────────────────────────
    user = await get_user_by_username(body.username)
    if user and verify_password(body.password, user["password_hash"]):
        token = create_jwt_token(user_id=user["user_id"])
        return LoginResponse(access_token=token)

    # Identical error for both failure modes — do not reveal which part was wrong
    raise HTTPException(
        status_code=401,
        detail="Invalid username or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/api/auth/token")
async def save_github_token(body: TokenUpdateRequest):
    """
    Save or update the authenticated user's encrypted GitHub personal access token.

    This endpoint is for multi-user mode where each user stores their own
    GitHub token encrypted in the SQLite database.

    NOTE: Full implementation requires the caller to pass a valid JWT so we can
    extract the user_id.  Wired up to require_auth once JWT middleware is the
    primary auth method.  For now this is a placeholder that returns 501.

    SPEC REFERENCE: §9.2 "Per-User GitHub Token Storage"
    """
    # TODO: wire to require_auth Depends once JWT is the primary auth method,
    # then call auth_store.encrypt_token() + database.store_user_token()
    raise HTTPException(
        status_code=501,
        detail="Per-user GitHub token storage requires JWT auth — not yet wired up.",
    )
