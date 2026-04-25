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

from exceptions import PDFGenerationError


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
        Generate a PDF using the Sile typesetting system.

        PARAMETERS:
        - slug:        Paper identifier — used to name the isolated temp directory
        - body:        Markdown text after the frontmatter block
        - frontmatter: Parsed YAML metadata (title, author, gate, version, …)
        - template:    Full content of the Sile/Lua (.lufi) template file

        RETURNS:
        - Path: absolute path to the generated PDF (/tmp/pressroom/{slug}/output.pdf)

        RAISES:
        - RuntimeError: if sile exits with a non-zero return code (stderr included)

        COMMAND EXECUTED:
            sile template.lufi -o output.pdf
        """
        import asyncio
        import yaml

        # ── 1. Prepare isolated temp directory ───────────────────────────────
        work_dir = Path(tempfile.gettempdir()) / "pressroom" / slug
        work_dir.mkdir(parents=True, exist_ok=True)

        input_md   = work_dir / "input.md"
        tmpl_lufi  = work_dir / "template.lufi"
        output_pdf = work_dir / "output.pdf"

        # ── 2. Write input markdown ───────────────────────────────────────────
        fm_yaml = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
        input_md.write_text(f"---\n{fm_yaml}---\n\n{body}", encoding="utf-8")

        # ── 3. Write Sile/Lua template ────────────────────────────────────────
        tmpl_lufi.write_text(template, encoding="utf-8")

        # ── 4. Run sile ───────────────────────────────────────────────────────
        cmd = [
            "sile",
            str(tmpl_lufi),
            "-o", str(output_pdf),
        ]

        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(work_dir),
            ),
        )

        if proc.returncode != 0:
            raise PDFGenerationError(
                f"sile failed for '{slug}':\n{proc.stderr}",
                engine="sile",
                exit_code=proc.returncode,
            )

        return output_pdf