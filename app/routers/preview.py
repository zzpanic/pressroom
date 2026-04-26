# routers/preview.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles PDF generation (preview) and the write-back of the review copy.
#
# Per spec §7.4 publish workflow, steps 1–4:
#
#   1. Pull       — fetch {slug}/publish/{slug}.md from ideas-workbench
#   2. Pre-flight — validate frontmatter and body before invoking Pandoc
#   3. Generate   — render via Pandoc + XeLaTeX
#   4. Write back — push review PDF to {slug}/publish/{slug}.pdf on GitHub
#   5. Return     — stream the PDF to the browser
#
# GET /api/preview/{slug}
#   Runs steps 1-5.  Returns the PDF with any pre-flight warnings in headers.
#
# GET /api/preview/{slug}/download
#   Returns the last locally generated PDF as a file download (no regeneration).
# ─────────────────────────────────────────────────────────────────────────────

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO, PRESSROOM_REPO, TEMP_DIR
from exceptions import PaperNotFoundError
from github import gh_get, gh_get_text, gh_put_bytes
from services.frontmatter import parse_frontmatter
from services.pdf import generate_pdf
from services.preflight import run_preflight


class PreviewRequest(BaseModel):
    """
    The form sends its current frontmatter values so the PDF reflects what the
    user has typed, not whatever is (or isn't) saved in the GitHub file yet.
    The server fetches only the paper body from GitHub.
    """
    frontmatter: dict

# Slug must be lowercase letters, digits, hyphens, underscores only.
# This blocks path traversal (e.g. "../etc") before the slug touches the filesystem.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# LaTeX templates are baked into the image at /app/pandoc/.
# This is the primary source — fast, no network dependency.
# GitHub is the fallback for templates not found locally (e.g. user-uploaded ones
# that haven't been built into the image yet).
_LOCAL_TEMPLATE_DIR = Path("/app/pandoc")

router = APIRouter()


@router.post("/api/preview/{slug}")
async def preview_pdf(slug: str, req: PreviewRequest, _: str = Depends(check_auth)):
    """
    Generate a PDF for the given paper slug and return it to the browser.

    The client POSTs the current form frontmatter so the PDF reflects what the
    user has typed — the file on GitHub may not have been saved yet, or may have
    no frontmatter at all for a new paper.  The server fetches only the body text
    from GitHub and combines it with the form's frontmatter.

    Steps:
      1. Validate the slug format (blocks path traversal)
      2. Fetch {slug}/publish/{slug}.md from GitHub — extract body only
      3. Run pre-flight checks using the form's frontmatter and the GitHub body
      4. Load the LaTeX template (local filesystem first, GitHub fallback)
      5. Run Pandoc + XeLaTeX to generate the PDF
      6. Push the PDF back to GitHub as the review copy
      7. Return the PDF to the browser

    HTTP responses:
      200  PDF returned.  X-Pressroom-Warnings header contains pre-flight warnings as JSON.
      400  Slug invalid, or pre-flight blocking error (empty body, placeholders at final gate).
      404  Paper .md file not found, or LaTeX template not found.
      500  Pandoc/XeLaTeX failed — stderr included in error detail.
    """
    # ── 1. Validate slug ──────────────────────────────────────────────────────
    if not _SLUG_RE.match(slug):
        raise HTTPException(
            400,
            f"Invalid slug '{slug}'. Use only lowercase letters, digits, hyphens, or underscores."
        )

    # ── 2. Fetch paper from GitHub — body only ───────────────────────────────
    # The form is the source of truth for frontmatter. We only need the body
    # text from the file. If the file has frontmatter we discard it; if not,
    # the whole file is the body.
    md_path = f"{slug}/publish/{slug}.md"
    md_text = await gh_get_text(IDEAS_WORKBENCH_REPO, md_path)
    if md_text is None:
        raise PaperNotFoundError(slug)

    _, body = parse_frontmatter(md_text)
    frontmatter = req.frontmatter

    # ── 4. Pre-flight checks ──────────────────────────────────────────────────
    preflight = run_preflight(frontmatter, body)

    # Blocking errors — stop here, don't invoke Pandoc
    if not preflight.ok:
        error_messages = " | ".join(e.message for e in preflight.errors)
        raise HTTPException(400, f"Pre-flight checks failed: {error_messages}")

    # ── 5. Load LaTeX template ────────────────────────────────────────────────
    template_name = frontmatter.get("template", "whitepaper")
    latex_raw = _load_template_local(template_name)

    if latex_raw is None:
        # Local template not found — try GitHub (user-uploaded or repo template)
        latex_raw = await gh_get_text(PRESSROOM_REPO, f"pandoc/{template_name}.latex")

    if latex_raw is None:
        raise HTTPException(
            404,
            f"LaTeX template '{template_name}' not found locally or in {PRESSROOM_REPO}/pandoc/."
        )

    # ── 6. Generate PDF ───────────────────────────────────────────────────────
    try:
        output_path = await generate_pdf(slug, body, frontmatter, latex_raw)
    except RuntimeError as exc:
        raise HTTPException(500, f"PDF generation failed: {exc}")

    # ── 7. Push review copy back to GitHub ───────────────────────────────────
    pdf_bytes   = output_path.read_bytes()
    pdf_gh_path = f"{slug}/publish/{slug}.pdf"

    existing_pdf = await gh_get(IDEAS_WORKBENCH_REPO, pdf_gh_path)
    existing_sha = existing_pdf.get("sha") if existing_pdf else None

    await gh_put_bytes(
        IDEAS_WORKBENCH_REPO,
        pdf_gh_path,
        pdf_bytes,
        message=f"pressroom: review PDF for {slug}",
        sha=existing_sha,
    )

    # ── 8. Return PDF with pre-flight warnings in headers ────────────────────
    # Warnings don't block generation but the UI surfaces them to the author.
    # We encode them as JSON in a response header — small, no extra round-trip.
    warning_messages = [w.message for w in preflight.warnings]
    if preflight.placeholder_count:
        # Placeholder count is already included in the warning message but we
        # also expose it as a standalone header for the UI to display prominently.
        pass

    headers = {
        "X-Pressroom-Placeholder-Count": str(preflight.placeholder_count),
        "X-Pressroom-Warnings": json.dumps(warning_messages),
    }

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{slug}-preview.pdf",
        headers=headers,
    )


@router.get("/api/preview/{slug}/download")
async def download_pdf(slug: str, _: str = Depends(check_auth)):
    """
    Return the last locally generated PDF as a file download.

    Does NOT regenerate — serves whatever was last produced by the preview
    endpoint.  Use 'Preview PDF' first.  The /tmp folder is cleared on
    container restart so this will 404 after a redeploy.
    """
    if not _SLUG_RE.match(slug):
        raise HTTPException(400, f"Invalid slug '{slug}'.")

    output_path = TEMP_DIR / slug / "output.pdf"

    if not output_path.exists():
        raise HTTPException(
            404,
            "No preview found for this session. Click 'Preview PDF' first to generate one."
        )

    return FileResponse(
        output_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}-preview.pdf"'},
    )


def _load_template_local(template_name: str) -> str | None:
    """
    Try to read a LaTeX template from the local /app/pandoc/ directory.

    Returns the file content as a string, or None if not found.
    Reading locally is always preferred over a GitHub API call — faster,
    works offline, and not subject to rate limits.
    """
    path = _LOCAL_TEMPLATE_DIR / f"{template_name}.latex"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None
