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

from exceptions import PDFGenerationError


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
        Generate a PDF using Pandoc with the XeLaTeX backend.

        PARAMETERS:
        - slug:        Paper identifier — used to name the isolated temp directory
        - body:        Markdown text after the frontmatter block
        - frontmatter: Parsed YAML metadata (title, author, gate, version, …)
        - template:    Full content of the LaTeX template file

        RETURNS:
        - Path: absolute path to the generated PDF (/tmp/pressroom/{slug}/output.pdf)

        RAISES:
        - RuntimeError: if pandoc exits with a non-zero return code (stderr included)

        COMMAND EXECUTED:
            pandoc input.md
                --pdf-engine=xelatex
                --template=template.latex
                -o output.pdf
        """
        import asyncio
        import yaml

        # ── 1. Prepare isolated temp directory ───────────────────────────────
        work_dir = Path(tempfile.gettempdir()) / "pressroom" / slug
        work_dir.mkdir(parents=True, exist_ok=True)

        input_md   = work_dir / "input.md"
        tmpl_latex = work_dir / "template.latex"
        output_pdf = work_dir / "output.pdf"

        # ── 2. Flatten the frontmatter for Pandoc ────────────────────────────
        # The app stores author as a nested dict {name, email, github} but the
        # LaTeX template uses $author$ (a plain string) and $email$ (top-level).
        # Pandoc cannot unpack a nested dict — we must flatten before writing.
        pandoc_fm = dict(frontmatter)
        if isinstance(pandoc_fm.get("author"), dict):
            author_dict = pandoc_fm["author"]
            pandoc_fm["author"] = author_dict.get("name", "")
            pandoc_fm["email"]  = author_dict.get("email", "")
            pandoc_fm["github"] = author_dict.get("github", "")

        fm_yaml = yaml.dump(pandoc_fm, allow_unicode=True, default_flow_style=False)
        input_md.write_text(f"---\n{fm_yaml}---\n\n{body}", encoding="utf-8")

        # ── 3. Write LaTeX template ───────────────────────────────────────────
        tmpl_latex.write_text(template, encoding="utf-8")

        # ── 4. Run pandoc ─────────────────────────────────────────────────────
        # Run in an executor so we don't block the event loop during the
        # (potentially slow) XeLaTeX compilation.
        cmd = [
            "pandoc",
            str(input_md),
            "--pdf-engine=xelatex",
            f"--template={tmpl_latex}",
            "-o", str(output_pdf),
        ]

        # Run Pandoc in a thread pool so the async event loop stays responsive.
        # Timeout of 120 seconds — XeLaTeX on a long paper typically takes 10-30s.
        # If it hasn't finished in 2 minutes something is seriously wrong.
        _PANDOC_TIMEOUT = 120

        loop = asyncio.get_event_loop()
        proc = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(work_dir),
                timeout=_PANDOC_TIMEOUT,
            ),
        )

        if proc.returncode != 0:
            raise PDFGenerationError(
                f"pandoc failed for '{slug}':\n{proc.stderr}",
                engine="pandoc",
                exit_code=proc.returncode,
            )

        return output_pdf