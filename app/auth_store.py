"""
auth_store.py — JWT authentication and per-user GitHub token management.

This file is responsible for:
1. Creating and verifying JWT tokens for authenticated users
2. Storing encrypted GitHub tokens in the SQLite database (via database.py)
3. Decrypting stored tokens before GitHub API calls
4. Providing an authentication middleware decorator for FastAPI routes

DESIGN RATIONALE:
- JWT tokens are stateless on the server — no session storage needed
- GitHub tokens are encrypted at rest using AES-256-GCM
- The master key for decryption is derived from JWT_SECRET (stored in env var)
- This separation means: even if database is stolen, tokens require JWT_SECRET to decrypt

SPEC REFERENCE: §9.1 "Authentication Flow"
         §9.2 "Per-User GitHub Token Storage"
         §12.1 "Authentication — Two Modes"

DEPENDENCIES:
- This file imports from: database (store_user_token, get_user_token), config (JWT_SECRET)
- This file is imported by: main.py (startup JWT_SECRET validation), routers (auth dependencies)

FLOW SINGLE-USER MODE:
1. User submits admin/pressroom credentials
2. Server validates against APP_USER/APP_PASSWORD env vars
3. Server issues JWT token with user_id="admin"
4. Subsequent requests include JWT in Authorization header
5. Middleware extracts user_id from JWT
6. GitHub API calls use global tokens from env vars (single-user mode)

FLOW MULTI-USER MODE:
1. User submits username/password credentials
2. Server validates against SQLite users table (database.py get_user_by_username)
3. Server issues JWT token with user_id="<uuid>"
4. Subsequent requests include JWT in Authorization header
5. Middleware extracts user_id from JWT
6. GitHub API calls use per-user tokens from SQLite (database.py get_user_token)
7. Token is decrypted before use (AES-256-GCM with derived master key)
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# ──────────────────────────────────────────────────────────────────
# JWT TOKEN CREATION AND VERIFICATION
# ──────────────────────────────────────────────────────────────────

def create_jwt_token(user_id: str, expiry_minutes: int = 480) -> str:
    """
    Create a signed JWT token for an authenticated user.

    PARAMETERS:
    - user_id:        Unique identifier for the authenticated user
    - expiry_minutes: Validity window in minutes (default 480 = 8 hours)

    RETURNS:
    - str: Encoded JWT (send as Authorization: Bearer <token>)

    CALLED BY: /api/auth/login after successful credential validation
    """
    # Delegate to auth.py which owns the canonical JWT implementation
    from auth import create_token
    return create_token(user_id, expires_minutes=expiry_minutes)


def verify_jwt_token(token: str) -> dict:
    """
    Verify a JWT token and return its decoded payload.

    PARAMETERS:
    - token: JWT string from Authorization: Bearer <token> header

    RETURNS:
    - dict: Decoded payload containing at least {"user_id": ..., "exp": ..., "iat": ...}

    RAISES:
    - HTTPException(401): if the token is expired or has an invalid signature

    CALLED BY: AuthMiddleware below, and any router that validates Bearer tokens
    """
    # Delegate to auth.py which owns the canonical JWT implementation
    from auth import verify_token
    return verify_token(token)


# ──────────────────────────────────────────────────────────────────
# TOKEN ENCRYPTION AND DECRYPTION
# ──────────────────────────────────────────────────────────────────

def encrypt_token(plain_token: str, user_id: str) -> bytes:
    """
    Encrypt a GitHub personal access token for storage in SQLite.

    This function is called when a user saves or updates their GitHub token.
    The encrypted output is stored in the user_tokens table (database.py).

    PARAMETERS:
    - plain_token: The plain-text GitHub token (e.g., "ghp_xxxxxxxxxxxx")
    - user_id: The user's ID — used to derive a unique encryption key per user
    
    RETURNS:
    - bytes: The encrypted token (IV + ciphertext + authentication tag)
    
    ENCRYPTION DETAILS:
    - Algorithm: AES-256-GCM (authenticated encryption)
    - Key derivation: PBKDF2 with SHA256, derived from JWT_SECRET + user_id
    - IV (Initialization Vector): Random 96-bit value, prepended to ciphertext
    
    WHY PER-USER KEY?
    - Even if two users have the same GitHub token, their stored ciphertexts are different
    - This prevents correlation attacks where an attacker determines if two users
      use the same token
    
    TODO: Replace pass with actual implementation:
    - Import AESGCM from cryptography.hazmat.primitives.ciphers.aead
    - Derive master key using PBKDF2(JWT_SECRET + user_id)
    - Generate random IV using secrets.token_bytes(12)
    - Encrypt using AESGCM(master_key).encrypt(iv, plain_token.encode(), None)
    - Return iv + ciphertext
    
    SECURITY NOTE:
    - The plain_token is NEVER logged or returned
    - The encrypted output can be stored in plaintext in the database
    - Decryption requires both the ciphertext AND the JWT_SECRET
    
    CALLED BY: /api/auth/token endpoint when user saves GitHub token
    """
    import secrets as _secrets
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from config import JWT_SECRET

    # Derive a unique 256-bit AES key for this user from the master secret.
    # PBKDF2 turns the text JWT_SECRET into a proper cryptographic key.
    # Using user_id as the salt means each user gets a different key even
    # if two users have the same plain_token value.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,           # 32 bytes = 256 bits for AES-256
        salt=user_id.encode(),
        iterations=100_000,  # NIST minimum for PBKDF2-SHA256
    )
    master_key = kdf.derive(JWT_SECRET.encode())

    # Random 96-bit IV — must be unique per encryption but not secret
    iv = _secrets.token_bytes(12)

    ciphertext = AESGCM(master_key).encrypt(iv, plain_token.encode(), None)

    # Prepend IV so decrypt_token can recover it without separate storage
    return iv + ciphertext


def decrypt_token(encrypted: bytes, user_id: str) -> str:
    """
    Decrypt a stored GitHub token back to plain text.

    PARAMETERS:
    - encrypted: IV + ciphertext bytes as returned by encrypt_token()
    - user_id:   The user's ID — used to re-derive the same per-user key

    RETURNS:
    - str: The decrypted plain-text GitHub token

    RAISES:
    - cryptography.exceptions.InvalidTag: if the ciphertext was tampered with
                                          or the wrong JWT_SECRET is in use
    """
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from config import JWT_SECRET

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=user_id.encode(),
        iterations=100_000,
    )
    master_key = kdf.derive(JWT_SECRET.encode())

    # IV is the first 12 bytes; the rest is ciphertext + GCM authentication tag
    iv         = encrypted[:12]
    ciphertext = encrypted[12:]

    try:
        plaintext = AESGCM(master_key).decrypt(iv, ciphertext, None)
    except Exception as exc:
        from exceptions import TokenDecryptionError
        raise TokenDecryptionError(
            "GitHub token decryption failed — the ciphertext may be corrupted "
            "or JWT_SECRET has changed since the token was stored."
        ) from exc
    return plaintext.decode()


# ──────────────────────────────────────────────────────────────────
# AUTHENTICATION MIDDLEWARE
# ──────────────────────────────────────────────────────────────────

class AuthMiddleware:
    """
    Starlette/FastAPI middleware that validates JWT Bearer tokens on every request.

    PUBLIC ROUTES (bypassed — no token required):
    - /api/health
    - /api/auth/login
    - /static/*

    All other routes must supply a valid Authorization: Bearer <token> header.
    On success, request.state.user_id is set for downstream route handlers.
    """

    # Routes that don't require authentication
    _PUBLIC_PREFIXES = ("/api/health", "/api/auth/login", "/static")

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Only intercept HTTP requests — pass websockets and lifespan events through
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request
        from starlette.responses import JSONResponse

        request = Request(scope, receive, send)
        path = request.url.path

        # Allow public routes through without a token
        if any(path.startswith(prefix) for prefix in self._PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Extract the Bearer token from the Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing or not Bearer"}
            )
            await response(scope, receive, send)
            return

        token = auth_header[len("Bearer "):]

        try:
            payload = verify_jwt_token(token)
            # Attach user_id to request state for route handlers
            request.state.user_id = payload["user_id"]
        except Exception:
            # verify_jwt_token already raises HTTPException(401) for bad tokens;
            # catch anything else too so we never return a raw 500 from middleware
            response = JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"}
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> str:
    """
    FastAPI dependency that extracts and validates a Bearer JWT, returning user_id.

    Usage in route handlers:
        @router.get("/api/papers")
        async def list_papers(user_id: str = Depends(require_auth)):
            ...

    RAISES:
    - HTTPException(401): if credentials are missing or the token is invalid/expired
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    payload = verify_jwt_token(credentials.credentials)
    return payload["user_id"]


# ──────────────────────────────────────────────────────────────────
# PER-USER CONFIG RESOLUTION (MULTI-USER MODE)
# ──────────────────────────────────────────────────────────────────

async def get_user_config(user_id: str) -> dict:
    """
    Get per-user configuration including decrypted GitHub token.

    This function resolves the user's configuration from the SQLite store.
    In single-user mode, it returns env var values (fallback).

    PARAMETERS:
    - user_id: The authenticated user's ID
    
    RETURNS:
    - dict with keys:
        - github_user: GitHub username (e.g., "johndoe")
        - github_token: Decrypted personal access token
        - workbench_repo: Owner/repo format (e.g., "johndoe/ideas-workbench")
        - pubs_repo: Owner/repo format (e.g., "johndoe/pressroom-pubs")
        - branch: Git branch (default: "main")
        - pdf_engine: PDF engine override (from user config, defaults to global)

    TODO: Implement for multi-user mode:
    1. Connect to database using get_connection()
    2. Execute SELECT encrypted_token, repo_url FROM user_tokens WHERE user_id = ?
    3. Decrypt token using decrypt_token()
    4. Return config dict
    
    SINGLE-USER FALLBACK (current behavior):
    Returns env var values from config module:
    {
        "github_user": config.IDEAS_WORKBENCH_GIT_USER,
        "github_token": config.IDEAS_WORKBENCH_GIT_TOKEN,
        "workbench_repo": config.IDEAS_WORKBENCH_REPO,
        "pubs_repo": config.PRESSROOM_PUBS_REPO,
        "branch": config.GITHUB_BRANCH,
        "pdf_engine": config.PDF_ENGINE,
    }

    CALLED BY: github.py get_gh_client(user_id) before every GitHub API call
    """
    # TODO: Implement per-user config resolution
    
    # SINGLE-USER FALLBACK (current behavior — when multi-user not enabled)
    from config import (
        IDEAS_WORKBENCH_GIT_USER,
        IDEAS_WORKBENCH_GIT_TOKEN,
        IDEAS_WORKBENCH_REPO,
        PRESSROOM_PUBS_REPO,
        GITHUB_BRANCH,
        PDF_ENGINE,
    )
    
    return {
        "github_user": IDEAS_WORKBENCH_GIT_USER,
        "github_token": IDEAS_WORKBENCH_GIT_TOKEN,
        "workbench_repo": IDEAS_WORKBENCH_REPO,
        "pubs_repo": PRESSROOM_PUBS_REPO,
        "branch": GITHUB_BRANCH,
        "pdf_engine": PDF_ENGINE,
    }