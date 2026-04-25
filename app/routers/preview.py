# routers/preview.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles PDF generation (preview) and the write-back of the review copy.
#
# Per spec §7.4 publish workflow, steps 1–4:
#
#   1. Pull   — fetch {slug}/publish/{slug}.md from ideas-workbench
#   2. Generate PDF — render via Pandoc
#   3. Write review copy — push the PDF back to {slug}/publish/{slug}.pdf
#   4. Review — return the PDF to the browser for the author to inspect
#
# Clicking "Preview PDF" in the UI triggers all four of these steps in one go.
# The PDF is saved to GitHub so it's available in Obsidian and for the later
# snapshot step (which reads the PDF from GitHub, not from /tmp).
#
# GET /api/preview/{slug}
#   Generates the PDF, pushes it to GitHub, returns it to the browser.
#
# GET /api/preview/{slug}/download
#   Returns the last locally generated PDF as a file download (no regeneration).
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import re

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO, PRESSROOM_REPO, TEMP_DIR
from github import gh_get, gh_get_text, gh_put_bytes
from services.frontmatter import parse_frontmatter
from services.pdf import generate_pdf

# Slug must be lowercase letters, digits, hyphens, underscores only.
# This blocks path traversal (e.g. "../etc") before the slug touches the filesystem.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

router = APIRouter()


@router.get("/api/preview/{slug}")
async def preview_pdf(slug: str, _: str = Depends(check_auth)):
    """
    Generate a PDF for the given paper slug and return it to the browser.

    Steps:
      1. Fetch {slug}/publish/{slug}.md from GitHub
      2. Parse the frontmatter (metadata) and extract the body (paper text)
      3. Fetch the LaTeX template from the pressroom repo
      4. Run Pandoc to generate the PDF
      5. Push the PDF back to {slug}/publish/{slug}.pdf in ideas-workbench
      6. Return the PDF so the browser can display it inline

    Raises HTTP 404 if the paper .md file doesn't exist.
    Raises HTTP 404 if the LaTeX template isn't found in the pressroom repo.
    Raises HTTP 500 if Pandoc fails (includes the error output for debugging).
    """
    if not _SLUG_RE.match(slug):
        raise HTTPException(400, f"Invalid slug '{slug}'. Must be lowercase letters, digits, hyphens, or underscores.")

    md_path = f"{slug}/publish/{slug}.md"

    # Step 1 — fetch the paper markdown from GitHub
    md_text = await gh_get_text(IDEAS_WORKBENCH_REPO, md_path)
    if md_text is None:
        raise HTTPException(
            404,
            f"Paper not found: {md_path}\n"
            "Create the file in ideas-workbench before generating a preview."
        )

    # Step 2 — split the markdown into frontmatter metadata and body text
    frontmatter, body = parse_frontmatter(md_text)

    # Step 3 — fetch the LaTeX template from the pressroom repo
    template_name = frontmatter.get("template", "whitepaper")
    latex_raw = await gh_get_text(PRESSROOM_REPO, f"pandoc/{template_name}.latex")
    if latex_raw is None:
        raise HTTPException(
            404,
            f"LaTeX template not found: pandoc/{template_name}.latex in {PRESSROOM_REPO}"
        )

    # Step 4 — run Pandoc to generate the PDF
    # generate_pdf() writes temp files under /tmp/pressroom/{slug}/ and returns
    # the path to the generated PDF file
    try:
        output_path = await generate_pdf(slug, body, frontmatter, latex_raw)
    except RuntimeError as exc:
        # Pandoc failed — return its stderr so the user can see what went wrong
        raise HTTPException(500, f"PDF generation failed:\n{exc}")

    # Step 5 — push the PDF back to GitHub as the review copy
    # This makes it available in Obsidian and for the snapshot step later
    pdf_bytes    = output_path.read_bytes()
    pdf_gh_path  = f"{slug}/publish/{slug}.pdf"

    # Check if a review PDF already exists (need its SHA to overwrite it)
    existing_pdf = await gh_get(IDEAS_WORKBENCH_REPO, pdf_gh_path)
    existing_sha = existing_pdf.get("sha") if existing_pdf else None

    await gh_put_bytes(
        IDEAS_WORKBENCH_REPO,
        pdf_gh_path,
        pdf_bytes,
        message=f"pressroom: review PDF for {slug}",
        sha=existing_sha,
    )

    # Step 6 — return the PDF to the browser
    # FileResponse streams the file from the local /tmp path
    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{slug}-preview.pdf",
    )


@router.get("/api/preview/{slug}/download")
async def download_pdf(slug: str, _: str = Depends(check_auth)):
    """
    Return the last locally generated PDF as a file download.

    This does NOT regenerate the PDF — it just serves whatever was last produced
    by the preview endpoint.  Use 'Preview PDF' first to generate it.

    Raises HTTP 404 if no preview has been generated in the current session.
    (The /tmp folder is cleared when the Docker container restarts.)
    """
    if not _SLUG_RE.match(slug):
        raise HTTPException(400, f"Invalid slug '{slug}'.")

    output_path = TEMP_DIR / slug / f"{slug}.pdf"

    if not output_path.exists():
        raise HTTPException(
            404,
            "No preview found for this session. Click 'Preview PDF' first."
        )

    return FileResponse(
        output_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{slug}-preview.pdf"'},
    )
