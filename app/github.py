# github.py
# ─────────────────────────────────────────────────────────────────────────────
# All GitHub API calls go through the helper functions in this file.
# Nothing else in the app talks to GitHub directly.
#
# Two repos need different auth tokens (ideas-workbench and pressroom-pubs),
# so this module exposes two pre-built header dicts — WORKBENCH_HEADERS and
# PUBS_HEADERS — and every function accepts a `headers` parameter so the
# caller can choose which identity to use.
#
# Most calls operate on ideas-workbench, so WORKBENCH_HEADERS is the default
# and callers only need to pass PUBS_HEADERS for pressroom-pubs operations.
# ─────────────────────────────────────────────────────────────────────────────

import base64
from typing import Optional

import httpx

from config import (
    IDEAS_WORKBENCH_GIT_TOKEN,
    PRESSROOM_PUBS_GIT_TOKEN,
    GITHUB_BRANCH,
    GITHUB_API,
)


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

async def gh_get(repo: str, path: str, headers: dict = None) -> Optional[dict]:
    """
    Fetch a single file's metadata + base64 content from GitHub.

    Returns None if the file doesn't exist (404).
    Returns the raw GitHub API response dict on success (structure is GitHub's
    Contents API format — callers should not depend on undocumented keys).

    Side effects: makes an HTTPS GET request to api.github.com.

    Raises:
        httpx.HTTPStatusError: for any non-404 HTTP error (e.g. 401, 403, 500).
        httpx.RequestError:    for network failures (timeout, DNS, connection refused).
    """
    if headers is None:
        headers = WORKBENCH_HEADERS

    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)

    if r.status_code == 404:
        return None
    r.raise_for_status()
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
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers)

    if r.status_code == 404:
        return []
    r.raise_for_status()
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

    async with httpx.AsyncClient() as client:
        r = await client.put(url, headers=headers, json=payload)
    r.raise_for_status()
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

    async with httpx.AsyncClient() as client:
        r = await client.put(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()
