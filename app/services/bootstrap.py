# services/bootstrap.py
# ─────────────────────────────────────────────────────────────────────────────
# Auto-populates zz-pressroom/ in the user's ideas-workbench repo on first run.
#
# zz-pressroom/ is the per-user Pressroom config home.  It lives alongside the
# papers in the workbench repo so it's version-controlled and Obsidian-editable.
#
# Files created (only if they don't already exist — never overwrites):
#
#   zz-pressroom/author.yaml              — author metadata seeded from env vars
#   zz-pressroom/defaults.yaml            — default frontmatter values per paper
#   zz-pressroom/templates/whitepaper.latex — bundled template copied from image
#
# Called once from /api/config on first login.  Subsequent calls skip it because
# author.yaml already exists.  The check is a single GitHub API call so the cost
# is negligible.
# ─────────────────────────────────────────────────────────────────────────────

from pathlib import Path

import yaml

from config import (
    IDEAS_WORKBENCH_REPO,
    AUTHOR_NAME,
    AUTHOR_EMAIL,
    AUTHOR_GITHUB,
)
from github import gh_get_text, gh_put

# The bundled LaTeX templates live here inside the Docker image
_LOCAL_TEMPLATE_DIR = Path("/app/pandoc")

# Root of the per-user config folder in the workbench repo
_ZZ = "zz-pressroom"


async def bootstrap_if_needed() -> bool:
    """
    Check whether zz-pressroom/ is initialised and create it if not.

    Returns True if bootstrapping ran, False if it was already set up.

    This is intentionally idempotent — each individual file is only created
    when it does not already exist, so it is safe to call on every startup.
    """
    # Use author.yaml as the sentinel — if it exists, assume the folder is set up
    existing = await gh_get_text(IDEAS_WORKBENCH_REPO, f"{_ZZ}/author.yaml")
    if existing is not None:
        return False  # already bootstrapped

    # Create all default files in parallel would be cleaner but sequential is
    # safer — GitHub rejects concurrent writes to the same repo branch reliably
    await _create_author_yaml()
    await _create_defaults_yaml()
    await _create_bundled_templates()

    return True


async def _create_author_yaml() -> None:
    """
    Write author.yaml seeded from AUTHOR_NAME / AUTHOR_EMAIL / AUTHOR_GITHUB
    environment variables.  The user can edit it in Obsidian afterward.
    """
    content = yaml.dump(
        {
            "name":   AUTHOR_NAME or "Your Name",
            "email":  AUTHOR_EMAIL or "you@example.com",
            "github": AUTHOR_GITHUB or "yourusername",
            "orcid":  "",
        },
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    await gh_put(
        IDEAS_WORKBENCH_REPO,
        f"{_ZZ}/author.yaml",
        content,
        message="pressroom: initialise zz-pressroom/author.yaml",
    )


async def _create_defaults_yaml() -> None:
    """
    Write defaults.yaml with the standard per-paper frontmatter defaults.
    These are used to pre-fill new papers and can be overridden per-paper.
    """
    content = yaml.dump(
        {
            "gate":     "alpha",
            "license":  "CC BY 4.0",
            "template": "whitepaper",
            "ai_assisted": {
                "ideation": False,
                "writing":  False,
                "research": False,
            },
        },
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    await gh_put(
        IDEAS_WORKBENCH_REPO,
        f"{_ZZ}/defaults.yaml",
        content,
        message="pressroom: initialise zz-pressroom/defaults.yaml",
    )


async def _create_bundled_templates() -> None:
    """
    Copy bundled LaTeX templates from /app/pandoc/ into zz-pressroom/templates/
    so the user has a starting point they can customise in their workbench repo.
    Only copies templates that exist in the image.
    """
    if not _LOCAL_TEMPLATE_DIR.exists():
        return  # running outside Docker (dev mode) — skip silently

    for latex_file in sorted(_LOCAL_TEMPLATE_DIR.glob("*.latex")):
        repo_path = f"{_ZZ}/templates/{latex_file.name}"

        # Don't overwrite a template the user has already customised
        existing = await gh_get_text(IDEAS_WORKBENCH_REPO, repo_path)
        if existing is not None:
            continue

        content = latex_file.read_text(encoding="utf-8")
        await gh_put(
            IDEAS_WORKBENCH_REPO,
            repo_path,
            content,
            message=f"pressroom: initialise zz-pressroom/templates/{latex_file.name}",
        )
