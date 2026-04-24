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

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO
from github import gh_get
from services.snapshot import create_snapshot, mirror_to_pubs

router = APIRouter()


@router.post("/api/papers/{slug}/publish")
async def publish_paper(slug: str, request: Request, _: str = Depends(check_auth)):
    """
    Create a versioned snapshot in ideas-workbench and mirror it to pressroom-pubs.

    The request body must include:
      { "version": "v0.1-exploratory" }

    Before creating the snapshot, this endpoint checks that:
      - A version string was provided
      - The review PDF exists in GitHub (i.e. "Preview PDF" was run first)

    If both checks pass, it calls create_snapshot() then mirror_to_pubs()
    from services/snapshot.py.

    Returns {"ok": true, "message": "..."} on success.
    Raises HTTP 400 if version is missing.
    Raises HTTP 409 if the review PDF doesn't exist in GitHub yet.
    Raises HTTP 500 if the snapshot or mirror operation fails.
    """
    body    = await request.json()
    version = body.get("version")

    if not version:
        raise HTTPException(400, "version is required")

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

    # Step 6 — create the versioned snapshot in ideas-workbench
    try:
        await create_snapshot(slug, version)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Snapshot failed: {exc}")

    # Step 7 — mirror the snapshot to pressroom-pubs
    try:
        await mirror_to_pubs(slug, version)
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
