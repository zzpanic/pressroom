"""
snapshot.py — Snapshot management for Pressroom papers.

This file is responsible for:
1. Building versioned snapshot paths for paper storage
2. Creating frozen copies of paper state in ideas-workbench via GitHub API
3. Mirroring those snapshots to pressroom-pubs

DESIGN RATIONALE:
- Snapshots are committed directly to GitHub — no local disk storage needed
- The workbench snapshot folder is the source of truth; pubs is the mirror
- Version strings encode both semver and gate level

SPEC REFERENCE: §3.1 "Per-User Ideas Workbench" — versioned snapshot folder structure
         §3.2 "Per-User Pressroom Pubs" — mirror structure
         §6   "Versioning" — version string construction
         §7.5 "Publish Workflow" — snapshot creation and mirroring

SNAPSHOT PATH STRUCTURE (inside either repo):
    {slug}/{version}/
    e.g.  my-paper/v0.1-alpha/

Files written per snapshot:
    {slug}/{version}/{slug}.md   — full markdown (frontmatter + body)
    {slug}/{version}/{slug}.pdf  — frozen copy of the review PDF
"""

import re
from dataclasses import dataclass
from typing import Optional

from exceptions import SnapshotCreationError, MirrorError


@dataclass(frozen=True)
class SnapshotPath:
    """
    Identifies a versioned snapshot inside a GitHub repo.

    ATTRIBUTES:
    - user_id: The authenticated user's ID (carried for context; not part of the repo path
               because the workbench repo is already per-user)
    - slug:    URL-friendly paper identifier (e.g., "my-great-idea")
    - version: Version string with gate (e.g., "v0.1-alpha", "v1.0")

    base_path is the repo-relative folder prefix used in both the workbench and
    pressroom-pubs repos:  {slug}/{version}
    """
    user_id: str
    slug: str
    version: str

    @property
    def base_path(self) -> str:
        """Repo-relative path prefix for this snapshot: {slug}/{version}"""
        return f"{self.slug}/{self.version}"


def build_snapshot_path(user_id: str, slug: str, gate: str, version: Optional[str] = None) -> SnapshotPath:
    """
    Build a SnapshotPath from user_id, slug, and gate/version info.
    
    PARAMETERS:
    - user_id: The authenticated user's ID
    - slug: URL-friendly paper identifier (lowercase, hyphens, numbers)
    - gate: Current gate level (alpha, exploratory, draft, review, published)
    - version: Optional explicit version string (auto-generated if not provided)
    
    RETURNS:
    - SnapshotPath: Parsed path object with base_path property
    
    RAISES:
    - ValueError: If slug or version format is invalid
    
    VERSION AUTO-GENERATION:
    If version is not provided, it's constructed from gate:
    - alpha -> v0.1-alpha
    - exploratory -> v0.1-exploratory
    - draft -> v0.2-draft
    - review -> v0.3-review
    - published -> v1.0-published
    
    EXAMPLE:
        >>> path = build_snapshot_path("user1", "my-paper", "alpha")
        >>> path.base_path
        '/pubs/user1/my-paper/v0.1-alpha'
    """
    # Auto-generate version from gate if not provided
    if version is None:
        GATE_VERSIONS = {
            "alpha": "v0.1-alpha",
            "exploratory": "v0.1-exploratory", 
            "draft": "v0.2-draft",
            "review": "v0.3-review",
            "published": "v1.0"
        }
        version = GATE_VERSIONS.get(gate, f"v0.1-{gate}")

    # Validate inputs using the validators defined in this module.
    # Done here rather than inside SnapshotPath so the error is caught at
    # construction time, not later when the path is used.
    if not validate_slug_format(slug):
        raise ValueError(f"Invalid slug '{slug}'. Must be lowercase letters, digits, hyphens, or underscores.")
    if not validate_version_format(version):
        raise ValueError(f"Invalid version string '{version}'. Expected format: v0.1-exploratory or v1.0.")

    return SnapshotPath(user_id=user_id, slug=slug, version=version)


def parse_snapshot_path(path: str, user_id: str = "") -> SnapshotPath:
    """
    Parse a repo-relative snapshot path string into its components.

    PARAMETERS:
    - path:    Repo-relative path (e.g., "my-paper/v0.1-alpha" or "my-paper/v0.1-alpha/")
    - user_id: The authenticated user's ID (not encoded in the path itself)

    RETURNS:
    - SnapshotPath: Parsed path object

    RAISES:
    - ValueError: If path doesn't match expected pattern

    EXAMPLE:
        >>> p = parse_snapshot_path("my-paper/v0.1-alpha", user_id="john")
        >>> p.slug
        'my-paper'
        >>> p.version
        'v0.1-alpha'
    """
    pattern = r"^([^/]+)/([^/]+)/?$"
    match = re.match(pattern, path.strip())
    if not match:
        raise ValueError(f"Invalid snapshot path format: {path!r}. Expected '{{slug}}/{{version}}'")

    slug, version = match.groups()
    return SnapshotPath(user_id=user_id, slug=slug, version=version)


def validate_version_format(version: str) -> bool:
    """
    Validate that a version string follows semver-with-gate format.
    
    PARAMETERS:
    - version: Version string to validate (e.g., "v0.1-alpha", "v1.0-published")
    
    RETURNS:
    - bool: True if valid, False otherwise
    
    FORMAT:
    Valid versions match pattern: v{digit}.{digit}-{gate}
    where gate is one of: alpha, exploratory, draft, review, published
    
    EXAMPLE:
        >>> validate_version_format("v0.1-alpha")
        True
        >>> validate_version_format("invalid")
        False
    """
    if not isinstance(version, str):
        return False
    # Gate suffix is optional only for v1.0 (published has no gate suffix per spec §6).
    # All other versions must end in one of the five known gate names.
    pattern = r"^v\d+\.\d+(-(?:alpha|exploratory|draft|review|published))?$"
    return bool(re.match(pattern, version))


def validate_slug_format(slug: str) -> bool:
    """
    Validate that a slug contains only allowed characters.
    
    PARAMETERS:
    - slug: Slug string to validate (e.g., "my-great-idea")
    
    RETURNS:
    - bool: True if valid, False otherwise
    
    ALLOWED: lowercase letters, numbers, hyphens, underscores
    INVALID: uppercase letters, spaces, special characters
    
    EXAMPLE:
        >>> validate_slug_format("my-paper-1")
        True
        >>> validate_slug_format("My Paper!")
        False
    """
    if not isinstance(slug, str):
        return False
    # Must start with a letter or digit (not a hyphen or underscore) so slugs
    # are meaningful path components and consistent with preview.py's _SLUG_RE.
    pattern = r"^[a-z0-9][a-z0-9_-]*$"
    return bool(re.match(pattern, slug))


async def create_snapshot(slug: str, body: str, frontmatter: dict, gate: str, user_id: str) -> SnapshotPath:
    """
    Create a versioned snapshot of the paper in ideas-workbench via GitHub API.

    Per spec §7.5 step 6 and §3.1, the snapshot folder is:
        {slug}/{version}/
    and contains two files:
        {slug}/{version}/{slug}.md   — full markdown (frontmatter + body reconstructed)
        {slug}/{version}/{slug}.pdf  — frozen copy of the review PDF from publish/

    PARAMETERS:
    - slug:        Paper identifier (e.g., "my-great-idea")
    - body:        Markdown body text (everything after the frontmatter block)
    - frontmatter: Parsed YAML metadata dict
    - gate:        Current gate level (alpha, exploratory, draft, review, published)
    - user_id:     Authenticated user ID

    RETURNS:
    - SnapshotPath: Identifies the created snapshot (slug + version + user_id)

    RAISES:
    - RuntimeError: if the review PDF doesn't exist in workbench, or any GitHub write fails

    SPEC REFERENCE: §7.5 "Publish Workflow" step 6
    """
    import logging
    from github import gh_get, gh_get_bytes, gh_put, gh_put_bytes, WORKBENCH_HEADERS
    from config import IDEAS_WORKBENCH_REPO
    from services.frontmatter import write_frontmatter

    GATE_VERSIONS = {
        "alpha":       "v0.1-alpha",
        "exploratory": "v0.1-exploratory",
        "draft":       "v0.2-draft",
        "review":      "v0.3-review",
        "published":   "v1.0",
    }
    version = GATE_VERSIONS.get(gate, f"v0.1-{gate}")
    snapshot_path = SnapshotPath(user_id=user_id, slug=slug, version=version)
    prefix = snapshot_path.base_path  # e.g. "my-paper/v0.1-alpha"

    # ── 1. Write {slug}.md to workbench snapshot folder ──────────────────────
    # Reconstruct the full markdown document (frontmatter fence + body) so the
    # snapshot is a self-contained, Obsidian-readable file.
    md_content = write_frontmatter(body, frontmatter)
    md_repo_path = f"{prefix}/{slug}.md"

    existing_md = await gh_get(IDEAS_WORKBENCH_REPO, md_repo_path, headers=WORKBENCH_HEADERS)
    md_sha = existing_md["sha"] if existing_md else None

    try:
        await gh_put(
            IDEAS_WORKBENCH_REPO,
            md_repo_path,
            md_content,
            message=f"pressroom: snapshot {slug} {version}",
            sha=md_sha,
            headers=WORKBENCH_HEADERS,
        )
        logging.info(f"Snapshot MD written to {IDEAS_WORKBENCH_REPO}/{md_repo_path}")
    except SnapshotCreationError:
        raise
    except Exception as exc:
        raise SnapshotCreationError(f"Failed to write snapshot MD to workbench: {exc}", slug=slug, version=version) from exc

    # ── 2. Copy review PDF into workbench snapshot folder ────────────────────
    # The PDF was written by the "Preview PDF" step to {slug}/publish/{slug}.pdf.
    # The publish router already checks it exists, but we guard here too.
    pdf_publish_path = f"{slug}/publish/{slug}.pdf"
    pdf_bytes = await gh_get_bytes(IDEAS_WORKBENCH_REPO, pdf_publish_path, headers=WORKBENCH_HEADERS)

    if pdf_bytes is None:
        raise SnapshotCreationError(
            f"Review PDF not found at {pdf_publish_path} in {IDEAS_WORKBENCH_REPO}. "
            "Run 'Preview PDF' before publishing.",
            slug=slug, version=version,
        )

    pdf_repo_path = f"{prefix}/{slug}.pdf"
    existing_pdf = await gh_get(IDEAS_WORKBENCH_REPO, pdf_repo_path, headers=WORKBENCH_HEADERS)
    pdf_sha = existing_pdf["sha"] if existing_pdf else None

    try:
        await gh_put_bytes(
            IDEAS_WORKBENCH_REPO,
            pdf_repo_path,
            pdf_bytes,
            message=f"pressroom: snapshot {slug} {version} — PDF",
            sha=pdf_sha,
            headers=WORKBENCH_HEADERS,
        )
        logging.info(f"Snapshot PDF written to {IDEAS_WORKBENCH_REPO}/{pdf_repo_path}")
    except SnapshotCreationError:
        raise
    except Exception as exc:
        raise SnapshotCreationError(f"Failed to write snapshot PDF to workbench: {exc}", slug=slug, version=version) from exc

    return snapshot_path


async def mirror_to_pubs(snapshot_path: SnapshotPath, github_token: str) -> None:
    """
    Mirror a workbench snapshot to pressroom-pubs via GitHub API.

    Per spec §7.5 step 7 and §3.2, both {slug}.md and {slug}.pdf are copied
    from the workbench snapshot folder to the same folder path in pressroom-pubs:

        SOURCE  (ideas-workbench):  {slug}/{version}/{slug}.md  +  .pdf
        DEST    (pressroom-pubs):   {slug}/{version}/{slug}.md  +  .pdf

    PARAMETERS:
    - snapshot_path: Identifies the snapshot (slug + version) — created by create_snapshot()
    - github_token:  Unused (kept for API compatibility); PRESSROOM_PUBS_GIT_TOKEN is used

    RAISES:
    - RuntimeError: if any workbench read or pressroom-pubs write fails

    SPEC REFERENCE: §7.5 "Publish Workflow" step 7 — Mirror to pressroom-pubs
    """
    import logging
    from github import (
        gh_get, gh_get_text, gh_get_bytes,
        gh_put, gh_put_bytes,
        WORKBENCH_HEADERS, PUBS_HEADERS,
    )
    from config import IDEAS_WORKBENCH_REPO, PRESSROOM_PUBS_REPO

    prefix = snapshot_path.base_path  # e.g. "my-paper/v0.1-alpha"
    slug    = snapshot_path.slug
    version = snapshot_path.version

    # ── 1. Mirror {slug}.md ───────────────────────────────────────────────────
    md_src_path = f"{prefix}/{slug}.md"
    md_content = await gh_get_text(IDEAS_WORKBENCH_REPO, md_src_path, headers=WORKBENCH_HEADERS)
    if md_content is None:
        raise MirrorError(
            f"Snapshot MD not found in workbench at {md_src_path}. "
            "create_snapshot() must succeed before mirror_to_pubs() is called.",
            pubs_repo=PRESSROOM_PUBS_REPO,
        )

    md_dest_path = f"{prefix}/{slug}.md"
    existing_md  = await gh_get(PRESSROOM_PUBS_REPO, md_dest_path, headers=PUBS_HEADERS)
    md_sha       = existing_md["sha"] if existing_md else None

    try:
        await gh_put(
            PRESSROOM_PUBS_REPO,
            md_dest_path,
            md_content,
            message=f"publish {slug} {version}",
            sha=md_sha,
            headers=PUBS_HEADERS,
        )
        logging.info(f"Mirrored {md_dest_path} to {PRESSROOM_PUBS_REPO}")
    except MirrorError:
        raise
    except Exception as exc:
        logging.error(f"Failed to mirror MD to pressroom-pubs: {exc}")
        raise MirrorError(f"Failed to mirror {md_dest_path}: {exc}", pubs_repo=PRESSROOM_PUBS_REPO) from exc

    # ── 2. Mirror {slug}.pdf ──────────────────────────────────────────────────
    pdf_src_path = f"{prefix}/{slug}.pdf"
    pdf_bytes    = await gh_get_bytes(IDEAS_WORKBENCH_REPO, pdf_src_path, headers=WORKBENCH_HEADERS)
    if pdf_bytes is None:
        raise MirrorError(
            f"Snapshot PDF not found in workbench at {pdf_src_path}.",
            pubs_repo=PRESSROOM_PUBS_REPO,
        )

    pdf_dest_path = f"{prefix}/{slug}.pdf"
    existing_pdf  = await gh_get(PRESSROOM_PUBS_REPO, pdf_dest_path, headers=PUBS_HEADERS)
    pdf_sha       = existing_pdf["sha"] if existing_pdf else None

    try:
        await gh_put_bytes(
            PRESSROOM_PUBS_REPO,
            pdf_dest_path,
            pdf_bytes,
            message=f"publish {slug} {version} — PDF",
            sha=pdf_sha,
            headers=PUBS_HEADERS,
        )
        logging.info(f"Mirrored {pdf_dest_path} to {PRESSROOM_PUBS_REPO}")
    except MirrorError:
        raise
    except Exception as exc:
        logging.error(f"Failed to mirror PDF to pressroom-pubs: {exc}")
        raise MirrorError(f"Failed to mirror PDF {pdf_dest_path}: {exc}", pubs_repo=PRESSROOM_PUBS_REPO) from exc