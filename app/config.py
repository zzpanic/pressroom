"""
config.py — Configuration management for Pressroom.

This file is responsible for:
1. Loading all environment variables
2. Providing default configuration values
3. Validating required configuration keys
4. Loading user-specific configuration overrides

DESIGN RATIONALE:
- Single import point for all configuration — nothing reads os.environ directly
- Validation on startup catches misconfiguration early
- User config merges over defaults, allowing personalization

SPEC REFERENCE: §5 "Configuration"
         §5.1 "Author-Specific Config" (config.yaml per user)
         §5.2 "Environment Variables" (stack.env loading)

DEPENDENCIES:
- This file is imported by: all other app modules
- No external dependencies — uses only Python standard library

TODO: Implement validate_config(), get_user_config(), validate_api_keys() stubs
"""

import os
from pathlib import Path


# ── Ideas Workbench ───────────────────────────────────────────────────────────
# The private GitHub repo that holds your ideas, drafts, and publish folders.
# This token needs repo scope (read + write) on ideas-workbench.

IDEAS_WORKBENCH_GIT_USER  = os.environ.get("IDEAS_WORKBENCH_GIT_USER", "")
# Use .get() so validate_config() in main.py can report all missing vars at once
# instead of crashing here on the first missing one.
IDEAS_WORKBENCH_GIT_TOKEN = os.environ.get("IDEAS_WORKBENCH_GIT_TOKEN", "")
IDEAS_WORKBENCH_REPO      = os.environ.get("IDEAS_WORKBENCH_REPO", "")    # e.g. zzpanic/ideas-workbench


# ── Pressroom Pubs ────────────────────────────────────────────────────────────
# The public GitHub repo that receives versioned, published snapshots.
# This token needs repo scope (read + write) on pressroom-pubs.

PRESSROOM_PUBS_GIT_USER   = os.environ.get("PRESSROOM_PUBS_GIT_USER", "")
PRESSROOM_PUBS_GIT_TOKEN  = os.environ.get("PRESSROOM_PUBS_GIT_TOKEN", "")
PRESSROOM_PUBS_REPO       = os.environ.get("PRESSROOM_PUBS_REPO", "")    # e.g. zzpanic/pressroom-pubs


# ── Pressroom App Repo ────────────────────────────────────────────────────────
# The public repo containing this app's source code.
# Used to fetch LaTeX templates and prompt templates at runtime.
# Read-only — the workbench token is fine here since pressroom is public.

PRESSROOM_REPO = os.environ.get("PRESSROOM_REPO", "zzpanic/pressroom")


# ── Git Branch ────────────────────────────────────────────────────────────────
# Which branch to read from and write to in all three repos.
# You almost certainly want "main".

GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")


# ── Author Details ────────────────────────────────────────────────────────────
# Used as fallback defaults when author.yaml doesn't exist in the workbench repo.
# author.yaml (if present) takes priority over these values.

AUTHOR_NAME   = os.environ.get("AUTHOR_NAME", "")
AUTHOR_EMAIL  = os.environ.get("AUTHOR_EMAIL", "")
AUTHOR_GITHUB = os.environ.get("AUTHOR_GITHUB", "")


# ── App Authentication ────────────────────────────────────────────────────────
# Username and password for the Pressroom web UI.
# Change these from the defaults before exposing the app to any network.

APP_USER     = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "pressroom")


# ── JWT Authentication ────────────────────────────────────────────────────────
# Secret key used to sign JWT tokens. Must be a long random string.
# Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
# JWT_EXPIRY_MINUTES controls how long a login session lasts.

JWT_SECRET         = os.environ.get("JWT_SECRET", "change-me-in-production")
try:
    JWT_EXPIRY_MINUTES = int(os.environ.get("JWT_EXPIRY_MINUTES", "480"))
except ValueError:
    raise ValueError(
        "JWT_EXPIRY_MINUTES must be a whole number of minutes (e.g. 480). "
        f"Got: {os.environ.get('JWT_EXPIRY_MINUTES')!r}"
    )
if JWT_EXPIRY_MINUTES <= 0:
    raise ValueError(
        f"JWT_EXPIRY_MINUTES must be positive, got {JWT_EXPIRY_MINUTES}. "
        "Negative or zero values produce immediately-expired tokens."
    )


# ── PDF Engine ────────────────────────────────────────────────────────────────
# Which rendering engine to use for PDF generation.
# "pandoc" (default) uses Pandoc + XeLaTeX.
# "sile" uses the Sile typesetting system (future).

PDF_ENGINE = os.environ.get("PDF_ENGINE", "pandoc")


# ── GitHub API ────────────────────────────────────────────────────────────────
# Base URL for the GitHub REST API.  Unlikely to ever need changing.

GITHUB_API = "https://api.github.com"


# ── Temp Directory ────────────────────────────────────────────────────────────
# Where Pandoc working files are written during PDF generation.
# This is inside the Docker container — nothing here survives a restart.

TEMP_DIR = Path("/tmp/pressroom")
try:
    TEMP_DIR.mkdir(exist_ok=True)
except OSError as _e:
    raise OSError(
        f"Cannot create temp directory {TEMP_DIR}: {_e}. "
        "Check that /tmp is writable inside the container "
        "(not mounted read-only or noexec)."
    ) from _e


# ─────────────────────────────────────────────────────────────────────────────
# STARTUP SECURITY WARNINGS
# Warn loudly when insecure defaults are still in use so they are never
# accidentally shipped.  We warn rather than hard-fail so the dev container
# can still start without a fully-configured .env file.
# ─────────────────────────────────────────────────────────────────────────────

import logging as _logging
_startup_log = _logging.getLogger(__name__)

if APP_USER == "admin":
    _startup_log.warning(
        "SECURITY: APP_USER is set to the default value 'admin'. "
        "Set the APP_USER environment variable to a custom username before exposing this service."
    )
if APP_PASSWORD == "pressroom":
    _startup_log.warning(
        "SECURITY: APP_PASSWORD is set to the default value 'pressroom'. "
        "Set the APP_PASSWORD environment variable to a strong password before exposing this service."
    )
if JWT_SECRET == "change-me-in-production":
    _startup_log.warning(
        "SECURITY: JWT_SECRET is set to the insecure default. "
        "Generate a random secret with: python -c \"import secrets; print(secrets.token_hex(32))\" "
        "and set it as the JWT_SECRET environment variable."
    )


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION AND USER CONFIG FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def validate_config(required_keys: list) -> None:
    """
    Validate that all required environment variables are set to non-empty values.

    PARAMETERS:
    - required_keys: List of environment variable names to check (e.g. ["IDEAS_WORKBENCH_GIT_TOKEN"])

    RAISES:
    - ValueError: with the names of all missing/empty keys listed together,
                  so a single startup failure surfaces every problem at once.

    USAGE:
        validate_config(["IDEAS_WORKBENCH_GIT_TOKEN", "PRESSROOM_PUBS_GIT_TOKEN"])
    """
    missing = [key for key in required_keys if not os.environ.get(key)]
    if missing:
        raise ValueError(
            f"Required environment variable(s) are missing or empty: {', '.join(missing)}. "
            "Set them in your .env file or Docker environment before starting the server."
        )


def get_user_config(user_id: str) -> dict:
    """
    Return the merged configuration for a user.

    Starts with a set of application-level defaults derived from this module,
    then overlays any user-specific overrides found in
    /app/data/users/{user_id}/config.yaml (if the file exists).

    PARAMETERS:
    - user_id: The authenticated user's ID

    RETURNS:
    - dict: Merged configuration.  Keys currently returned:
        - default_template (str)   — LaTeX template name to use when none is specified
        - pdf_engine (str)         — "pandoc" or "sile"
        - github_branch (str)      — which branch to read/write in GitHub repos

    USAGE IN ROUTERS:
        user_config = get_user_config(user_id)
        template_name = user_config.get("default_template", "whitepaper")
    """
    # Application-level defaults sourced from environment / this module
    defaults = {
        "default_template": "whitepaper",
        "pdf_engine": PDF_ENGINE,
        "github_branch": GITHUB_BRANCH,
    }

    # Per-user override file — optional, silently skipped when absent
    user_config_path = Path(f"/app/data/users/{user_id}/config.yaml")
    if user_config_path.exists():
        try:
            import yaml
            with open(user_config_path, "r", encoding="utf-8") as fh:
                user_overrides = yaml.safe_load(fh) or {}
            # Only merge keys that are already in defaults to avoid accepting
            # arbitrary config keys from the file.
            for key in defaults:
                if key in user_overrides:
                    defaults[key] = user_overrides[key]
        except Exception as exc:
            _startup_log.warning(
                f"Could not load user config for {user_id} from {user_config_path}: {exc}. "
                "Using application defaults."
            )

    return defaults


def validate_api_keys() -> None:
    """
    Validate that the GitHub personal access tokens look like real tokens.

    GitHub PATs start with "ghp_" (classic) or "github_pat_" (fine-grained).
    A token that doesn't match either prefix was almost certainly misconfigured
    (e.g. copied with extra whitespace, or the wrong variable was set).

    RAISES:
    - ValueError: listing every token that fails the prefix check.

    USAGE:
        validate_api_keys()  # Called at startup in main.py
    """
    _VALID_PREFIXES = ("ghp_", "github_pat_")
    errors = []

    for var_name, token_value in [
        ("IDEAS_WORKBENCH_GIT_TOKEN", IDEAS_WORKBENCH_GIT_TOKEN),
        ("PRESSROOM_PUBS_GIT_TOKEN",  PRESSROOM_PUBS_GIT_TOKEN),
    ]:
        if not any(token_value.startswith(p) for p in _VALID_PREFIXES):
            errors.append(
                f"{var_name} does not look like a GitHub PAT "
                f"(expected prefix 'ghp_' or 'github_pat_', got {token_value[:8]!r}...)"
            )

    if errors:
        raise ValueError(
            "Invalid GitHub API key(s) detected at startup:\n" + "\n".join(errors)
        )