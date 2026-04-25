"""
auth.py — Authentication utilities for Pressroom.

This file is responsible for:
1. Basic HTTP Basic Auth middleware (check_auth)
2. JWT token creation and verification (stub functions)
3. Password hashing and verification (stub functions)

DESIGN RATIONALE:
- HTTP Basic Auth is simple and works well for single-user deployment
- JWT tokens will be used for API authentication in multi-user mode
- Password hashing uses bcrypt for secure storage

SPEC REFERENCE: §7 "Authentication"
         §7.1 "Basic Auth" (current implementation)
         §7.2 "JWT Token Authentication" (future multi-user mode)

DEPENDENCIES:
- This file imports: config (APP_USER, APP_PASSWORD)
- Imported by: main.py, routers/*.py (for authentication middleware)

AUTHENTICATION FLOW:
1. User accesses web UI → FastAPI requires Basic Auth credentials
2. check_auth() validates credentials against config values
3. If valid, user_id is returned and request proceeds
4. If invalid, 401 Unauthorized is returned

TODO: Implement JWT token functions (see module docstring for design)
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import APP_USER, APP_PASSWORD

# JWT library — add to requirements.txt when implementing:
#   PyJWT>=2.8.0
# For now, stub the JWT functions

security = HTTPBasic()


def check_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """
    Validate Basic Auth credentials and return username.
    
    PARAMETERS:
    - credentials: HTTPBasicCredentials from the request
    
    RETURNS:
    - str: username if authentication succeeds
    
    RAISES:
    - HTTPException(401) if authentication fails
    """
    ok_user = secrets.compare_digest(credentials.username.encode(), APP_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), APP_PASSWORD.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ──────────────────────────────────────────────────────────────────
# JWT TOKEN FUNCTIONS (STUBS — to be implemented)
# ──────────────────────────────────────────────────────────────────

def create_token(user_id: str, expires_minutes: int = 60) -> str:
    """
    Create a JWT token for the given user_id.
    
    PARAMETERS:
    - user_id: The authenticated user's ID
    - expires_minutes: Token expiration time in minutes
    
    RETURNS:
    - str: Encoded JWT token string
    
    TODO: Implement:
    1. Import jwt (PyJWT library)
    2. Create payload: {"user_id": user_id, "exp": datetime.utcnow() + timedelta(minutes=expires_minutes)}
    3. Encode with config.JWT_SECRET
    4. Return token string
    
    USAGE IN ROUTERS:
        # After successful login
        token = create_token(user_id)
        return {"access_token": token, "token_type": "bearer"}
    """
    # TODO: Implement when PyJWT is added to requirements.txt
    pass


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token.
    
    PARAMETERS:
    - token: JWT token string to verify
    
    RETURNS:
    - dict: Decoded payload with user_id and expiration info
    
    RAISES:
    - HTTPException(401) if token is invalid or expired
    
    TODO: Implement:
    1. Import jwt (PyJWT library)
    2. Decode with config.JWT_SECRET
    3. Return decoded payload dict
    """
    # TODO: Implement when PyJWT is added to requirements.txt
    pass


def hash_password(password: str) -> str:
    """
    Hash a password for secure storage.
    
    PARAMETERS:
    - password: Plain text password to hash
    
    RETURNS:
    - str: Hashed password string
    
    TODO: Implement:
    1. Import bcrypt library (add to requirements.txt)
    2. Return bcrypt.hash_password(password.encode(), salt=bcrypt.gensalt()).decode()
    """
    # TODO: Implement when bcrypt is added to requirements.txt
    pass


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    PARAMETERS:
    - plain_password: Plain text password to verify
    - hashed_password: Previously hashed password string
    
    RETURNS:
    - bool: True if password matches, False otherwise
    
    TODO: Implement:
    1. Import bcrypt library (add to requirements.txt)
    2. Return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    """
    # TODO: Implement when bcrypt is added to requirements.txt
    pass
