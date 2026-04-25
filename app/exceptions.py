"""
exceptions.py — Custom exception classes for the Pressroom application.

This file is responsible for:
1. Defining custom exception classes that provide structured error information
2. Creating exception hierarchies for different error categories
3. Providing exception handlers that return consistent JSON error responses

DESIGN RATIONALE:
- Custom exceptions allow us to add structured data (error codes, field names)
- Exception hierarchy enables targeted error handling in routers
- Consistent error response format helps frontend error handling

SPEC REFERENCE: §12 "Security" (error handling requirements)
         §7.5 "Publish Workflow" (workflow-specific errors)

DEPENDENCIES:
- This file is imported by: all routers (for specific exceptions)
- No external dependencies — uses only Python standard library

ERROR RESPONSE FORMAT:
All API errors return JSON with this structure:
{
    "error": {
        "code": "INVALID_FRONTMATTER",
        "message": "Gate value 'invalid' is not valid",
        "field": "gate",
        "details": {...}
    }
}

TODO: Register exception handlers in main.py:
    app.add_exception_handler(PaperNotFoundError, handle_paper_not_found)
    app.add_exception_handler(GitHubAPIError, handle_github_error)
    etc.
"""

from typing import Optional, Dict, Any


# ──────────────────────────────────────────────────────────────────
# BASE EXCEPTION CLASS
# ──────────────────────────────────────────────────────────────────

class PressroomException(Exception):
    """
    Base exception class for all Pressroom-specific errors.

    This class provides a common interface for all custom exceptions:
    - error_code: Machine-readable error identifier
    - http_status: Default HTTP status code
    - details: Additional structured error information

    USAGE:
        raise InvalidGateError("Value 'test' is not valid", gate="test")

    TODO: In main.py exception handlers, convert these to JSON responses:
        async def handle_custom_exception(request, exc):
            return JSONResponse(
                status_code=exc.http_status,
                content={"error": exc.error_code, "message": str(exc), "details": exc.details}
            )
    """

    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", http_status: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status
        self.details = dict(details) if details else {}  # shallow copy — caller cannot mutate our state


# ──────────────────────────────────────────────────────────────────
# INPUT VALIDATION EXCEPTIONS
# ──────────────────────────────────────────────────────────────────

class InvalidFrontmatterError(PressroomException):
    """
    Raised when frontmatter contains invalid or missing required fields.

    EXAMPLES:
    - Missing required field (title, slug)
    - Invalid gate value
    - Malformed YAML syntax

    TODO: Raise in services/frontmatter.py parse_frontmatter() validation
    """

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="INVALID_FRONTMATTER",
            http_status=422,
            details={"field": field}
        )


class InvalidGateError(InvalidFrontmatterError):
    """
    Raised when gate value is not one of the valid values.

    VALID GATES (from SPEC §4):
    - alpha
    - exploratory
    - draft
    - review
    - published

    TODO: Raise in services/frontmatter.py apply_derived_fields() validation
    """

    def __init__(self, gate: str):
        super().__init__(
            message=f"Gate value '{gate}' is not valid. Must be one of: alpha, exploratory, draft, review, published",
            field="gate",
        )


# ──────────────────────────────────────────────────────────────────
# RESOURCE NOT FOUND EXCEPTIONS
# ──────────────────────────────────────────────────────────────────

class PaperNotFoundError(PressroomException):
    """
    Raised when a paper/slug is not found in the workbench repository.

    EXAMPLES:
    - User requests preview for non-existent slug
    - Save request for slug that doesn't have a folder

    TODO: Raise in routers/papers.py get_paper() and save_paper() routes
    """

    def __init__(self, slug: str):
        super().__init__(
            message=f"Paper not found: {slug}",
            error_code="PAPER_NOT_FOUND",
            http_status=404,
            details={"slug": slug}
        )


class TemplateNotFoundError(PressroomException):
    """
    Raised when a requested template is not found.

    TODO: Raise in services/template_resolver.py resolve_template()
    """

    def __init__(self, template_name: str):
        super().__init__(
            message=f"Template not found: {template_name}",
            error_code="TEMPLATE_NOT_FOUND",
            http_status=404,
            details={"template_name": template_name}
        )


# ──────────────────────────────────────────────────────────────────
# GITHUB API EXCEPTIONS
# ──────────────────────────────────────────────────────────────────

class GitHubAPIError(PressroomException):
    """
    Raised when GitHub API call fails.

    EXAMPLES:
    - Network timeout
    - 403 Forbidden (rate limit, wrong token)
    - 404 Not Found (repo doesn't exist)
    - 500 Internal Server Error (GitHub downtime)

    TODO: Raise in github.py helpers when httpx request fails
    """

    def __init__(self, message: str, status_code: int = 500, response_body: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="GITHUB_API_ERROR",
            http_status=status_code,
            details={"status_code": status_code, "response_body": response_body}
        )


class GitHubRateLimitError(GitHubAPIError):
    """
    Raised when GitHub API rate limit is exceeded.

    TODO: Raise in github.py when response contains 403 with rate-limit header
    """

    def __init__(self, reset_at: Optional[str] = None):
        super().__init__(
            message="GitHub API rate limit exceeded",
            status_code=429,
            response_body=f"Rate limit resets at: {reset_at}" if reset_at else None,
        )


# ──────────────────────────────────────────────────────────────────
# PDF GENERATION EXCEPTIONS
# ──────────────────────────────────────────────────────────────────

class PDFGenerationError(PressroomException):
    """
    Raised when PDF generation fails.

    EXAMPLES:
    - Pandoc subprocess returns non-zero exit code
    - XeLaTeX compilation fails (LaTeX syntax error in template)
    - Template file not found
    - Out of disk space during generation

    TODO: Raise in services/pdf/pandoc_engine.py generate() on subprocess failure
    """

    def __init__(self, message: str, engine: str = "unknown", exit_code: Optional[int] = None):
        super().__init__(
            message=message,
            error_code="PDF_GENERATION_ERROR",
            http_status=500,
            details={"engine": engine, "exit_code": exit_code}
        )


# ──────────────────────────────────────────────────────────────────
# AUTHENTICATION EXCEPTIONS
# ──────────────────────────────────────────────────────────────────

class AuthenticationError(PressroomException):
    """
    Raised when authentication fails.

    TODO: Raise in auth.py check_auth() or auth_store.py verify_credentials()
    """

    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_FAILED",
            http_status=401
        )


class TokenDecryptionError(PressroomException):
    """
    Raised when GitHub token decryption fails.

    TODO: Raise in auth_store.py decrypt_token() if ciphertext is corrupted
    """

    def __init__(self, message: str = "Token decryption failed"):
        super().__init__(
            message=message,
            error_code="TOKEN_DECRYPTION_ERROR",
            http_status=500
        )


# ──────────────────────────────────────────────────────────────────
# WORKFLOW EXCEPTIONS
# ──────────────────────────────────────────────────────────────────

class PublishWorkflowError(PressroomException):
    """
    Raised when publish workflow fails at any step.

    TODO: Raise in routers/publish.py publish_paper() on step failure
    """

    def __init__(self, message: str, step: str = "unknown"):
        super().__init__(
            message=message,
            error_code="PUBLISH_WORKFLOW_ERROR",
            http_status=500,
            details={"step": step}
        )


class SnapshotCreationError(PublishWorkflowError):
    """
    Raised when snapshot creation fails.

    TODO: Raise in services/snapshot.py create_snapshot()
    """

    def __init__(self, message: str, slug: str = "", version: str = ""):
        context = f" (slug={slug!r}, version={version!r})" if slug or version else ""
        super().__init__(
            message=message + context,
            step="snapshot_creation",
        )


class MirrorError(PublishWorkflowError):
    """
    Raised when mirror to pressroom-pubs fails.

    TODO: Raise in services/snapshot.py mirror_to_pubs()
    """

    def __init__(self, message: str, pubs_repo: str = ""):
        context = f" (pubs_repo={pubs_repo!r})" if pubs_repo else ""
        super().__init__(
            message=message + context,
            step="mirror_to_pubs",
        )