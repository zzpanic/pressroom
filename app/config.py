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
IDEAS_WORKBENCH_GIT_TOKEN = os.environ["IDEAS_WORKBENCH_GIT_TOKEN"]
IDEAS_WORKBENCH_REPO      = os.environ["IDEAS_WORKBENCH_REPO"]   # e.g. zzpanic/ideas-workbench


# ── Pressroom Pubs ────────────────────────────────────────────────────────────
# The public GitHub repo that receives versioned, published snapshots.
# This token needs repo scope (read + write) on pressroom-pubs.

PRESSROOM_PUBS_GIT_USER   = os.environ.get("PRESSROOM_PUBS_GIT_USER", "")
PRESSROOM_PUBS_GIT_TOKEN  = os.environ["PRESSROOM_PUBS_GIT_TOKEN"]
PRESSROOM_PUBS_REPO       = os.environ["PRESSROOM_PUBS_REPO"]    # e.g. zzpanic/pressroom-pubs


# ── Pressroom App Repo ────────────────────────────────────────────────────────
# The public repo containing this app's source code.
# Used to fetch LaTeX templates and prompt templates at runtime.
# Read-only — the workbench token is fine here since pressroom is public.

PRESSROOM_REPO = os.environ.get("PRESSROOM_REPO", "zzpanic/pressroom")


# ── Git Branch ────────────────────────────────────────────────────────────────
# Which branch to read from and write to in all three repos.
# You almost certainly want "main".

GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")


# ── App Authentication ────────────────────────────────────────────────────────
# Username and password for the Pressroom web UI.
# Change these from the defaults before exposing the app to any network.

APP_USER     = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "pressroom")


# ── GitHub API ────────────────────────────────────────────────────────────────
# Base URL for the GitHub REST API.  Unlikely to ever need changing.

GITHUB_API = "https://api.github.com"


# ── Temp Directory ────────────────────────────────────────────────────────────
# Where Pandoc working files are written during PDF generation.
# This is inside the Docker container — nothing here survives a restart.

TEMP_DIR = Path("/tmp/pressroom")
TEMP_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION AND USER CONFIG FUNCTIONS (STUBS — to be implemented)
# ─────────────────────────────────────────────────────────────────────────────

def validate_config(required_keys: list) -> None:
    """
    Validate that all required configuration keys are present.
    
    PARAMETERS:
    - required_keys: List of configuration key names to check
    
    RAISES:
    - ValueError if any required key is missing or empty
    
    TODO: Implement:
    1. Loop through required_keys
    2. For each key, check os.environ.get(key) returns non-empty value
    3. Raise ValueError with descriptive message for missing keys
    
    USAGE:
        validate_config(["IDEAS_WORKBENCH_GIT_TOKEN", "PRESSROOM_PUBS_GIT_TOKEN"])
        # Raises ValueError if either token is missing
    """
    pass


def get_user_config(user_id: str) -> dict:
    """
    Get user-specific configuration from config.yaml.
    
    PARAMETERS:
    - user_id: The authenticated user's ID
    
    RETURNS:
    - dict: Merged configuration (default + user-specific overrides)
    
    TODO: Implement:
    1. Load default config from this module
    2. Check for user-specific config.yaml at ~/.pressroom/{user_id}/config.yaml
    3. If exists, merge user config over default config
    4. Return merged dict
    
    USAGE IN ROUTERS:
        # In publish endpoint, after authentication
        user_config = get_user_config(user_id)
        template_name = user_config.get("default_template", "whitepaper")
    """
    pass


def validate_api_keys() -> None:
    """
    Validate that all API keys are present and valid format.
    
    TODO: Implement:
    1. Check IDEAS_WORKBENCH_GIT_TOKEN starts with "ghp_"
    2. Check PRESSROOM_PUBS_GIT_TOKEN starts with "ghp_"
    3. Raise ValueError with descriptive message if invalid
    
    USAGE:
        validate_api_keys()
        # Called at startup in main.py before starting server
    """
    pass