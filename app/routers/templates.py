"""
routers/templates.py — Template and license listing endpoints.

GET /api/templates        — list available paper templates from the pressroom repo
GET /api/templates/{name} — fetch a single template's content and section headers
GET /api/licenses         — list available license files from the pressroom repo

Templates are Markdown files in the pressroom repo's templates/ folder.
The user selects one when starting a new paper in Obsidian.

SPEC REFERENCE: §8 "Templates"
"""

import re

from fastapi import APIRouter, Depends, HTTPException

from auth import check_auth
from config import PRESSROOM_REPO
from github import gh_get_text, gh_list

router = APIRouter()

_CONFIG_FOLDER = "zz-pressroom"

# Template names must be safe path components — no dots, slashes, or traversal sequences.
_TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Path to paper structure templates (prompt/ subfolder) within the pressroom repo.
# These are Markdown files with placeholder-filled section structures.
_PROMPT_TEMPLATE_DIR = "app/static/templates/prompt"


@router.get("/api/templates")
async def list_templates(_: str = Depends(check_auth)):
    items = await gh_list(PRESSROOM_REPO, _PROMPT_TEMPLATE_DIR)
    return [i["name"].replace(".md", "") for i in items if i["name"].endswith(".md")]


@router.get("/api/templates/{name}")
async def get_template(name: str, _: str = Depends(check_auth)):
    if not _TEMPLATE_NAME_RE.match(name):
        raise HTTPException(400, f"Invalid template name '{name}'.")
    content = await gh_get_text(PRESSROOM_REPO, f"{_PROMPT_TEMPLATE_DIR}/{name}.md")
    if content is None:
        raise HTTPException(404, f"Template '{name}' not found")
    headers = [
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("#") and not line.startswith("<!--")
    ]
    return {"name": name, "content": content, "headers": headers}


@router.get("/api/licenses")
async def list_licenses(_: str = Depends(check_auth)):
    items = await gh_list(PRESSROOM_REPO, "licenses")
    return [i["name"].replace(".md", "") for i in items if i["name"].endswith(".md")]
