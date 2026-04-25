"""
template_resolver.py - Template resolution and management for Pressroom.

This file is responsible for:
1. Resolving which template to use for a given paper/publish operation
2. Loading template content from the user's workbench repository or local files
3. Providing template metadata (name, format, preview)
4. Validating template compatibility with the requested output format

DESIGN RATIONALE:
- Templates can come from two sources: user's workbench repo (multi-user) or local files (single-user)
- Template resolution happens before PDF generation - the engine needs both content AND template
- Caching is important - templates don't change often, so we should cache resolved templates

SPEC REFERENCE: §8.3 "Template Resolution"
         §8.4 "Template Formats" (LaTeX vs Sile)
         §5.1 "Author-Specific Config" (templates directory structure)

DEPENDENCIES:
- This file is imported by: services/pdf/pandoc_engine.py, services/pdf/sile_engine.py
- Imports from: config (TEMPLATE_DIR, user workbench paths)

TEMPLATE RESOLUTION FLOW:
1. User selects a template in the UI (e.g., "whitepaper")
2. Router calls template_resolver.resolve_template(template_name, user_id)
3. Function searches for template in:
   a. User's workbench zz-pressroom/templates/ directory (multi-user)
   b. Local templates/ directory (single-user fallback)
4. Returns TemplateInfo with path, format, content

TODO: Implement the TemplateInfo dataclass and resolve_template function:
    from dataclasses import dataclass
    from typing import Optional
    
    @dataclass
    class TemplateInfo:
        name: str                    # Template name (e.g., "whitepaper")
        format: str                  # "latex" or "sile"
        content: str                 # Full template file content
        source: str                  # "workbench" or "local"
        path: str                    # Absolute path to template file
    
    async def resolve_template(template_name: str, user_id: Optional[str] = None) -> TemplateInfo:
        """
        Resolve a template by name.
        
        PARAMETERS:
        - template_name: User-selected template name (e.g., "whitepaper")
        - user_id: Authenticated user ID (for multi-user mode)
        
        SEARCH ORDER:
        1. User workbench: /zz-pressroom/templates/{template_name}.{format}
        2. Local templates: templates/{template_name}.{format}
        
        RAISES:
        - TemplateNotFoundError if template not found in either location
        """
        pass
"""

from pathlib import Path
from typing import Optional

from exceptions import TemplateNotFoundError

# Extension used by each engine format
_FORMAT_EXT = {"latex": ".latex", "sile": ".lufi"}

# Where user-uploaded templates live inside the workbench repo
_WORKBENCH_TEMPLATE_DIR = "zz-pressroom/templates"

# Local fallback directory inside the container (bundled with the app image).
# Spec §8.3 says bundled templates live in app/static/templates/.
_LOCAL_TEMPLATE_DIR = Path("/app/static/templates")


class TemplateResolver:
    """
    Resolves LaTeX/Sile templates for PDF generation.

    Search order for resolve_template():
    1. User's workbench repo — zz-pressroom/templates/{name}.{ext}
    2. Local container templates — /app/templates/{name}.{ext}

    This lets users override bundled templates by committing their own to
    their workbench repo without changing the app image.
    """

    async def resolve_template(
        self, template_name: str, user_id: Optional[str] = None
    ) -> dict:
        """
        Find a template by name and return its content and metadata.

        PARAMETERS:
        - template_name: Template name without extension (e.g. "whitepaper")
        - user_id:       Ignored in single-user mode; reserved for multi-user

        RETURNS:
        - dict with keys:
            name    (str) — template_name
            format  (str) — "latex" or "sile"
            content (str) — full file text
            source  (str) — "workbench" or "local"

        RAISES:
        - FileNotFoundError: if the template is not found in either location
        """
        from github import gh_get_text, WORKBENCH_HEADERS
        from config import IDEAS_WORKBENCH_REPO

        # Try each format in preference order (latex before sile)
        for fmt, ext in _FORMAT_EXT.items():
            # 1. Workbench repo
            repo_path = f"{_WORKBENCH_TEMPLATE_DIR}/{template_name}{ext}"
            content = await gh_get_text(
                IDEAS_WORKBENCH_REPO, repo_path, headers=WORKBENCH_HEADERS
            )
            if content is not None:
                return {"name": template_name, "format": fmt, "content": content, "source": "workbench"}

            # 2. Local container fallback
            local_path = _LOCAL_TEMPLATE_DIR / f"{template_name}{ext}"
            if local_path.exists():
                return {
                    "name": template_name,
                    "format": fmt,
                    "content": local_path.read_text(encoding="utf-8"),
                    "source": "local",
                }

        raise TemplateNotFoundError(template_name)

    async def list_templates(self, user_id: Optional[str] = None) -> list:
        """
        Return all available templates from both workbench and local sources.

        RETURNS:
        - list of dicts: [{name, format, source}, ...]
          Workbench templates appear before local ones.
          Duplicates (same name in both) are deduplicated, keeping workbench entry.
        """
        from github import gh_list, WORKBENCH_HEADERS
        from config import IDEAS_WORKBENCH_REPO

        seen: set[str] = set()
        results: list[dict] = []

        # Workbench templates
        try:
            items = await gh_list(
                IDEAS_WORKBENCH_REPO, _WORKBENCH_TEMPLATE_DIR, headers=WORKBENCH_HEADERS
            )
            for item in items:
                fname = item.get("name", "")
                for fmt, ext in _FORMAT_EXT.items():
                    if fname.endswith(ext):
                        name = fname[: -len(ext)]
                        seen.add(name)
                        results.append({"name": name, "format": fmt, "source": "workbench"})
        except Exception:
            # Workbench unavailable — fall through to local only
            pass

        # Local container templates
        if _LOCAL_TEMPLATE_DIR.exists():
            for path in sorted(_LOCAL_TEMPLATE_DIR.iterdir()):
                for fmt, ext in _FORMAT_EXT.items():
                    if path.name.endswith(ext):
                        name = path.name[: -len(ext)]
                        if name not in seen:
                            seen.add(name)
                            results.append({"name": name, "format": fmt, "source": "local"})

        return results

    async def upload_template(
        self, name: str, content: str, fmt: str, user_id: str
    ) -> None:
        """
        Upload a template to the user's workbench repo.

        PARAMETERS:
        - name:    Template name without extension (e.g. "my-journal")
        - content: Full template file text
        - fmt:     "latex" or "sile"
        - user_id: Authenticated user ID (unused in single-user mode)

        RAISES:
        - ValueError: if fmt is not "latex" or "sile"
        - RuntimeError: if the GitHub write fails
        """
        from github import gh_get, gh_put, WORKBENCH_HEADERS
        from config import IDEAS_WORKBENCH_REPO

        if fmt not in _FORMAT_EXT:
            raise ValueError(
                f"Invalid template format '{fmt}'. Must be one of: {', '.join(_FORMAT_EXT)}"
            )

        ext = _FORMAT_EXT[fmt]
        repo_path = f"{_WORKBENCH_TEMPLATE_DIR}/{name}{ext}"

        # Fetch existing SHA so GitHub accepts the update without a conflict
        existing = await gh_get(IDEAS_WORKBENCH_REPO, repo_path, headers=WORKBENCH_HEADERS)
        sha = existing["sha"] if existing else None

        try:
            await gh_put(
                IDEAS_WORKBENCH_REPO,
                repo_path,
                content,
                message=f"pressroom: upload template {name}{ext}",
                sha=sha,
                headers=WORKBENCH_HEADERS,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to upload template '{name}': {exc}") from exc