"""
sile_engine.py — Sile PDF generation engine for Pressroom.

This file implements the PDFEngine protocol using Sile (a Lua-based typesetting system) as the PDF backend.

DESIGN RATIONALE:
- Sile is an alternative to LaTeX/Pandoc for PDF generation
- Uses Lua templates (.lufi format) instead of LaTeX (.latex format)
- subprocess.run() executes the Sile CLI with appropriate arguments
- Provides a drop-in replacement for PandocEngine when config.PDF_ENGINE == "sile"

SPEC REFERENCE: §8.2 "Sile Engine — Alternative PDF Backend"
         §8.2.4 "Command Line Invocation" (sile CLI arguments)
         §8.4 "Template Formats" (Lua/Sile format vs LaTeX)

DEPENDENCIES:
- This file implements: PDFEngine protocol from base.py
- Imported by: services/pdf/base.py (get_pdf_engine factory when PDF_ENGINE=="sile")

PDF GENERATION FLOW:
1. Router calls pdf.generate(slug, body, frontmatter, template)
2. Engine creates temp dir /tmp/pressroom/{slug}/
3. Writes frontmatter + body to input.md
4. Writes template to template.lufi (Sile format)
5. Runs: sile -o output.pdf template.lufi input.md
6. Returns Path to output.pdf

TODO: Implement the full SileEngine class (see module docstring for design)

USAGE IN ROUTERS:
    engine = get_pdf_engine()  # Returns SileEngine if config.PDF_ENGINE=="sile"
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


class SileEngine:
    """
    Sile PDF engine using Lua templates.

    TODO: Implement the full SileEngine class (see module docstring for design)

    INTEGRATION POINTS:
    - Called by get_pdf_engine() factory in base.py when config.PDF_ENGINE == "sile"
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
        Generate PDF using Sile + Lua templates.

        PARAMETERS:
        - slug: Paper identifier (e.g., "my-great-idea")
          Used to create isolated temp directory /tmp/pressroom/{slug}/
        - body: Markdown content AFTER frontmatter
          This is the actual paper text to be rendered
        - frontmatter: Dict of YAML metadata fields
          Contains title, author, gate, version, etc.
        - template: Full text of the Sile/Lua template file

        RETURNS:
        - Path to generated PDF file on local filesystem

        SIDE EFFECTS:
        - Creates temp directory /tmp/pressroom/{slug}/
        - Writes markdown content to input.md
        - Writes template to template.lufi
        - Runs sile CLI to generate PDF
        - Cleans up temp files after generation

        COMMAND LINE EXAMPLE:
            sile -o output.pdf \\
                template.lufi \\
                input.md

        TODO: Implement:
        1. Create temp dir /tmp/pressroom/{slug}/
        2. Write frontmatter + body to input.md
        3. Write template to template.lufi (note: .lufi extension for Sile)
        4. Run subprocess with sile CLI arguments
        5. Return Path to output.pdf

        COMPARISON WITH PandocEngine:
        - Both must return Path to the same output location
        - Pandoc uses .latex templates, Sile uses .lufi templates
        - Pandoc uses xelatex backend, Sile uses Lua runtime
        - Output PDF format is identical (both produce standard PDF)

        ERROR HANDLING:
        - If sile subprocess returns non-zero exit code, raise PDFGenerationError
        - Capture stderr for error message
        """
        pass