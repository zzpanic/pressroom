"""
services/pdf.py — Main entry point for PDF generation services.

This file provides the main interface to PDF generation functionality.
It acts as a thin wrapper that coordinates between:
1. The PDF engine factory (determines which engine to use)
2. The actual PDF engines (Pandoc, Sile, etc.)
3. The frontmatter processing

The generate_pdf() function is the main entry point for all PDF generation.

SPEC REFERENCE: §7.4 "Publish Workflow" — PDF Generation
"""

import tempfile
import os
import logging
from pathlib import Path

from .base import PDFEngine, get_pdf_engine


async def generate_pdf(slug: str, body: str, frontmatter: dict, template_content: str) -> Path:
    """
    Generate a PDF from markdown content using the configured PDF engine.
    
    PARAMETERS:
    - slug: Paper identifier (used for temporary file paths)
    - body: Markdown body content
    - frontmatter: Frontmatter fields dict
    - template_content: Raw LaTeX template content
    
    RETURNS:
    - Path: Path to the generated PDF file
    
    SIDE EFFECTS:
    - Creates temporary files in /tmp/pressroom/{slug}/ directory
    - Generates a PDF file that can be served or stored
    
    SPEC REFERENCE: §7.4 "Publish Workflow" step 3 — Generate PDF
    
    EXAMPLE:
        >>> output_path = await generate_pdf("my-paper", body, frontmatter, template_content)
        >>> print(output_path)  # Path to the generated PDF
    """
    # Create temporary directory for this paper's PDF operations
    temp_dir = Path(tempfile.gettempdir()) / "pressroom" / slug
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the configured PDF engine (defaults to Pandoc if not specified)
    engine = get_pdf_engine()
    
    # Generate the PDF using the selected engine
    pdf_path = temp_dir / f"{slug}.pdf"
    
    try:
        # Call the engine's generate method with appropriate parameters
        result = await engine.generate(slug, body, frontmatter, template_content)
        return result
    except Exception as e:
        logging.error(f"PDF generation failed for slug {slug}: {str(e)}")
        raise RuntimeError(f"PDF generation failed: {str(e)}")
