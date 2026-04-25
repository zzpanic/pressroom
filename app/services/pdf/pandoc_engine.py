"""
pandoc_engine.py - Pandoc PDF generation engine for Pressroom.

This file implements the PDFEngine protocol using Pandoc (via XeLaTeX) as the PDF backend.

DESIGN RATIONALE:
- Pandoc is the default and most mature PDF engine
- Uses XeLaTeX backend for UTF-8 and CJK character support
- Templates are LaTeX (.latex) files written to temp directories at runtime
- subprocess.run() executes the Pandoc CLI with appropriate arguments

SPEC REFERENCE: §8.2 "Pandoc Engine - Default PDF Backend"
         §8.2.1 "Command Line Invocation" (pandoc CLI arguments)
         §8.2.3 "Temp Directory Isolation" (/tmp/pressroom/{slug}/)

DEPENDENCIES:
- This file implements: PDFEngine protocol from base.py
- Imported by: services/pdf/base.py (get_pdf_engine factory)

PDF GENERATION FLOW:
1. Router calls pdf.generate(slug, body, frontmatter, template)
2. Engine creates temp dir /tmp/pressroom/{slug}/
3. Writes frontmatter + body to input.md
4. Writes template to template.latex
5. Runs: pandoc --pdf-engine=xelatex -t latex template.latex input.md -o output.pdf
6. Returns Path to output.pdf

TODO: Implement the full PandocEngine class (see module docstring for design)

USAGE IN ROUTERS:
    engine = get_pdf_engine()  # Returns PandocEngine by default
    pdf_path = await engine.generate(
        slug="my-paper",
        body=markdown_body,
        frontmatter=frontmatter,
        template=template_content
    )
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any


class PandocEngine:
    """
    Pandoc PDF engine using XeLaTeX backend.

    TODO: Implement the full PandocEngine class (see module docstring for design)

    INTEGRATION POINTS:
    - Called by get_pdf_engine() factory in base.py when config.PDF_ENGINE != "sile"
    - Called by routers/publish.py publish_paper() endpoint
    - Called by routers/papers.py save_paper() when auto-generating PDF
    """

    async def generate(
        self,
        slug: str,
        body: str,
        frontmatter: dict[str, Any],
        template: str,
    ) -> Path:
        """
        Generate PDF using Pandoc + XeLaTeX.

        PARAMETERS:
        - slug: Paper identifier (e.g., "my-great-idea")
          Used to create isolated temp directory /tmp/pressroom/{slug}/
        - body: Markdown content AFTER frontmatter
          This is the actual paper text to be rendered
        - frontmatter: Dict of YAML metadata fields
          Contains title, author, gate, version, etc.
        - template: Full text of the LaTeX template file

        RETURNS:
        - Path to generated PDF file on local filesystem

        SIDE EFFECTS:
        - Creates temp directory /tmp/pressroom/{slug}/
        - Writes markdown content to input.md
        - Writes template to template.latex
        - Runs pandoc CLI to generate PDF
        - Cleans up temp files after generation

        COMMAND LINE EXAMPLE:
            pandoc --pdf-engine=xelatex \\
                -t latex \\
                template.latex \\
                input.md \\
                -o output.pdf

        TODO: Implement:
        1. Create temp dir /tmp/pressroom/{slug}/
        2. Write frontmatter + body to input.md
        3. Write template to template.latex
        4. Run subprocess with pandoc CLI arguments
        5. Return Path to output.pdf

        ERROR HANDLING:
        - If pandoc subprocess returns non-zero exit code, raise PDFGenerationError
        - Capture stderr for error message
        """
        pass