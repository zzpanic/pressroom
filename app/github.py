"""
github.py — GitHub REST API client for Pressroom.

All GitHub API calls in the app go through this module — nothing else in the
codebase talks to the GitHub API directly.

Two repos need different auth tokens (ideas-workbench is private; pressroom-pubs
is public), so this module exposes two pre-built header dicts — WORKBENCH_HEADERS
and PUBS_HEADERS — and every helper accepts a `headers` parameter so callers can
choose which identity to use.  Most calls operate on ideas-workbench, so
WORKBENCH_HEADERS is the default.

FUNCTIONS:
    gh_get(repo, path)            — fetch a file's metadata + content (None if 404)
    gh_get_text(repo, path)       — decode file content as a UTF-8 string
    gh_get_bytes(repo, path)      — decode file content as raw bytes (used for PDFs)
    gh_list(repo, path)           — list a folder's contents
    gh_put(repo, path, ...)       — create or update a text file
    gh_put_bytes(repo, path, ...) — create or update a binary file

SPEC REFERENCE: §11 "GitHub Integration"
"""

import base64
from typing import Optional

import httpx

from config import (
    IDEAS_WORKBENCH_GIT_TOKEN,
    PRESSROOM_PUBS_GIT_TOKEN,
    GITHUB_BRANCH,
    GITHUB_API,
)
from exceptions import GitHubAPIError, GitHubRateLimitError


# ── Auth header sets ──────────────────────────────────────────────────────────

def _make_headers(token: str) -> dict:
    """Build the GitHub API auth headers for a given personal access token."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

# Import these in other modules to choose which repo to operate on.
# Example: await gh_put(PRESSROOM_PUBS_REPO, path, ..., headers=PUBS_HEADERS)
WORKBENCH_HEADERS = _make_headers(IDEAS_WORKBENCH_GIT_TOKEN)
PUBS_HEADERS      = _make_headers(PRESSROOM_PUBS_GIT_TOKEN)


# ── Read helpers ──────────────────────────────────────────────────────────────

def _raise_for_github_status(r: httpx.Response) -> None:
    """Raise a structured PressroomException for any non-2xx GitHub response."""
    if r.status_code == 404:
        return  # callers handle 404 by checking for None return value
    if r.status_code == 403:
        reset_at = r.headers.get("X-RateLimit-Reset")
        if r.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubRateLimitError(reset_at=reset_at)
        raise GitHubAPIError(
            f"GitHub API returned 403 Forbidden — check token permissions.",
            status_code=403,
            response_body=r.text[:500],
        )
    if not r.is_success:
        raise GitHubAPIError(
            f"GitHub API error {r.status_code} for {r.url}",
            status_code=502,  # surface as 502 Bad Gateway — upstream fault
            response_body=r.text[:500],
        )


async def gh_get(repo: str, path: str, headers: dict = None) -> Optional[dict]:
    """
    Fetch a single file's metadata + base64 content from GitHub.

    Returns None if the file doesn't exist (404).
    Returns the raw GitHub API response dict on success.

    Raises:
        GitHubRateLimitError: on 403 with exhausted rate limit.
        GitHubAPIError:       for any other non-2xx response.
        httpx.RequestError:   for network failures (timeout, DNS).
    """
    if headers is None:
        headers = WORKBENCH_HEADERS

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise GitHubAPIError(f"Network error reaching GitHub: {exc}", status_code=503)

    if r.status_code == 404:
        return None
    _raise_for_github_status(r)
    return r.json()


async def gh_get_text(repo: str, path: str, headers: dict = None) -> Optional[str]:
    """
    Fetch a file from GitHub and return its content as a UTF-8 string.

    Returns None if the file doesn't exist or is not a regular file
    (submodules and symlinks have no "content" field in the API response).

    Side effects: makes an HTTPS GET request to api.github.com.

    Raises:
        httpx.HTTPStatusError: for non-404 HTTP errors.
        httpx.RequestError:    for network failures.
        UnicodeDecodeError:    if the file content is not valid UTF-8.
    """
    data = await gh_get(repo, path, headers=headers)
    if data is None:
        return None
    # GitHub returns file content base64-encoded in the "content" field.
    # Non-file responses (submodules, symlinks) may not have this field.
    if "content" not in data:
        return None
    return base64.b64decode(data["content"]).decode("utf-8")


async def gh_get_bytes(repo: str, path: str, headers: dict = None) -> Optional[bytes]:
    """
    Fetch a file from GitHub and return its raw bytes.

    Used for binary files like PDFs.
    Returns None if the file doesn't exist or has no "content" field.

    Side effects: makes an HTTPS GET request to api.github.com.

    Raises:
        httpx.HTTPStatusError: for non-404 HTTP errors.
        httpx.RequestError:    for network failures.
    """
    data = await gh_get(repo, path, headers=headers)
    if data is None:
        return None
    if "content" not in data:
        return None
    return base64.b64decode(data["content"])


async def gh_list(repo: str, path: str, headers: dict = None) -> list:
    """
    List the contents of a folder in a GitHub repo.

    Returns a list of GitHub Contents API entry dicts (keys: name, path, type, sha, …).
    Returns an empty list if the folder doesn't exist OR if path points to a file
    rather than a folder — callers cannot distinguish these two cases.

    Side effects: makes an HTTPS GET request to api.github.com.

    Raises:
        httpx.HTTPStatusError: for non-404 HTTP errors.
        httpx.RequestError:    for network failures.
    """
    if headers is None:
        headers = WORKBENCH_HEADERS

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise GitHubAPIError(f"Network error reaching GitHub: {exc}", status_code=503)

    if r.status_code == 404:
        return []
    _raise_for_github_status(r)
    data = r.json()
    # The API returns a list for folders, a dict for files — always return a list
    return data if isinstance(data, list) else []


# ── Write helpers ─────────────────────────────────────────────────────────────

async def gh_put(
    repo: str,
    path: str,
    content: str,
    message: str,
    sha: Optional[str] = None,
    headers: dict = None,
) -> dict:
    """
    Create or update a text file in a GitHub repo.

    - repo:    owner/repo string, e.g. "zzpanic/ideas-workbench"
    - path:    file path inside the repo, e.g. "my-idea/publish/my-idea.md"
    - content: the full text content to write
    - message: the git commit message
    - sha:     the current file's SHA from GitHub (required when updating an
               existing file; omit when creating a new file)
    - headers: which auth token to use (defaults to WORKBENCH_HEADERS)

    Returns the GitHub API response dict (Contents API format).

    Side effects: creates or overwrites a file and produces a git commit in the repo.

    Raises:
        httpx.HTTPStatusError: e.g. 409 Conflict if sha is wrong/missing for an update.
        httpx.RequestError:    for network failures.
    """
    if headers is None:
        headers = WORKBENCH_HEADERS

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise GitHubAPIError(f"Network error reaching GitHub: {exc}", status_code=503)

    _raise_for_github_status(r)
    return r.json()


async def gh_put_bytes(
    repo: str,
    path: str,
    content: bytes,
    message: str,
    sha: Optional[str] = None,
    headers: dict = None,
) -> dict:
    """
    Create or update a binary file (e.g. a PDF) in a GitHub repo.

    Same parameters as gh_put, except content is raw bytes instead of a string.

    Side effects: creates or overwrites a file and produces a git commit in the repo.

    Raises:
        httpx.HTTPStatusError: e.g. 409 Conflict if sha is wrong/missing for an update.
        httpx.RequestError:    for network failures.
    """
    if headers is None:
        headers = WORKBENCH_HEADERS

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content).decode(),
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise GitHubAPIError(f"Network error reaching GitHub: {exc}", status_code=503)

    _raise_for_github_status(r)
    return r.json()
