# Adding a PDF Engine to Pressroom

> **Revision:** Generated from docs/SPEC.md on 2026-04-25
>
> This guide explains how to add a new PDF engine to Pressroom, following the existing PDFEngine protocol established by pandoc_engine.py and sile_engine.py.

## Overview

Pressroom uses a modular PDF engine architecture that allows multiple backends (Pandoc, Sile, or future engines) to be plugged in with minimal changes. This document explains:

1. The **PDFEngine protocol/interface** defined in `base.py`
2. How `pandoc_engine.py` implements it
3. Step-by-step instructions for adding a new engine
4. How the engine is selected at runtime

## The PDFEngine Protocol

The PDF engine interface is defined in `app/services/pdf/base.py`:

```python
from abc import ABC, abstractmethod
from pathlib import Path

class PDFEngine(ABC):
    """
    Abstract base class for all PDF generation engines.
    
    Every engine must implement:
    - generate(slug, body, frontmatter, template) -> Path
      Generates a PDF and returns the path to the output file.
    - list_templates() -> list[dict]
      Returns available templates with metadata.
    """
    
    @abstractmethod
    async def generate(self, slug: str, body: str, frontmatter: dict, template: str) -> str:
        """
        Generate a PDF from markdown content.
        
        PARAMETERS:
        - slug: Paper identifier (used for output filename)
        - body: Markdown body content (without frontmatter)
        - frontmatter: Parsed YAML frontmatter dictionary
        - template: LaTeX template content as string
        
        RETURNS:
        - str: Absolute path to the generated PDF file
        
        RAISES:
        - RuntimeError: If PDF generation fails
        """
        ...
    
    @abstractmethod
    async def list_templates(self) -> list:
        """
        List available templates.
        
        RETURNS:
        - list of dicts: [{"name": str, "format": str, ...}, ...]
        """
        ...
```

### Key Design Decisions

1. **Returns file path, not bytes** — The PDF is written to disk and the path is returned. This avoids passing large binary objects through memory.
2. **Template as string** — Templates are resolved separately by `template_resolver.py` and passed as content strings.
3. **Async methods** — All engine methods are async to avoid blocking the event loop (though the actual PDF generation may still be synchronous subprocess calls).

## How Pandoc Engine Implements It

The Pandoc engine in `app/services/pdf/pandoc_engine.py` follows this pattern:

```python
class PandocEngine(PDFEngine):
    """
    Pandoc + XeLaTeX PDF generation engine.
    
    Flow:
    1. Write markdown to temp file
    2. Write template to temp file
    3. Run: pandoc input.md -t latex --template=template.latex
    4. Run: xelatex intermediate.dvi
    5. Return path to output PDF
    """
    
    FORMAT = "pdf-xelatex"
    EXTENSION = ".pdf"
    
    async def generate(self, slug: str, body: str, frontmatter: dict, template: str) -> str:
        # 1. Create temp directory
        work_dir = Path(f"/tmp/pressroom/{slug}")
        work_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Write markdown content
        md_path = work_dir / f"{slug}.md"
        md_path.write_text(self._build_markdown(body, frontmatter))
        
        # 3. Write template content
        tpl_path = work_dir / "template.latex"
        tpl_path.write_text(template)
        
        # 4. Run Pandoc conversion
        cmd = [
            "pandoc", str(md_path),
            "-t", "latex",
            f"--template={tpl_path}",
            "-o", str(work_dir / f"{slug}.tex"),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Pandoc failed: {result.stderr}")
        
        # 5. Run XeLaTeX to convert LaTeX to PDF
        cmd = ["xelatex", "-interaction=nonstopmode", f"{slug}.tex"]
        subprocess.run(cmd, cwd=work_dir)
        
        return str(work_dir / f"{slug}.pdf")
    
    async def list_templates(self) -> list:
        # Scan templates directory for .latex files
        ...
```

### Important Implementation Details

1. **Working directory isolation** — Each generation runs in `/tmp/pressroom/{slug}/` to avoid conflicts between concurrent requests.
2. **Error propagation** — Subprocess errors are caught and re-raised as `RuntimeError` with stderr output included.
3. **Temp file cleanup** — The temp directory is created fresh each time; old directories should be cleaned up by a separate maintenance process.

## Step-by-Step: Adding a New Engine

### Step 1: Create the Engine File

Create a new file in `app/services/pdf/` — for example, `app/services/pdf/weasyprint_engine.py`:

```python
"""
weasyprint_engine.py — WeasyPrint HTML-to-PDF engine.

This engine converts markdown to HTML first, then uses WeasyPrint
to generate a PDF from the HTML output.

SPEC REFERENCE: §8.2 "Available Engines"
"""

import subprocess
from pathlib import Path


class WeasyPrintEngine:
    """
    WeasyPrint HTML-to-PDF engine stub.
    
    Flow:
    1. Convert markdown to HTML (using markdown library)
    2. Inject CSS stylesheets from template
    3. Run WeasyPrint HTML -> PDF
    
    TODO: Implement the generate() and list_templates() methods
    """
    
    FORMAT = "pdf-weasyprint"
    EXTENSION = ".pdf"
    
    async def generate(self, slug: str, body: str, frontmatter: dict, template: str) -> str:
        """
        Generate PDF using WeasyPrint.
        
        TODO: Implement
        1. Create temp directory /tmp/pressroom/{slug}/
        2. Convert markdown to HTML
        3. Inject CSS from template
        4. Run: weasyprint input.html output.pdf
        5. Return path to PDF
        
        RAISES:
        - RuntimeError: If WeasyPrint fails
        """
        # TODO: Implement
        pass
    
    async def list_templates(self) -> list:
        """
        List available CSS templates.
        
        TODO: Implement
        Returns [{"name": str, "format": str}, ...]
        """
        # TODO: Implement
        pass
```

### Step 2: Register the Engine

Update `app/services/pdf/base.py` to include the new engine in the `get_pdf_engine()` factory function:

```python
# In base.py - add to the ENGINE_REGISTRY dict or if/elif chain

def get_pdf_engine() -> PDFEngine:
    """
    Get the configured PDF engine instance.
    
    The engine is selected based on the PDF_ENGINE environment variable.
    """
    engine = os.getenv("PDF_ENGINE", "pandoc").lower()
    
    if engine == "pandoc":
        from .pandoc_engine import PandocEngine
        return PandocEngine()
    elif engine == "sile":
        from .sile_engine import SileEngine
        return SileEngine()
    elif engine == "weasyprint":
        from .weasyprint_engine import WeasyPrintEngine  # <-- Add this
        return WeasyPrintEngine()  # <-- Add this
    else:
        raise ValueError(f"Unknown PDF_ENGINE: {engine}")
```

### Step 3: Handle Engine Selection at Runtime

The engine selection happens in `get_pdf_engine()` based on the `PDF_ENGINE` environment variable. To use your new engine:

```bash
# In .env or docker-compose.yml env vars:
PDF_ENGINE=weasyprint
```

### Step 4: Test the Engine

Run the existing test suite to ensure your engine doesn't break anything:

```bash
pytest tests/test_pdf_engine.py -v
```

The test in `tests/test_pdf_engine.py` mocks the actual PDF generation and verifies:
- The correct engine is selected for each `PDF_ENGINE` value
- The `generate()` method returns a valid path
- The `list_templates()` method returns a non-empty list

## How Engine Selection Works at Runtime

```
User requests PDF preview
        │
        ▼
Env var PDF_ENGINE = "weasyprint" (or "pandoc" or "sile")
        │
        ▼
get_pdf_engine() in base.py
        │
        ▼
Imports and returns the correct engine class instance
        │
        ▼
routers/preview.py calls engine.generate(slug, body, frontmatter, template)
        │
        ▼
Engine-specific implementation runs
        │
        ▼
Returns path to generated PDF
```

## Error Handling Conventions

Every engine should follow the same error handling pattern:

```python
try:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Engine failed: %s", result.stderr)
        raise RuntimeError(f"Engine command failed: {result.stderr}")
except FileNotFoundError as exc:
    raise RuntimeError(f"Required binary not found: {exc}")
except Exception as exc:
    logger.error("Unexpected engine error: %s", exc)
    raise RuntimeError(f"Engine internal error: {exc}")
```

## Template Format Notes

Different engines expect different template formats:

| Engine | Template Format | Extension |
|---|---|---|
| Pandoc | LaTeX with Pandoc template variables | `.latex` |
| Sile | Lua-based typesetting format | `.lufi` |
| WeasyPrint | CSS stylesheets + HTML structure | `.html`, `.css` |

When implementing `list_templates()`, return the correct format identifier so the UI can display the right options.

## Testing Your Engine

### Unit Test Pattern

```python
# In tests/test_pdf_engine.py, add to the parametrized test:

@pytest.mark.parametrize("engine_var,expected_class", [
    ("pandoc", "PandocEngine"),
    ("sile", "SileEngine"),
    ("weasyprint", "WeasyPrintEngine"),  # <-- Add your engine
])
def test_get_pdf_engine(engine_var, expected_class):
    ...
```

### Integration Test

To fully test your engine:
1. Set `PDF_ENGINE=weasyprint` in the test environment
2. Call the preview endpoint with test content
3. Verify a PDF file is created at the returned path
4. Verify the PDF is valid (check magic bytes or use `pypdf`)

## Common Pitfalls

1. **Blocking the event loop** — Subprocess calls in async functions block. Consider using `asyncio.create_subprocess_exec()` for production code (SPEC §10.2).
2. **File descriptor leaks** — Always close subprocess stdout/stderr streams.
3. **Temp file cleanup** — Implement a periodic cleanup of `/tmp/pressroom/` directories.
4. **Template path resolution** — Use absolute paths when passing templates to subprocesses.

---

*This guide was generated from SPEC.md. For the most up-to-date information, refer to the specification document.*