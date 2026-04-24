# routers/papers.py
# ─────────────────────────────────────────────────────────────────────────────
# API endpoints for listing papers and reading/writing paper metadata.
#
# Per spec §7.4: the YAML frontmatter inside {slug}/publish/{slug}.md is the
# single source of truth.  There is no separate manifest.json.
#
# When the frontend loads a paper:
#   GET /api/papers/{slug} → fetches {slug}/publish/{slug}.md from GitHub,
#   parses the frontmatter, and returns the fields to populate the UI form.
#
# When the frontend saves changes:
#   POST /api/papers/{slug}/save → receives updated fields, fetches the
#   current .md file to extract the paper body, rebuilds the full document
#   with new frontmatter, and pushes it back to GitHub.
#
# The paper body (the actual text content) is never sent to or from the UI —
# only the frontmatter metadata is managed here.  Body edits happen in Obsidian.
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import check_auth
from config import IDEAS_WORKBENCH_REPO
from github import gh_get, gh_get_text, gh_put, gh_list
from services.frontmatter import parse_frontmatter, write_frontmatter, apply_derived_fields

router = APIRouter()

# The zz-pressroom folder holds app config (author.yaml, etc.) and should
# not appear in the papers list
_CONFIG_FOLDER = "zz-pressroom"


@router.get("/api/papers")
async def list_papers(_: str = Depends(check_auth)):
    """
    Return a list of all idea slugs (folder names) from ideas-workbench.

    Excludes hidden folders (starting with .) and the zz-pressroom config folder.
    Each item in the returned list is a string slug, e.g. "my-great-idea".
    """
    items = await gh_list(IDEAS_WORKBENCH_REPO, "")
    return [
        i["name"] for i in items
        if i["type"] == "dir"
        and not i["name"].startswith(".")
        and i["name"] != _CONFIG_FOLDER
    ]


@router.get("/api/papers/{slug}")
async def get_paper(slug: str, _: str = Depends(check_auth)):
    """
    Load a paper's frontmatter fields from {slug}/publish/{slug}.md.

    Returns:
      {
        "slug":         the paper slug,
        "frontmatter":  dict of all frontmatter fields (empty dict if none yet),
        "paper_exists": true if the .md file exists in GitHub
      }

    If the paper file doesn't exist, returns empty frontmatter so the UI still
    loads — the user can fill in metadata before adding the paper content.
    """
    md_path = f"{slug}/publish/{slug}.md"
    md_text = await gh_get_text(IDEAS_WORKBENCH_REPO, md_path)

    paper_exists = md_text is not None

    if md_text:
        # Parse the YAML frontmatter block out of the markdown file
        frontmatter, _ = parse_frontmatter(md_text)
    else:
        frontmatter = {}

    return {
        "slug":         slug,
        "frontmatter":  frontmatter,
        "paper_exists": paper_exists,
    }


@router.get("/api/papers/{slug}/versions")
async def get_versions(slug: str, _: str = Depends(check_auth)):
    """
    Return a sorted list of versioned snapshot folder names for a paper.

    These are the subfolders inside {slug}/ that look like version strings
    (e.g. "v0.1-exploratory", "v0.2-draft").  The "publish" subfolder is excluded.

    Returns a list of strings, sorted alphabetically.
    """
    items = await gh_list(IDEAS_WORKBENCH_REPO, slug)
    versions = [
        i["name"] for i in items
        if i["type"] == "dir" and i["name"] != "publish"
    ]
    return sorted(versions)


@router.post("/api/papers/{slug}/save")
async def save_paper(slug: str, request: Request, _: str = Depends(check_auth)):
    """
    Write updated frontmatter fields back to {slug}/publish/{slug}.md on GitHub.

    The request body should be a JSON object of frontmatter fields from the UI form.
    This endpoint:
      1. Fetches the current .md file from GitHub to get the paper body and SHA
      2. Merges the new fields into the frontmatter (also auto-fills derived fields)
      3. Rebuilds the full markdown document with the new frontmatter + original body
      4. Pushes the updated file back to GitHub

    The paper body content is preserved exactly — only the frontmatter changes.

    Returns {"ok": true} on success.
    """
    new_fields = await request.json()

    # Always set the slug field to match the folder name
    new_fields["slug"] = slug

    # Auto-fill derived fields (status, license_url, date)
    new_fields = apply_derived_fields(new_fields)

    md_path = f"{slug}/publish/{slug}.md"

    # Fetch the current file so we can preserve the body and get the SHA
    # (GitHub requires the SHA when updating an existing file)
    existing_file = await gh_get(IDEAS_WORKBENCH_REPO, md_path)

    if existing_file is not None:
        # File exists — decode its content to extract the body
        import base64
        current_text = base64.b64decode(existing_file["content"]).decode("utf-8")
        _, body = parse_frontmatter(current_text)
        sha = existing_file["sha"]
    else:
        # File doesn't exist yet — start with an empty body and no SHA
        body = ""
        sha  = None

    # Rebuild the full .md document: new frontmatter + original body
    updated_text = write_frontmatter(body, new_fields)

    await gh_put(
        IDEAS_WORKBENCH_REPO,
        md_path,
        updated_text,
        message=f"pressroom: update metadata for {slug}",
        sha=sha,
    )

    return {"ok": True}
