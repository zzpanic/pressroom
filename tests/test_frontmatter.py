"""
test_frontmatter.py — Unit tests for frontmatter parsing.

This file contains unit tests for the frontmatter parsing functionality.
Tests verify that YAML metadata is correctly extracted and validated.

DEPENDENCIES:
- This file tests: services/frontmatter.py (existing)
- External dependency: pytest (add to requirements.txt when implementing)

TEST CATEGORIES:
1. parse_frontmatter() — Extract YAML from markdown
2. validate_frontmatter() — Validate required fields
3. apply_derived_fields() — Auto-derive version from gate
"""

import pytest


class TestParseFrontmatter:
    """Tests for frontmatter parsing."""

    def test_parse_valid_frontmatter(self):
        """
        Test parsing valid frontmatter with all required fields.
        
        GIVEN markdown with valid YAML frontmatter
        WHEN parse_frontmatter() is called
        THEN it returns dict with title, author, gate, version
        """
        # TODO: Implement when services/frontmatter.py exists
        # markdown = "---\\ntitle: My Paper\\nauthor: John\\ngate: alpha\\nversion: v0.1-alpha\\n---\\n\\nBody text"
        # result = parse_frontmatter(markdown)
        # assert result["title"] == "My Paper"
        # assert result["author"] == "John"
        
        pass

    def test_parse_missing_required_field(self):
        """
        Test parsing frontmatter missing required 'title' field.
        
        GIVEN markdown with frontmatter missing title
        WHEN parse_frontmatter() is called
        THEN it raises InvalidFrontmatterError
        """
        # TODO: Implement when services/frontmatter.py exists
        pass

    def test_parse_empty_body(self):
        """
        Test parsing frontmatter with empty body text.
        
        GIVEN markdown with frontmatter but no body
        WHEN parse_frontmatter() is called
        THEN it returns frontmatter dict and empty body string
        """
        # TODO: Implement when services/frontmatter.py exists
        pass

    def test_parse_no_frontmatter(self):
        """
        Test parsing markdown without frontmatter delimiters.
        
        GIVEN markdown without --- delimiters
        WHEN parse_frontmatter() is called
        THEN it returns empty frontmatter and full text as body
        """
        # TODO: Implement when services/frontmatter.py exists
        pass


class TestValidateFrontmatter:
    """Tests for frontmatter validation."""

    def test_validate_valid_gate(self):
        """
        Test validation with valid gate value.
        
        GIVEN frontmatter with gate="alpha"
        WHEN validate_frontmatter() is called
        THEN it returns without raising exception
        """
        # TODO: Implement when services/frontmatter.py exists
        pass

    def test_validate_invalid_gate(self):
        """
        Test validation with invalid gate value.
        
        GIVEN frontmatter with gate="test"
        WHEN validate_frontmatter() is called
        THEN it raises InvalidGateError
        """
        # TODO: Implement when services/frontmatter.py exists
        pass

    def test_validate_missing_title(self):
        """
        Test validation with missing title field.
        
        GIVEN frontmatter without title
        WHEN validate_frontmatter() is called
        THEN it raises InvalidFrontmatterError
        """
        # TODO: Implement when services/frontmatter.py exists
        pass


class TestApplyDerivedFields:
    """Tests for derived field computation."""

    def test_derive_version_from_gate_alpha(self):
        """
        Test version derivation for alpha gate.
        
        GIVEN gate="alpha" and no version provided
        WHEN apply_derived_fields() is called
        THEN it sets version="v0.1-alpha"
        """
        # TODO: Implement when services/frontmatter.py exists
        frontmatter = {"gate": "alpha"}
        result = apply_derived_fields(frontmatter)
        assert result["version"] == "v0.1-alpha"

    def test_derive_version_from_gate_published(self):
        """
        Test version derivation for published gate.
        
        GIVEN gate="published" and no version provided
        WHEN apply_derived_fields() is called
        THEN it sets version="v1.0"
        """
        # TODO: Implement when services/frontmatter.py exists
        frontmatter = {"gate": "published"}
        result = apply_derived_fields(frontmatter)
        assert result["version"] == "v1.0"

    def test_preserve_explicit_version(self):
        """
        Test that explicit version is not overwritten.
        
        GIVEN gate="alpha" and version="v0.2-custom" provided
        WHEN apply_derived_fields() is called
        THEN it keeps version="v0.2-custom"
        """
        # TODO: Implement when services/frontmatter.py exists
        frontmatter = {"gate": "alpha", "version": "v0.2-custom"}
        result = apply_derived_fields(frontmatter)
        assert result["version"] == "v0.2-custom"