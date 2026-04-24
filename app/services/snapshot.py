# services/snapshot.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles the two-step publish workflow (spec §7.4, steps 6 and 7):
#
#   Step 6 — Snapshot
#     Creates a versioned, frozen copy of the paper inside ideas-workbench.
#     Source:      {slug}/publish/
#     Destination: {slug}/{version}/
#     Files copied: {slug}.md, {slug}.pdf, and everything in artifacts/ (if present)
#
#   Step 7 — Mirror
#     Copies the same snapshot into pressroom-pubs, making it publicly visible.
#     Destination: {slug}/{version}/ in pressroom-pubs
#
# Both steps use direct GitHub API calls — no GitHub Actions involved.
# The two repos use different auth tokens (see github.py).
# ─────────────────────────────────────────────────────────────────────────────

from github import (
    gh_get,
    gh_get_text,
    gh_get_bytes,
    gh_put,
    gh_put_bytes,
    gh_list,
    WORKBENCH_HEADERS,
    PUBS_HEADERS,
)
from config import IDEAS_WORKBENCH_REPO, PRESSROOM_PUBS_REPO


async def create_snapshot(slug: str, version: str) -> None:
    """
    Copy the current publish/ folder into a versioned snapshot folder in ideas-workbench.

    This freezes the paper at this point in time.  The snapshot folder is:
        {slug}/{version}/

    Files written:
      {slug}/{version}/{slug}.md   — the source markdown (with frontmatter)
      {slug}/{version}/{slug}.pdf  — the review PDF generated during preview
      {slug}/{version}/artifacts/* — any files in publish/artifacts/ (one level deep)

    Parameters:
      slug:    the idea folder name, e.g. "my-great-idea"
      version: the version string, e.g. "v0.1-exploratory"

    Raises:
      FileNotFoundError: if the .md or .pdf source files don't exist in GitHub.
    """
    repo = IDEAS_WORKBENCH_REPO

    # ── Copy the markdown file ────────────────────────────────────────────────
    md_src_path  = f"{slug}/publish/{slug}.md"
    md_dest_path = f"{slug}/{version}/{slug}.md"

    md_text = await gh_get_text(repo, md_src_path)
    if md_text is None:
        raise FileNotFoundError(
            f"{md_src_path} not found in {repo}. "
            "Make sure the paper exists before publishing."
        )

    await gh_put(
        repo,
        md_dest_path,
        md_text,
        message=f"pressroom: snapshot {slug} {version} — markdown",
    )

    # ── Copy the PDF file ─────────────────────────────────────────────────────
    pdf_src_path  = f"{slug}/publish/{slug}.pdf"
    pdf_dest_path = f"{slug}/{version}/{slug}.pdf"

    pdf_bytes = await gh_get_bytes(repo, pdf_src_path)
    if pdf_bytes is None:
        raise FileNotFoundError(
            f"{pdf_src_path} not found in {repo}. "
            "Run 'Preview PDF' before publishing to generate the review copy."
        )

    await gh_put_bytes(
        repo,
        pdf_dest_path,
        pdf_bytes,
        message=f"pressroom: snapshot {slug} {version} — PDF",
    )

    # ── Copy artifacts (if the folder exists) ─────────────────────────────────
    # We only copy files directly inside artifacts/ — one level deep.
    # Nested subfolders are not supported and will be silently skipped.
    artifacts_src = f"{slug}/publish/artifacts"
    artifact_items = await gh_list(repo, artifacts_src)

    for item in artifact_items:
        # Skip subfolders — only copy files
        if item["type"] != "file":
            continue

        filename = item["name"]
        src_path  = f"{artifacts_src}/{filename}"
        dest_path = f"{slug}/{version}/artifacts/{filename}"

        file_bytes = await gh_get_bytes(repo, src_path)
        if file_bytes is not None:
            await gh_put_bytes(
                repo,
                dest_path,
                file_bytes,
                message=f"pressroom: snapshot {slug} {version} — artifact {filename}",
            )


async def mirror_to_pubs(slug: str, version: str) -> None:
    """
    Copy the versioned snapshot from ideas-workbench into pressroom-pubs.

    pressroom-pubs is the public, append-only repo where published work lives.
    It mirrors the same folder structure as ideas-workbench snapshots.

    This function reads the snapshot from ideas-workbench (which was just
    created by create_snapshot) and writes each file to pressroom-pubs using
    the pubs repo's separate auth token.

    Parameters:
      slug:    the idea folder name, e.g. "my-great-idea"
      version: the version string, e.g. "v0.1-exploratory"
    """
    workbench_repo = IDEAS_WORKBENCH_REPO
    pubs_repo      = PRESSROOM_PUBS_REPO

    # ── Mirror the markdown file ──────────────────────────────────────────────
    md_path = f"{slug}/{version}/{slug}.md"
    md_text = await gh_get_text(workbench_repo, md_path)
    if md_text is not None:
        await gh_put(
            pubs_repo,
            md_path,
            md_text,
            message=f"pressroom: publish {slug} {version} — markdown",
            headers=PUBS_HEADERS,
        )

    # ── Mirror the PDF file ───────────────────────────────────────────────────
    pdf_path  = f"{slug}/{version}/{slug}.pdf"
    pdf_bytes = await gh_get_bytes(workbench_repo, pdf_path)
    if pdf_bytes is not None:
        await gh_put_bytes(
            pubs_repo,
            pdf_path,
            pdf_bytes,
            message=f"pressroom: publish {slug} {version} — PDF",
            headers=PUBS_HEADERS,
        )

    # ── Mirror artifacts ──────────────────────────────────────────────────────
    artifacts_path  = f"{slug}/{version}/artifacts"
    artifact_items  = await gh_list(workbench_repo, artifacts_path)

    for item in artifact_items:
        if item["type"] != "file":
            continue

        filename  = item["name"]
        file_path = f"{artifacts_path}/{filename}"

        file_bytes = await gh_get_bytes(workbench_repo, file_path)
        if file_bytes is not None:
            await gh_put_bytes(
                pubs_repo,
                file_path,
                file_bytes,
                message=f"pressroom: publish {slug} {version} — artifact {filename}",
                headers=PUBS_HEADERS,
            )
