"""
services/frontmatter.py — YAML frontmatter parsing and writing for paper .md files.

Provides parse_frontmatter(), write_frontmatter(), and apply_derived_fields() — the
core functions for reading and writing the metadata block at the top of each paper's
Markdown file.  Also defines GATE_VERSIONS and LICENSE_URLS constants used across
the app to derive version strings and license URLs from gate/license names.

A markdown file with frontmatter looks like this:

    ---
    title: My Great Idea
    gate: exploratory
    version: v0.1-exploratory
    ---

    # Introduction
    The actual paper text starts here...

Everything between the first --- and the second --- is YAML metadata (frontmatter).
Everything after the second --- is the paper body.  Pressroom reads, modifies, and
writes back only the frontmatter — the body is always preserved exactly as-is.

SPEC REFERENCE: §5 "Frontmatter Schema"
"""

from datetime import datetime
from typing import Any

import yaml


# Maps a gate name to its canonical version string (per spec §4)
GATE_VERSIONS = {
    "alpha":       "v0.1-alpha",
    "exploratory": "v0.1-exploratory",
    "draft":       "v0.2-draft",
    "review":      "v0.3-review",
    "published":   "v1.0",
}

# Maps a license name to its URL
LICENSE_URLS = {
    "CC BY 4.0":  "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-4.0":  "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-NC 4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "MIT":        "https://opensource.org/licenses/MIT",
}


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """
    Split a markdown document into its frontmatter fields and its body text.

    Expects the document to start with a --- delimiter line, followed by YAML,
    followed by another --- delimiter line, then the body.

    Returns a tuple of (fields, body):
      - fields: a dict of the parsed YAML values (empty dict if no frontmatter)
      - body:   the paper text after the closing --- (empty string if none)

    Example:
        fields, body = parse_frontmatter(md_text)
        print(fields["title"])   # "My Paper"
        print(body[:50])         # "# Introduction\nThe actual paper..."
    """
    # Guard against None — gh_get_text() returns None for missing files
    if text is None:
        return {}, ""

    # If the document doesn't start with ---, there is no frontmatter
    if not text.startswith("---"):
        return {}, text

    # Find the closing --- on its own line (search from position 3 to skip the opening ---)
    closing = text.find("\n---", 3)
    if closing == -1:
        # Opening --- found but no closing --- — treat as no frontmatter
        return {}, text

    # Extract just the YAML block (between the two --- markers)
    yaml_block = text[3:closing].strip()

    # Everything after the closing --- (plus its newline) is the body
    body = text[closing + 4:].lstrip("\n")

    # Parse the YAML — use safe_load so arbitrary Python objects can't be injected
    try:
        fields = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        # Broken YAML: return empty fields but preserve the body (not the full file).
        # We still extract the body so the paper text isn't lost.
        # Callers that need to detect broken frontmatter should check fields == {}.
        return {}, body

    return fields, body


def write_frontmatter(body: str, fields: dict[str, Any]) -> str:
    """
    Produce a complete markdown document by combining YAML frontmatter with body text.

    This is the reverse of parse_frontmatter.  Call it when you want to save
    changes back to {slug}.md — pass the original body (unchanged) and the
    updated fields dict, and this returns the full file text ready to push.

    The field order in the YAML output follows the spec §5 schema.

    Example:
        updated_text = write_frontmatter(body, {"title": "New Title", "gate": "draft", ...})
        # Then push updated_text to GitHub via gh_put()
    """
    # Build the YAML block in a controlled field order that matches the spec schema.
    # yaml.dump would sort keys alphabetically, which is harder to read.
    ordered = _build_ordered_fields(fields)
    yaml_text = yaml.dump(ordered, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return f"---\n{yaml_text}---\n\n{body}"


def apply_derived_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """
    Fill in fields that are automatically derived from other fields.

    Called before writing frontmatter back to GitHub, so the .md file always
    has a complete and consistent set of metadata.

    Derived fields (only set when the source field is present and non-empty):
      - status:      gate name in UPPERCASE (e.g. "exploratory" → "EXPLORATORY"); omitted if gate is absent
      - version:     canonical version string for the gate (e.g. "v0.1-exploratory"); only set if gate is known and version is not already set
      - license_url: URL matching the license name; omitted if license is unknown
      - date:        today's date — always updated on every save
    """
    updated = dict(fields)

    gate = updated.get("gate", "")

    # status is always the gate name in uppercase
    if gate:
        updated["status"] = gate.upper()

    # version follows the gate if it hasn't been manually overridden
    if gate and gate in GATE_VERSIONS and not updated.get("version"):
        updated["version"] = GATE_VERSIONS[gate]

    # license_url is derived from the license name
    license_name = updated.get("license", "")
    if license_name in LICENSE_URLS:
        updated["license_url"] = LICENSE_URLS[license_name]

    # date is always updated to today
    updated["date"] = datetime.utcnow().strftime("%Y-%m-%d")

    return updated


def _build_ordered_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """
    Return a copy of fields with keys in the canonical spec §5 order.

    Any extra keys (e.g. checklist) are appended after the spec fields.
    This keeps the YAML output readable and predictable.
    """
    # Canonical order from spec §5
    spec_keys = [
        "title", "subtitle", "author", "date", "version", "gate", "status",
        "slug", "license", "license_url", "ai_assisted",
        "github_repo", "zenodo_doi", "prior_art_disclosure",
    ]

    ordered = {}
    # Add spec keys first, in order, skipping any that aren't present
    for key in spec_keys:
        if key in fields:
            ordered[key] = fields[key]

    # Append any remaining keys (e.g. checklist — not in the spec schema but
    # written by Pressroom to persist QA state)
    for key, value in fields.items():
        if key not in ordered:
            ordered[key] = value

    return ordered
