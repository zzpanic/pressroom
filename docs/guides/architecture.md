# Pressroom Architecture Guide

> **Revision:** Generated from docs/SPEC.md on 2026-04-25
>
> This guide is written for AI coding assistants and developers implementing stubs. It covers module boundaries, data flow, and contracts between layers.

## Three-Layer Architecture Overview

Pressroom follows a clean three-layer architecture:

```
┌─────────────────────────────────────────────────────────────┐
│  HTTP Client / Browser                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Routers   (app/routers/*.py)                       │
│  - Define HTTP endpoints                                     │
│  - Parse request bodies                                      │
│  - Return responses                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ calls
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 2: Services  (app/services/*.py)                      │
│  - Business logic                                            │
│  - Orchestration                                             │
│  - Data transformation                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ calls
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: GitHub API  (app/github.py)                        │
│  - External service abstraction                              │
│  - HTTP requests to GitHub                                   │
│  - Token management                                          │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Routers are thin** — They parse HTTP, call services, return responses. No business logic here.
2. **Services are pure** — They implement logic without direct HTTP awareness. They don't know about requests or responses.
3. **github.py is the only external caller** — All GitHub API calls go through this single module. Services never import `httpx` directly.

## Data Flow: A Typical Request End-to-End

Let's trace a paper save request through the system:

```
1. Browser sends POST /api/papers/my-paper/save with JSON body
        │
        ▼
2. routers/papers.py::save_paper() receives request
   - Parses request.json()
   - Calls check_auth() for authentication
        │
        ▼
3. config.get_user_config() loads author.yaml from workbench
   - Reads user preferences
        │
        ▼
4. github.gh_get() fetches current .md file from GitHub
   - Returns existing content and SHA
        │
        ▼
5. services/frontmatter.py::parse_frontmatter() extracts body
   - Splits YAML frontmatter from markdown body
        │
        ▼
6. services/frontmatter.py::write_frontmatter() rebuilds document
   - Merges new fields into existing frontmatter
        │
        ▼
7. github.gh_put() pushes updated content back to GitHub
   - Uses SHA for optimistic concurrency
```

### Module Boundaries and Contracts

#### Routers Layer (`app/routers/`)

**Responsibilities:**
- Define FastAPI route handlers
- Validate request bodies via Pydantic models
- Call service functions
- Return HTTP responses (JSON, FileResponse, etc.)

**Not responsible for:**
- Business logic (delegates to services)
- Direct GitHub API calls (delegates to github.py)
- Data persistence (delegates to database.py when needed)

**Key contracts:**
```python
# Every router endpoint follows this pattern:
@router.<method>(<path>)
async def <handler>(<path_params>, request: Request, auth: str = Depends(check_auth)):
    # 1. Parse request
    body = await request.json()

    # 2. Call services
    result = await some_service.do_something(body["field"])

    # 3. Return response
    return {"ok": True, "result": result}
```

#### Services Layer (`app/services/`)

**Responsibilities:**
- Implement business logic (frontmatter manipulation, PDF generation, snapshot creation)
- Orchestrate multiple steps (e.g., publish workflow)
- Transform data between formats

**Not responsible for:**
- Defining HTTP endpoints
- Parsing HTTP requests
- Direct socket/network operations

**Key contracts:**
```python
# Service functions are async and accept typed parameters:
async def process_paper(slug: str, body: str, frontmatter: dict) -> dict:
    """
    Docstring describes:
    - Parameters accepted
    - Return value structure
    - Side effects (if any)
    - Exceptions raised
    """
    ...
    return {"status": "processed", "slug": slug}
```

#### GitHub API Layer (`app/github.py`)

**Responsibilities:**
- All GitHub REST API calls
- Token injection via headers
- Response parsing (JSON, content decoding)

**Not responsible for:**
- Business logic
- Request validation
- Error handling beyond HTTP status codes

**Key functions and their contracts:**
```python
async def gh_get(repo: str, path: str, token: str = None) -> dict | None:
    """
    Fetch a file or folder from GitHub.

    PARAMETERS:
    - repo: Full repo spec (e.g., "user/ideas-workbench")
    - path: File path within the repo
    - token: Optional override token (uses configured token if not provided)

    RETURNS:
    - dict with keys: name, sha, content, html_url, etc.
    - None if file not found (404)
    """

async def gh_get_text(repo: str, path: str, token: str = None) -> str | None:
    """
    Fetch file content as decoded text.

    RETURNS:
    - str: Decoded UTF-8 content
    - None if file not found
    """

async def gh_put(repo: str, path: str, content: str, message: str, token = None, sha = None) -> dict:
    """
    Create or update a file in the repo.

    PARAMETERS:
    - sha: If provided, updates existing file (optimistic concurrency)
    """

async def gh_list(repo: str, path: str = "") -> list:
    """
    List files in a repository path.

    RETURNS:
    - list of dicts: [{"name": ..., "type": "file"|"dir", ...}, ...]
    """
```

## Error Handling Conventions

### Routers Layer

All exceptions from services are caught and converted to HTTP errors:
```python
try:
    result = await service.do_something()
except FileNotFoundError as exc:
    raise HTTPException(404, str(exc))
except ValueError as exc:
    raise HTTPException(400, str(exc))
except Exception as exc:
    logger.error("Unexpected error in %s", __name__, extra={"error": str(exc)})
    raise HTTPException(500, "Internal server error")
```

### Services Layer

Services raise descriptive exceptions:
- `FileNotFoundError` — Resource not found
- `ValueError` — Invalid input data
- `RuntimeError` — Unexpected state
- Custom exception classes in `app/exceptions.py` for domain-specific errors

### GitHub API Layer

Errors are logged and re-raised:
```python
try:
    response = await client.get(url, headers=headers)
    response.raise_for_status()
except httpx.HTTPStatusError as exc:
    logger.error("GitHub API error: %s %s", exc.response.status_code, exc.response.text)
    raise
```

## The GitHub API Abstraction Layer Specifically

### Why a Single Point of Entry?

All GitHub calls go through `github.py` to ensure:
1. **Token management is centralized** — tokens are injected via headers in one place
2. **Rate limiting awareness** — the module tracks per-token usage
3. **Retry logic** — transient failures can be retried in one place
4. **Testing** — github.py can be mocked entirely for unit tests

### How Token Injection Works

```python
async def _make_request(method: str, url: str, repo: str, token: str = None, **kwargs) -> httpx.Response:
    # Determine which token to use
    effective_token = token or get_user_token()

    headers = {
        "Authorization": f"token {effective_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Pressroom/1.0",
    }

    # Make the HTTP call
    async with httpx.AsyncClient() as client:
        return await client.request(method, url, headers=headers, **kwargs)
```

### Key Implementation Notes for AI Assistants

When implementing new stubs:

1. **Add functions to `github.py`**, not directly in services
2. **Services call github.py functions** — never import `httpx` directly
3. **Document the return type** in docstrings — this is the contract
4. **Use `# TODO:` comments** for unimplemented logic within stubs