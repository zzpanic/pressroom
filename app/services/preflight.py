"""
services/preflight.py — Pre-flight quality checks run before PDF generation.

These are Pressroom-specific checks, not a generic markdown linter.  Generic
linters produce noise on academic markdown — they don't understand
[PLACEHOLDER: ...] syntax, footnotes, citation styles, or the fact that headings
don't need to be sequential in a working draft.

Checks performed (in order):
  1. Required frontmatter fields  — title must exist for the PDF header
  2. Unresolved placeholders      — [PLACEHOLDER: ...] markers left in the text
  3. LaTeX-unsafe bare characters — % and & outside code blocks will crash XeLaTeX
  4. Empty body                   — nothing to render

Returns a PreflightResult with errors (blocking) and warnings (advisory).
Routers block PDF generation on errors but surface warnings to the author
in the UI via response headers.

SPEC REFERENCE: §7.4 "Publish Workflow" step 2 — pre-flight validation
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Issue:
    """
    A single pre-flight finding.

    severity:  "error" blocks PDF generation; "warning" allows it but surfaces in the UI.
    code:      short machine-readable identifier (e.g. "MISSING_TITLE")
    message:   human-readable explanation shown to the user
    """
    severity: str   # "error" or "warning"
    code: str
    message: str


@dataclass
class PreflightResult:
    """
    The combined result of all pre-flight checks.

    errors:   list of Issues with severity="error"  — PDF should not be generated
    warnings: list of Issues with severity="warning" — PDF can be generated but user is informed
    placeholder_count: how many [PLACEHOLDER: ...] markers were found
    """
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    placeholder_count: int = 0

    @property
    def ok(self) -> bool:
        """True if there are no errors (warnings are allowed)."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """One-line summary for logging."""
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        if self.placeholder_count:
            parts.append(f"{self.placeholder_count} placeholder(s)")
        return ", ".join(parts) if parts else "all clear"


# Matches [PLACEHOLDER: anything here]
_PLACEHOLDER_RE = re.compile(r"\[PLACEHOLDER:[^\]]+\]", re.IGNORECASE)

# Matches fenced code blocks (``` or ~~~) — we skip these when checking for
# LaTeX-unsafe characters because code blocks are rendered verbatim, not via LaTeX.
_CODE_FENCE_RE = re.compile(r"```.*?```|~~~.*?~~~", re.DOTALL)

# LaTeX-unsafe bare characters that will crash XeLaTeX if they appear outside
# a \verb or lstlisting environment.  We strip code blocks before checking.
# Note: % is the most common culprit (e.g. "50% of cases").
_LATEX_UNSAFE_RE = re.compile(r"(?<!\\)[%&]")


def run_preflight(frontmatter: dict[str, Any], body: str) -> PreflightResult:
    """
    Run all pre-flight checks and return a PreflightResult.

    PARAMETERS:
    - frontmatter: parsed YAML fields from the paper
    - body:        markdown body text (everything after the frontmatter block)

    RETURNS:
    - PreflightResult with any errors and warnings found

    USAGE:
        result = run_preflight(frontmatter, body)
        if not result.ok:
            raise HTTPException(400, f"Pre-flight failed: {result.errors[0].message}")
        # surface result.warnings and result.placeholder_count to the user
    """
    result = PreflightResult()

    _check_required_fields(frontmatter, result)
    _check_empty_body(body, result)
    _check_placeholders(body, result, frontmatter.get("gate", ""))
    _check_latex_unsafe(body, result)

    return result


def _check_required_fields(fm: dict[str, Any], result: PreflightResult) -> None:
    """Error if title is missing — the PDF header template uses $title$ and will look wrong."""
    if not fm.get("title", "").strip():
        result.errors.append(Issue(
            severity="error",
            code="MISSING_TITLE",
            message="Frontmatter is missing a 'title' field. The PDF template requires it.",
        ))


def _check_empty_body(body: str, result: PreflightResult) -> None:
    """Error if the paper body is empty — nothing to render."""
    if not body.strip():
        result.errors.append(Issue(
            severity="error",
            code="EMPTY_BODY",
            message="The paper body is empty. Add content below the frontmatter block.",
        ))


def _check_placeholders(body: str, result: PreflightResult, gate: str) -> None:
    """
    Count unresolved [PLACEHOLDER: ...] markers.

    At 'review' or 'published' gates this is an error — those gates require zero placeholders.
    At all other gates it's a warning so the author knows how many remain.
    """
    matches = _PLACEHOLDER_RE.findall(body)
    count = len(matches)
    result.placeholder_count = count

    if count == 0:
        return

    # Gates that require zero placeholders
    if gate in ("review", "published"):
        result.errors.append(Issue(
            severity="error",
            code="PLACEHOLDERS_AT_FINAL_GATE",
            message=(
                f"{count} unresolved placeholder(s) found. "
                f"The '{gate}' gate requires all placeholders to be resolved before publishing."
            ),
        ))
    else:
        result.warnings.append(Issue(
            severity="warning",
            code="PLACEHOLDERS_PRESENT",
            message=f"{count} unresolved [PLACEHOLDER: ...] marker(s) in the paper body.",
        ))


def _check_latex_unsafe(body: str, result: PreflightResult) -> None:
    """
    Warn about bare % or & characters outside code blocks.

    XeLaTeX treats % as a comment start and & as a table column separator.
    Both will cause cryptic LaTeX errors if they appear unescaped in the body.
    Common examples: "50% of cases", "Smith & Jones".
    """
    # Remove fenced code blocks before scanning — those are safe
    body_no_code = _CODE_FENCE_RE.sub("", body)

    matches = _LATEX_UNSAFE_RE.findall(body_no_code)
    if not matches:
        return

    # Count occurrences of each character for the message
    pct = matches.count("%")
    amp = matches.count("&")
    parts = []
    if pct:
        parts.append(f"{pct} bare '%' (escape as \\%)")
    if amp:
        parts.append(f"{amp} bare '&' (escape as \\&)")

    result.warnings.append(Issue(
        severity="warning",
        code="LATEX_UNSAFE_CHARS",
        message=(
            "Possible LaTeX-unsafe characters outside code blocks: "
            + ", ".join(parts)
            + ". These may cause PDF generation to fail."
        ),
    ))
