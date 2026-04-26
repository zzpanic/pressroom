"""
routers/prompts.py — Prompts library endpoints.

GET /api/prompts        — list all prompts with name and preview text
GET /api/prompts/{name} — return the full content of a single prompt

Prompts are Markdown files stored in zz-pressroom/prompts/ in the user's
ideas-workbench repo.  They appear in the Prompts tab as cards with a short
preview and a copy-to-clipboard button.

The user owns and edits these files in Obsidian — changes appear in the app
immediately without restarting the container.

SPEC REFERENCE: §5.1 "Author-Specific Config" — zz-pressroom/prompts/ structure
"""

import re

from fastapi import APIRouter, Depends, HTTPException

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO
from github import gh_get_text, gh_list

router = APIRouter()

# Prompts live in this folder inside the workbench repo
_PROMPTS_DIR = "zz-pressroom/prompts"

# Prompt names must be safe path components (no dots, slashes, traversal)
_PROMPT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# How many characters of content to return as the card preview
_PREVIEW_CHARS = 300


@router.get("/api/prompts")
async def list_prompts(_: str = Depends(check_auth)):
    """
    Return all prompts from zz-pressroom/prompts/ in the workbench repo.

    Each item has:
      name    — filename without the .md extension (e.g. "new-paper")
      preview — first ~300 characters of the prompt content

    Returns an empty list if the prompts folder doesn't exist yet.
    (Bootstrap will have created it with a default prompt on first login,
    but we return an empty list gracefully in case that hasn't run.)
    """
    items = await gh_list(IDEAS_WORKBENCH_REPO, _PROMPTS_DIR)

    result = []
    for item in items:
        # Only process markdown files
        if not item["name"].endswith(".md"):
            continue

        name = item["name"][:-3]  # strip .md extension

        # Fetch a bit of the content for the card preview.
        # We fetch the full file here — prompts are small (a few hundred words)
        # so the overhead is minimal and it avoids a second request on copy.
        content = await gh_get_text(IDEAS_WORKBENCH_REPO, f"{_PROMPTS_DIR}/{item['name']}")
        if content is None:
            continue

        result.append({
            "name":    name,
            "preview": content[:_PREVIEW_CHARS],
            "content": content,
        })

    return result


@router.get("/api/prompts/{name}")
async def get_prompt(name: str, _: str = Depends(check_auth)):
    """
    Return the full content of a single prompt file.

    Raises HTTP 400 if the name contains unsafe characters.
    Raises HTTP 404 if the prompt file doesn't exist.
    """
    if not _PROMPT_NAME_RE.match(name):
        raise HTTPException(400, f"Invalid prompt name '{name}'.")

    content = await gh_get_text(IDEAS_WORKBENCH_REPO, f"{_PROMPTS_DIR}/{name}.md")
    if content is None:
        raise HTTPException(404, f"Prompt '{name}' not found in {_PROMPTS_DIR}/")

    return {"name": name, "content": content}
