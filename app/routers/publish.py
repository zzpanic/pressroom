# routers/publish.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles the final publish step (spec §7.4, steps 5–7).
#
# When the author has reviewed the PDF and is satisfied:
#   5. Approve  — the author confirms version, gate, and metadata in the UI
#   6. Snapshot — Pressroom creates {slug}/{version}/ in ideas-workbench
#   7. Mirror   — same snapshot is pushed to pressroom-pubs
#
# POST /api/papers/{slug}/publish
#   Saves the current frontmatter, then creates the versioned snapshot and
#   mirrors it to pressroom-pubs via direct GitHub API calls.
#
# Important: the review PDF ({slug}/publish/{slug}.pdf) must already exist
# in ideas-workbench.  The user must click "Preview PDF" before publishing.
# ─────────────────────────────────────────────────────────────────────────────

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth import check_auth
from models import PublishRequest

_VALID_GATES    = {"alpha", "exploratory", "draft", "review", "published"}
_VERSION_RE     = re.compile(r"^v\d+\.\d+(-[a-z]+)?$")  # e.g. v0.1-exploratory or v1.0
from config import IDEAS_WORKBENCH_REPO, PRESSROOM_PUBS_GIT_TOKEN
from github import gh_get, gh_get_text
from services.frontmatter import parse_frontmatter
from services.snapshot import create_snapshot, mirror_to_pubs

router = APIRouter()

# Rate limiter: keyed by client IP address so each caller gets their own bucket.
# The limit is intentionally low — publish is an expensive operation (PDF generation
# + two GitHub API writes) and should never be called in a tight loop.
_limiter = Limiter(key_func=get_remote_address)


@router.post("/api/papers/{slug}/publish")
@_limiter.limit("5/minute")
async def publish_paper(slug: str, request: Request, body: PublishRequest, user_id: str = Depends(check_auth)):
    """
    Create a versioned snapshot in ideas-workbench and mirror it to pressroom-pubs.

    The request body is validated by PublishRequest (Pydantic):
      { "version": "v0.1-exploratory", "gate": "exploratory" }

    Before creating the snapshot, this endpoint checks that:
      - The review PDF exists in GitHub (i.e. "Preview PDF" was run first)

    Returns {"ok": true, "message": "..."} on success.
    Raises HTTP 409 if the review PDF doesn't exist in GitHub yet.
    Raises HTTP 500 if the snapshot or mirror operation fails.
    """
    version = body.version

    if not _VERSION_RE.match(version):
        raise HTTPException(400, f"Invalid version format '{version}'. Expected e.g. v0.1-exploratory or v1.0.")

    # Check that the review PDF exists before attempting to snapshot.
    # If the user hasn't run "Preview PDF" yet, the PDF won't be in GitHub
    # and the snapshot would fail part-way through.
    pdf_path = f"{slug}/publish/{slug}.pdf"
    pdf_exists = await gh_get(IDEAS_WORKBENCH_REPO, pdf_path) is not None

    if not pdf_exists:
        raise HTTPException(
            409,
            f"Review PDF not found at {pdf_path}.\n"
            "Click 'Preview PDF' first to generate and save the review copy."
        )

    # Fetch the paper markdown so we can pass body + frontmatter to create_snapshot.
    # The snapshot service needs the actual paper content, not just the slug.
    md_path = f"{slug}/publish/{slug}.md"
    md_text = await gh_get_text(IDEAS_WORKBENCH_REPO, md_path)
    if md_text is None:
        raise HTTPException(404, f"Paper markdown not found: {md_path}")

    frontmatter, body = parse_frontmatter(md_text)
    gate = frontmatter.get("gate", "")
    if gate not in _VALID_GATES:
        raise HTTPException(
            422,
            f"Paper gate '{gate}' is not valid. Must be one of: {', '.join(sorted(_VALID_GATES))}. "
            "Edit the frontmatter in Obsidian before publishing."
        )

    # Step 6 — create the versioned snapshot in ideas-workbench.
    # Use the SnapshotPath returned by create_snapshot (not a separately pre-computed
    # one) so that mirror_to_pubs uses exactly the same path that was written.
    try:
        snapshot_path = await create_snapshot(slug, body, frontmatter, gate, user_id)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Snapshot failed: {exc}")

    # Step 7 — mirror the snapshot to pressroom-pubs
    try:
        await mirror_to_pubs(snapshot_path, PRESSROOM_PUBS_GIT_TOKEN)
    except Exception as exc:
        # Snapshot succeeded but mirror failed — report clearly so the user
        # knows the ideas-workbench snapshot is fine but pubs needs a retry
        raise HTTPException(
            500,
            f"Snapshot created in ideas-workbench but mirror to pressroom-pubs failed: {exc}"
        )

    return {
        "ok":      True,
        "message": f"Published {slug} {version} to ideas-workbench and pressroom-pubs",
    }
