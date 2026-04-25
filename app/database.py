"""
database.py — SQLite database initialization and connection management.

This file is responsible for:
1. Creating the SQLite database file at /app/data/pressroom.db on first startup
2. Creating the three tables (users, user_tokens, tasks) if they don't exist
3. Providing a get_connection() context manager that yields sqlite3.Connection objects

DESIGN RATIONALE:
- SQLite is chosen over PostgreSQL/MySQL because it requires no separate server process
- The database file persists across container restarts via Docker volume mount (pressroom-data)
- All user data (tokens, tasks) is local to this container — no replication needed
- Single-writer pattern: FastAPI handles one request at a time per worker, so no mutex needed

SPEC REFERENCE: §7.1 "Stateless Design with Lightweight User Store"
         §9.1 "Authentication Flow" (user_tokens table)
         §10 "Non-Blocking UI" (tasks table)

DEPENDENCIES:
- This file is imported by main.py at startup (calls init_db())
- This file is imported by auth_store.py for token operations
- This file is imported by services/task_queue.py for task status updates
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator


# ──────────────────────────────────────────────────────────────────
# DATABASE PATH CONFIGURATION
# ──────────────────────────────────────────────────────────────────

DATABASE_PATH = "/app/data/pressroom.db"
"""
Path to the SQLite database file.

This path is mounted as a Docker volume so data persists
across container restarts. If the directory doesn't exist, init_db() creates it.
"""


# ──────────────────────────────────────────────────────────────────
# TABLE SCHEMAS
# ──────────────────────────────────────────────────────────────────

USERS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,           -- Unique identifier (e.g., UUID)
    username TEXT UNIQUE NOT NULL,      -- Human-readable username
    password_hash TEXT NOT NULL,        -- bcrypt hash of user's password
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- When account was created
);
"""
"""
Schema for the users table.

Each row represents one authenticated user. In single-user mode (APP_USER/APP_PASSWORD),
this table may be empty — authentication falls back to env vars.

Columns:
- user_id: Primary key, typically a UUID v4 string
- username: Unique human-readable name (e.g., "admin", "john")
- password_hash: bcrypt hash — NEVER store plain-text passwords
- created_at: Auto-populated by SQLite CURRENT_TIMESTAMP
"""

USER_TOKENS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_tokens (
    user_id TEXT PRIMARY KEY,           -- Foreign key referencing users.user_id
    encrypted_token TEXT NOT NULL,      -- AES-256-GCM ciphertext of GitHub token
    repo_url TEXT,                      -- Which workbench repo this token authenticates
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- Last time token was rotated
);
"""
"""
Schema for the user_tokens table.

Each row stores one encrypted GitHub personal access token for a user.
The token is encrypted at rest using AES-256-GCM with a key derived from JWT_SECRET.

Columns:
- user_id: Links to users.user_id (one token per user)
- encrypted_token: Ciphertext — meaningless without the master key
- repo_url: Which repository this token authenticates (e.g., "johndoe/ideas-workbench")
- updated_at: When the token was last rotated
"""

TASKS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,           -- Unique identifier for the async task
    user_id TEXT NOT NULL,              -- Which user initiated this task
    status TEXT DEFAULT 'pending',      -- pending | running | completed | failed
    result JSON,                        -- Serialized success result (e.g., {"pdf_path": "/tmp/..."})
    error TEXT,                         -- Error message if status is 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- When task was submitted
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- Last status change
);
"""
"""
Schema for the tasks table.

Each row tracks one async task (e.g., PDF generation, template upload).
The UI polls /api/status/{task_id} to check status and display progress.

Columns:
- task_id: UUID string, matches the ID returned when task is submitted
- user_id: Which user initiated this task
- status: Current state — UI shows different messages per status
- result: JSON blob on success (e.g., {"pdf_path": "/tmp/pressroom/my-paper/my-paper.pdf"})
- error: Error message string if status is 'failed'
- created_at / updated_at: Timestamps for debugging and SLA tracking
"""


# ──────────────────────────────────────────────────────────────────
# DATABASE INITIALIZATION
# ──────────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Initialize the SQLite database by creating tables if they don't exist.

    This function is called once at application startup from main.py.
    It ensures:
    1. The /app/data/ directory exists (creates it if needed)
    2. All three tables are created (no-op if they already exist)

    SIDE EFFECTS:
    - Creates /app/data/ directory on first run
    - Creates database file at DATABASE_PATH on first run
    - Tables are created lazily (only when init_db() is called)

    CALLER: app/main.py startup sequence (called before uvicorn.serve())

    EXAMPLE:
        # In main.py at startup:
        from database import init_db
        init_db()  # Creates tables if they don't exist
    """
    # Create data directory if it doesn't exist
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Open connection and create tables
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute(USERS_TABLE_SCHEMA)
        conn.execute(USER_TOKENS_TABLE_SCHEMA)
        conn.execute(TASKS_TABLE_SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────
# CONNECTION MANAGEMENT
# ──────────────────────────────────────────────────────────────────

@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    Get a SQLite database connection with row factory enabled.

    This is a context manager that yields a sqlite3.Connection object.
    The connection is automatically closed when the block exits.

    ROW FACTORY: conn.row_factory = sqlite3.Row enables dict-like access:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", ("abc123",)).fetchone()
        print(row["username"])  # Can access by column name
        print(row[0])          # Can also access by index

    USAGE EXAMPLE:
        # As a context manager (recommended):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", ("admin",)).fetchone()
            if row:
                print(f"Found user: {row['username']}")
        
        # With statement ensures connection is closed even if exception occurs

    SPEC REFERENCE: §7.1 "Stateless Design with Lightweight User Store"
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────────────────────────

async def create_user(user_id: str, username: str, password_hash: str) -> None:
    """
    Create a new user account.

    SECURITY NOTE:
    - password_hash should be generated using bcrypt.hashpw(password, bcrypt.gensalt())
    - NEVER accept plain-text passwords — always hash before storing
    - user_id should be a UUID v4: str(uuid.uuid4())

    CALLED BY: auth_store.py register_user() endpoint
    """
    import logging
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (user_id, username, password_hash) VALUES (?, ?, ?)",
                (user_id, username, password_hash)
            )
            conn.commit()
    except Exception as e:
        # Log error but don't expose sensitive info
        logging.error(f"Database error creating user {username}: {str(e)}")
        raise RuntimeError(f"Failed to create user: {str(e)}")


async def get_user_by_username(username: str) -> dict | None:
    """
    Look up a user by username.

    RETURN VALUE:
    - dict with keys: user_id, username, password_hash, created_at
    - None if username not found

    CALLED BY: auth_store.py verify_credentials() during login
    """
    import logging
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None
    except Exception as e:
        # Log error but don't expose sensitive info  
        logging.error(f"Database error retrieving user {username}: {str(e)}")
        raise RuntimeError(f"Failed to retrieve user: {str(e)}")


async def store_user_token(user_id: str, encrypted_token: str, repo_url: str) -> None:
    """
    Store an encrypted GitHub token for a user.

    PARAMETERS:
    - user_id: The user's ID (from users table)
    - encrypted_token: AES-256-GCM ciphertext of the GitHub token
    - repo_url: Which repository this token authenticates for

    SECURITY NOTE:
    - The encrypted_token is NEVER decrypted before storage — it stays ciphertext
    - Decryption happens at request time in auth_store.py get_decrypted_token()
    """
    import logging
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_tokens (user_id, encrypted_token, repo_url) VALUES (?, ?, ?)",
                (user_id, encrypted_token, repo_url)
            )
            conn.commit()
    except Exception as e:
        # Log error but don't expose sensitive info
        logging.error(f"Database error storing token for user {user_id}: {str(e)}")
        raise RuntimeError(f"Failed to store user token: {str(e)}")


async def get_user_token(user_id: str) -> str | None:
    """
    Retrieve a stored encrypted GitHub token for a user.

    RETURN VALUE:
    - str: The encrypted token ciphertext (to be decrypted by auth_store.py)
    - None: If no token exists for this user

    CALLED BY: auth_store.py get_decrypted_token() before GitHub API calls
    """
    import logging
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT encrypted_token FROM user_tokens WHERE user_id = ?", (user_id,)).fetchone()
            return row["encrypted_token"] if row else None
    except Exception as e:
        # Log error but don't expose sensitive info
        logging.error(f"Database error retrieving token for user {user_id}: {str(e)}")
        raise RuntimeError(f"Failed to retrieve user token: {str(e)}")


async def validate_user_credentials(username: str, plain_password: str) -> bool:
    """
    Validate user credentials by checking the plain-text password against the stored bcrypt hash.

    PARAMETERS:
    - username: The username to validate
    - plain_password: The plain-text password submitted by the user (NOT a hash)

    RETURNS:
    - bool: True if the password matches the stored bcrypt hash, False otherwise

    SECURITY NOTE:
    - Uses bcrypt.checkpw() via auth.verify_password() — never a plain string compare
    - Returns False (not an exception) when the user doesn't exist, to avoid timing leaks

    SPEC REFERENCE: §7.1 "Authentication Flow" — Credential Validation
    """
    import logging
    # Import here to avoid a circular import (auth imports config; database doesn't import auth at module level)
    from auth import verify_password
    try:
        user = await get_user_by_username(username)
        if not user:
            return False

        # Use bcrypt comparison — plain string equality would always fail against a bcrypt hash
        return verify_password(plain_password, user['password_hash'])

    except Exception as e:
        # Log error but don't expose sensitive info
        logging.error(f"Database error validating credentials for user {username}: {str(e)}")
        raise RuntimeError(f"Failed to validate user credentials: {str(e)}")


async def create_task(task_id: str, user_id: str) -> None:
    """
    Create a new task record with 'pending' status.

    CALLED BY: services/task_queue.py TaskQueue.submit() before executing task
    """
    import logging
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, user_id, status) VALUES (?, ?, 'pending')",
                (task_id, user_id)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Database error creating task {task_id} for user {user_id}: {e}")
        raise RuntimeError(f"Failed to create task: {e}")


async def update_task_status(task_id: str, status: str, result: dict = None, error: str = None) -> None:
    """
    Update a task's status, result, or error message.

    STATUS TRANSITIONS:
    - pending -> running (when task starts)
    - running -> completed (when task succeeds)
    - running -> failed (when task raises exception)

    CALLED BY: services/task_queue.py TaskQueue.submit() after executing task
    """
    import logging
    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, result = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                (status, result, error, task_id)
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Database error updating task {task_id} to status '{status}': {e}")
        raise RuntimeError(f"Failed to update task status: {e}")
