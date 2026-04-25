"""
pdf.py — DEPRECATED: PDF generation services have moved to the pdf/ subpackage.

This file is a deprecation shim that redirects imports to the new location.
All PDF-related code has been moved to:
- services/pdf/base.py — PDFEngine protocol
- services/pdf/pandoc_engine.py — Pandoc engine implementation
- services/pdf/sile_engine.py — Sile engine implementation
- services/pdf/factory.py — Factory function for engine selection

TODO: Remove this file once all imports have been migrated.
"""

import warnings

# Redirect users to the new location
warnings.warn(
    "app.services.pdf is deprecated. Import from app.services.pdf.base instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export for backward compatibility (deprecated)
from services.pdf.base import PDFEngine, get_pdf_engine

__all__ = ["PDFEngine", "get_pdf_engine"]