"""
base.py - PDF generation engine protocol for Pressroom.

This file is responsible for:
1. Defining the PDFEngine protocol (abstract base class)
2. Ensuring all PDF engines implement the same generate() method signature
3. Providing factory function to select the correct engine at runtime

DESIGN RATIONALE:
- Protocol ensures all engines return Path to generated PDF
- Factory pattern allows switching engines via config.PDF_ENGINE env var
- Adding a new engine is simple: create new file, implement PDFEngine protocol, add to factory

SPEC REFERENCE: §8 "PDF Generation - Modular Engine Architecture"
         §8.1 "PDFEngine Protocol" (method signatures)
         §8.2 "Engine Selection" (config.PDF_ENGINE)

DEPENDENCIES:
- This file is imported by: services/pdf/pandoc_engine.py, services/pdf/sile_engine.py
- Abstract base class - concrete implementations in pandoc_engine.py, sile_engine.py

ENGINE SELECTION FLOW:
1. User clicks Publish in UI
2. Router calls pdf.generate(slug, body, frontmatter, template)
3. Factory selects engine based on config.PDF_ENGINE ("pandoc" or "sile")
4. Selected engine's generate() method is called
5. Returns Path to generated PDF

TODO: Implement the full PDFEngine class (see module docstring for design)
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class PDFEngine(ABC):
    """
    Abstract base class for PDF generation engines.

    TODO: Implement the full PDFEngine protocol (see module docstring for design)

    ALL CONCRETE ENGINES MUST:
    1. Inherit from PDFEngine
    2. Implement generate() method with exact signature
    3. Return Path to generated PDF file

    FACTORY USAGE:
        engine = get_pdf_engine()
        pdf_path = await engine.generate(
            slug="my-paper",
            body=markdown_body,
            frontmatter=frontmatter,
            template=template_content
        )
    """

    @abstractmethod
    async def generate(
        self,
        slug: str,
        body: str,
        frontmatter: dict[str, Any],
        template: str,
    ) -> Path:
        """
        Generate a PDF file from paper content and template.

        PARAMETERS:
        - slug: Paper identifier (e.g., "my-great-idea")
          Used to create isolated temp directory /tmp/pressroom/{slug}/
        - body: Markdown content AFTER frontmatter
          This is the actual paper text to be rendered
        - frontmatter: Dict of YAML metadata fields
          Contains title, author, gate, version, etc.
        - template: Full text of the template file (LaTeX or Sile format)

        RETURNS:
        - Path to generated PDF file on local filesystem

        SIDE EFFECTS:
        - Creates temp directory /tmp/pressroom/{slug}/
        - Writes markdown content to temp file
        - Writes template to temp file
        - Runs engine CLI to generate PDF

        MUST BE IMPLEMENTED BY:
        - PandocEngine (services/pdf/pandoc_engine.py)
        - SileEngine (services/pdf/sile_engine.py)
        """
        pass


def get_pdf_engine() -> PDFEngine:
    """
    Factory function to select the correct PDF engine at runtime.

    TODO: Implement based on config.PDF_ENGINE setting:
        from config import PDF_ENGINE

        if PDF_ENGINE == "sile":
            from services.pdf.sile_engine import SileEngine
            return SileEngine()
        else:  # Default to pandoc
            from services.pdf.pandoc_engine import PandocEngine
            return PandocEngine()
    """
    pass


async def generate_pdf(slug: str, body: str, frontmatter: dict, template: str) -> Path:
    """
    Generate a PDF for the given paper using the configured engine.

    This is the main entry point called by routers — it selects the engine
    via get_pdf_engine() and delegates to its generate() method.

    PARAMETERS:
    - slug: Paper identifier (used for temp file naming)
    - body: Markdown body text (everything after the frontmatter block)
    - frontmatter: Parsed YAML metadata dict
    - template: Full content of the LaTeX/Sile template file

    RETURNS:
    - Path: Local filesystem path to the generated PDF file

    RAISES:
    - RuntimeError: If no PDF engine is configured (get_pdf_engine stub not yet implemented)

    TODO: This will work automatically once get_pdf_engine() is implemented.
    """
    engine = get_pdf_engine()
    if engine is None:
        raise RuntimeError(
            "PDF engine not yet configured. Implement get_pdf_engine() in services/pdf/base.py."
        )
    return await engine.generate(slug, body, frontmatter, template)