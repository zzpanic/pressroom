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

import logging

from fastapi import APIRouter, Depends

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO, PRESSROOM_REPO, AUTHOR_NAME, AUTHOR_EMAIL, AUTHOR_GITHUB
from services.bootstrap import bootstrap_if_needed

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/config")
async def get_config(_: str = Depends(check_auth)):
    """
    Return app configuration to the frontend.

    Also bootstraps zz-pressroom/ in the workbench repo on first run —
    creates author.yaml, defaults.yaml, and copies bundled templates
    if the folder doesn't exist yet.
    """
    # Bootstrap zz-pressroom/ if this is a first run
    try:
        bootstrapped = await bootstrap_if_needed()
        if bootstrapped:
            logger.info("zz-pressroom/ bootstrapped in %s", IDEAS_WORKBENCH_REPO)
    except Exception as exc:
        # Bootstrap failure is non-fatal — log it and continue
        logger.warning("zz-pressroom bootstrap failed (non-fatal): %s", exc)

    return {
        "author_name":    AUTHOR_NAME,
        "author_email":   AUTHOR_EMAIL,
        "author_github":  AUTHOR_GITHUB,
        "author_orcid":   "",

        # Repo names — shown in the header bar
        "github_repo":    IDEAS_WORKBENCH_REPO,
        "pressroom_repo": PRESSROOM_REPO,
    }
