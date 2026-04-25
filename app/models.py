"""
models.py — Pydantic request/response validation models for the Pressroom API.

This file is responsible for:
1. Defining Pydantic BaseModel classes for request body validation
2. Defining response model classes for API documentation (OpenAPI/Swagger)
3. Ensuring type safety and automatic input validation
4. Providing auto-generated API documentation

DESIGN RATIONALE:
- Pydantic validates incoming JSON against schemas before reaching route handlers
- Invalid input returns 422 Unprocessable Entity with clear error messages
- The schemas are automatically documented in Swagger UI (/docs endpoint)
- Using models instead of raw dicts enables IDE autocomplete and type checking

SPEC REFERENCE: §12.3 "Input Validation"
         §5 "Frontmatter Schema" (field definitions)
         §6 "Versioned Snapshot Naming" (version string format)

DEPENDENCIES:
- This file is imported by: all routers (papers.py, preview.py, publish.py, auth.py)
- External dependency: pydantic (add to requirements.txt when implementing)

MIGRATION FROM CURRENT STATE:
- Currently routers accept raw dicts or no validation
- After adding models, replace Body(...) with model class in route decorators
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


# ──────────────────────────────────────────────────────────────────
# AUTHENTICATION MODELS
# ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """
    Request model for /api/auth/login endpoint.

    Used when user submits username/password via POST request body.
    Pydantic validates that both fields are present and are strings.
    """
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class LoginResponse(BaseModel):
    """
    Response model for /api/auth/login endpoint.

    Returns a JWT token on successful login.
    """
    access_token: str = Field(..., description="JWT bearer token")
    token_type: str = Field(default="bearer", description="Always 'bearer'")


class TokenUpdateRequest(BaseModel):
    """
    Request model for /api/auth/token endpoint (saving GitHub token).

    Used when user saves or updates their GitHub personal access token.
    """
    github_token: str = Field(..., min_length=10, description="GitHub personal access token (ghp_xxxx)")
    repo_url: Optional[str] = Field(None, description="Repository URL (owner/repo format)")


# ──────────────────────────────────────────────────────────────────
# PAPER METADATA MODELS
# ──────────────────────────────────────────────────────────────────

class PaperSaveRequest(BaseModel):
    """
    Request model for saving paper metadata via /api/papers/{slug}/save.

    This model validates the frontmatter fields that the user can edit
    in the UI before saving to the workbench repository.

    FIELD DESCRIPTIONS:
    - title: Paper title (required, 1-200 chars)
    - gate: Current gate level (alpha, exploratory, draft, review, published)
    - version: Semantic version string (auto-derived from gate if not provided)
    - license: Creative Commons license identifier
    - ai_assisted: Dict of AI usage flags
    """
    title: str = Field(..., min_length=1, max_length=200, description="Paper title")
    subtitle: Optional[str] = Field(None, description="One-sentence summary")
    gate: str = Field(..., pattern=r"^(alpha|exploratory|draft|review|published)$",
                      description="Current gate level")
    version: Optional[str] = Field(None, description="Version string (e.g., v0.1-exploratory)")
    license: Optional[str] = Field("CC BY 4.0", description="Creative Commons license")
    ai_assisted: Optional[Dict[str, bool]] = Field(None, description="AI usage disclosure flags")
    prior_art_disclosure: Optional[str] = Field(None, description="Prior art claims")


class PaperResponse(BaseModel):
    """
    Response model for paper data.

    Returns parsed frontmatter + body to the UI.
    """
    slug: str = Field(..., description="Paper slug (folder name)")
    frontmatter: Dict[str, Any] = Field(..., description="Parsed YAML frontmatter fields")
    body: str = Field(..., description="Markdown body text (after frontmatter)")


# ──────────────────────────────────────────────────────────────────
# PUBLISH MODELS
# ──────────────────────────────────────────────────────────────────

class PublishRequest(BaseModel):
    """
    Request model for publishing a paper via /api/papers/{slug}/publish.

    The user selects the version string and gate when publishing.
    This model validates that the request contains valid values.
    """
    version: str = Field(..., min_length=1, description="Version string (e.g., v0.1-exploratory)")
    gate: str = Field(..., pattern=r"^(alpha|exploratory|draft|review|published)$",
                       description="Gate level")


class PublishResponse(BaseModel):
    """
    Response model for publish operation.

    Returns the snapshot location and mirror status.
    """
    snapshot_path: str = Field(..., description="Path to created snapshot")
    mirrored: bool = Field(..., description="Whether mirror to pubs succeeded")
    pubs_path: Optional[str] = Field(None, description="Path in pressroom-pubs repo")


# ──────────────────────────────────────────────────────────────────
# TEMPLATE MODELS
# ──────────────────────────────────────────────────────────────────

class TemplateUploadRequest(BaseModel):
    """
    Request model for uploading a template via /api/templates/upload.

    Used when user uploads a .latex or .lufi template file.
    """
    name: str = Field(..., min_length=1, max_length=100, description="Template name (without extension)")
    content: str = Field(..., min_length=1, description="Full template file content")
    format: str = Field(..., pattern=r"^(latex|sile)$", description="Template format (latex or sile)")


class TemplateResponse(BaseModel):
    """
    Response model for template listing.

    Returns basic template info (name, format, preview).
    """
    name: str = Field(..., description="Template name")
    format: str = Field(..., description="Template format (latex, sile)")
    preview: Optional[str] = Field(None, description="First 200 chars of template content")


# ──────────────────────────────────────────────────────────────────
# TASK STATUS MODELS
# ──────────────────────────────────────────────────────────────────

class TaskStatusResponse(BaseModel):
    """
    Response model for /api/status/{task_id} polling endpoint.

    Used by the UI to check async task progress (PDF generation, template upload).
    """
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., pattern=r"^(pending|running|completed|failed)$",
                        description="Current task status")
    result: Optional[Any] = Field(None, description="Success result (e.g., pdf_path)")
    error: Optional[str] = Field(None, description="Error message if failed")


# ──────────────────────────────────────────────────────────────────
# FRONTMATTER HELPERS
# ──────────────────────────────────────────────────────────────────

def derive_version_from_gate(gate: str) -> str:
    """
    Derive version string from gate name.

    This is a helper function that maps gate names to standard version prefixes.
    Used by both models and services when version is not explicitly provided.

    PARAMETER MAPPING (from SPEC §4):
    - alpha -> v0.1-alpha
    - exploratory -> v0.1-exploratory
    - draft -> v0.2-draft
    - review -> v0.3-review
    - published -> v1.0

    TODO: Move to services/frontmatter.py when refactoring
    """
    GATE_VERSIONS = {
        "alpha": "v0.1-alpha",
        "exploratory": "v0.1-exploratory",
        "draft": "v0.2-draft",
        "review": "v0.3-review",
        "published": "v1.0",
    }
    return GATE_VERSIONS.get(gate, f"v0.0-{gate}")