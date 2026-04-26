"""
routers/config.py — Author configuration endpoint.

GET /api/config — return author details and repo names to the frontend.

Per spec §7.3, author details come from zz-pressroom/author.yaml in the
ideas-workbench repo — NOT from environment variables.  This lets the author
edit their profile in Obsidian without restarting the Docker container.

Expected format (at ideas-workbench/zz-pressroom/author.yaml):

    name: Patrick Nichols
    email: patrick@example.com
    github: zzpanic
    orcid: 0000-0000-0000-0000   (optional)

On the first call this endpoint also triggers bootstrap_if_needed(), which
creates the zz-pressroom/ folder with default files if it does not exist yet.

SPEC REFERENCE: §7.3 "Author Configuration"
"""

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
