"""
test_pdf_engine.py — Unit tests for PDF generation engines.

This file contains unit tests for the PandocEngine and SileEngine classes,
testing the generate() method signature and output behavior.

DEPENDENCIES:
- This file tests: services/pdf/pandoc_engine.py, services/pdf/sile_engine.py
- External dependency: pytest (add to requirements.txt when implementing)

TEST CATEGORIES:
1. PandocEngine.generate() — Basic signature test
2. SileEngine.generate() — Basic signature test
3. get_pdf_engine() — Factory function test
"""

import pytest
from pathlib import Path


class TestPandocEngine:
    """Tests for the Pandoc PDF engine."""

    def test_pandoc_engine_generate_returns_path(self):
        """
        Test that generate() returns a Path object.
        
        GIVEN valid input parameters
        WHEN PandocEngine.generate() is called
        THEN it returns a Path to the generated PDF
        """
        # TODO: Implement when services/pdf/pandoc_engine.py exists
        pass

    def test_pandoc_engine_creates_pdf_file(self):
        """
        Test that generate() creates an actual PDF file.
        
        GIVEN valid input parameters
        WHEN PandocEngine.generate() is called
        THEN a PDF file exists at the returned Path
        """
        # TODO: Implement when services/pdf/pandoc_engine.py exists
        pass

    def test_pandoc_engine_invalid_template(self):
        """
        Test generate() with invalid template content.
        
        GIVEN invalid template content
        WHEN PandocEngine.generate() is called
        THEN it raises PDFGenerationError
        """
        # TODO: Implement when services/pdf/pandoc_engine.py exists
        pass


class TestSileEngine:
    """Tests for the Sile PDF engine."""

    def test_sile_engine_generate_returns_path(self):
        """
        Test that generate() returns a Path object.
        
        GIVEN valid input parameters
        WHEN SileEngine.generate() is called
        THEN it returns a Path to the generated PDF
        """
        # TODO: Implement when services/pdf/sile_engine.py exists
        pass

    def test_sile_engine_creates_pdf_file(self):
        """
        Test that generate() creates an actual PDF file.
        
        GIVEN valid input parameters
        WHEN SileEngine.generate() is called
        THEN a PDF file exists at the returned Path
        """
        # TODO: Implement when services/pdf/sile_engine.py exists
        pass


class TestGetPdfEngine:
    """Tests for the PDF engine factory function."""

    def test_get_pdf_engine_default_pandoc(self):
        """
        Test default engine selection.
        
        GIVEN config.PDF_ENGINE != "sile"
        WHEN get_pdf_engine() is called
        THEN it returns a PandocEngine instance
        """
        # TODO: Implement when services/pdf/base.py has get_pdf_engine()
        pass

    def test_get_pdf_engine_sile(self):
        """
        Test Sile engine selection.
        
        GIVEN config.PDF_ENGINE == "sile"
        WHEN get_pdf_engine() is called
        THEN it returns a SileEngine instance
        """
        # TODO: Implement when services/pdf/base.py has get_pdf_engine()
        pass