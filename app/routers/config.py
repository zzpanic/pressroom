# routers/config.py
# ─────────────────────────────────────────────────────────────────────────────
# Provides the /api/config endpoint.
#
# The frontend calls this once on startup to get the author's details and repo
# names.  Per spec §7.3, author details are read from author.yaml in the
# ideas-workbench repo (at zz-pressroom/author.yaml), NOT from environment
# variables.  This keeps the author profile editable in Obsidian alongside
# the ideas, without needing to restart the Docker container.
#
# Expected author.yaml format (in ideas-workbench/zz-pressroom/author.yaml):
#
#   name: Patrick Nichols
#   email: patrick@example.com
#   github: zzpanic
#   orcid: 0000-0000-0000-0000   (optional)
# ─────────────────────────────────────────────────────────────────────────────

import yaml

from fastapi import APIRouter, Depends

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO, PRESSROOM_REPO, AUTHOR_NAME, AUTHOR_EMAIL, AUTHOR_GITHUB
from github import gh_get_text

router = APIRouter()

# Path to the author config file inside ideas-workbench
_AUTHOR_YAML_PATH = "zz-pressroom/author.yaml"


@router.get("/api/config")
async def get_config(_: str = Depends(check_auth)):
    """
    Return app configuration to the frontend.

    Fetches author details from ideas-workbench/zz-pressroom/author.yaml.
    If the file doesn't exist yet, returns empty strings for author fields
    so the UI still loads — the user can fill them in manually.
    """
    # Try to load author details from GitHub
    author = await _load_author_yaml()

    return {
        # Author details — author.yaml values take priority; env vars are the fallback
        "author_name":    author.get("name",   "") or AUTHOR_NAME,
        "author_email":   author.get("email",  "") or AUTHOR_EMAIL,
        "author_github":  author.get("github", "") or AUTHOR_GITHUB,
        "author_orcid":   author.get("orcid",  ""),

        # Repo names — shown in the header bar
        "github_repo":    IDEAS_WORKBENCH_REPO,
        "pressroom_repo": PRESSROOM_REPO,
    }


async def _load_author_yaml() -> dict:
    """
    Fetch and parse zz-pressroom/author.yaml from ideas-workbench.

    Returns an empty dict if the file doesn't exist or can't be parsed,
    so the rest of the app degrades gracefully instead of crashing.
    """
    raw = await gh_get_text(IDEAS_WORKBENCH_REPO, _AUTHOR_YAML_PATH)

    if raw is None:
        # File doesn't exist yet — that's OK, just return empty
        return {}

    try:
        parsed = yaml.safe_load(raw)
        # yaml.safe_load returns None for an empty file
        return parsed if isinstance(parsed, dict) else {}
    except yaml.YAMLError:
        # If the YAML is broken, return empty rather than crashing
        return {}
