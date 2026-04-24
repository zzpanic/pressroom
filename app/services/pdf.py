# services/pdf.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles PDF generation using Pandoc + XeLaTeX.
#
# Pandoc is a command-line tool that converts documents between formats.
# XeLaTeX is a LaTeX engine that produces PDFs and handles modern fonts well.
# Both are pre-installed in the pandoc/extra Docker image this app uses.
#
# Font note
# ─────────
# XeLaTeX can only use fonts that are physically installed in the Docker image.
# If you see errors like "font not found" or "cannot find file", the LaTeX
# template is asking for a font that isn't there.  The Dockerfile installs a
# set of common free fonts (Liberation, DejaVu) to cover typical use cases.
# If you need a specific font, add it with apt-get in the Dockerfile.
#
# The LaTeX template (whitepaper.latex) lives in the pressroom GitHub repo
# and is fetched at runtime — it is NOT bundled in the Docker image.
# ─────────────────────────────────────────────────────────────────────────────

import subprocess
from pathlib import Path

import yaml

from config import TEMP_DIR


def _build_pandoc_meta(frontmatter: dict) -> dict:
    """
    Extract the metadata fields that the LaTeX template expects.

    Pandoc reads metadata from a separate YAML file and makes each field
    available as a variable inside the LaTeX template (e.g. $title$, $author$).

    The author field in the spec is a nested dict {name, email, github}, but
    Pandoc's LaTeX templates typically expect author as a flat string, so we
    flatten it here.  The template can then use $author$ and $email$ directly.
    """
    # author may be a dict {name, email, github} or a plain string
    author_field = frontmatter.get("author", "")
    if isinstance(author_field, dict):
        author_name  = author_field.get("name", "")
        author_email = author_field.get("email", "")
    else:
        author_name  = str(author_field)
        author_email = frontmatter.get("email", "")

    return {
        "title":    frontmatter.get("title", "Untitled"),
        "subtitle": frontmatter.get("subtitle", ""),
        "author":   author_name,
        "email":    author_email,
        "date":     frontmatter.get("date", ""),
        "version":  frontmatter.get("version", ""),
        "gate":     frontmatter.get("gate", ""),
        "license":  frontmatter.get("license", ""),
        "abstract": frontmatter.get("abstract", ""),
    }


def generate_pdf(slug: str, paper_body: str, frontmatter: dict, latex_template: str) -> Path:
    """
    Render a paper to PDF using Pandoc + XeLaTeX.

    Parameters:
      slug:           The idea slug (e.g. "my-great-idea").  Used to name temp files.
      paper_body:     The markdown content of the paper (everything AFTER the
                      frontmatter block — just the actual text, no --- delimiters).
      frontmatter:    Dict of the paper's metadata fields (title, author, gate, etc.)
      latex_template: The full text of the .latex template file fetched from GitHub.

    Returns:
      Path to the generated PDF file on the local filesystem.

    Raises:
      RuntimeError: if Pandoc exits with an error. The error message contains
                    the full Pandoc/XeLaTeX stderr output for debugging.
    """
    # Create a working directory for this slug under /tmp/pressroom/
    work_dir = TEMP_DIR / slug
    work_dir.mkdir(exist_ok=True)

    template_name = frontmatter.get("template", "whitepaper")

    # Paths for all temp files Pandoc needs
    paper_path    = work_dir / f"{slug}.md"          # the paper body (no frontmatter)
    meta_path     = work_dir / "meta.yaml"           # flat metadata for Pandoc variables
    template_path = work_dir / f"{template_name}.latex"  # the LaTeX template
    output_path   = work_dir / f"{slug}.pdf"         # final output

    # Write the paper body — we strip the frontmatter before passing here,
    # so Pandoc doesn't see the --- block and get confused
    paper_path.write_text(paper_body, encoding="utf-8")

    # Write the LaTeX template fetched from GitHub
    template_path.write_text(latex_template, encoding="utf-8")

    # Write the flat metadata YAML that Pandoc will use to fill template variables
    pandoc_meta = _build_pandoc_meta(frontmatter)
    meta_path.write_text(yaml.dump(pandoc_meta, allow_unicode=True))

    # Build the Pandoc command
    cmd = [
        "pandoc", str(paper_path),
        "--template",      str(template_path),   # use our custom LaTeX template
        "--metadata-file", str(meta_path),        # inject title, author, etc.
        "--pdf-engine=xelatex",                   # use XeLaTeX for modern font support
        "-o", str(output_path),
    ]

    # Run Pandoc.  capture_output=True collects stdout and stderr so we can
    # return the error message if something goes wrong.
    # Note: subprocess.run blocks the async event loop while Pandoc runs
    # (~5-30 seconds).  This is acceptable for a single-user local tool.
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return output_path
