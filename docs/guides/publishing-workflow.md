# Pressroom Publishing Workflow

> **Revision:** Generated from docs/SPEC.md on 2026-04-25
>
> A step-by-step walkthrough of the full publish flow, from raw markdown to published snapshot.

## Overview

The publishing workflow transforms a user's raw markdown document into a professionally typeset PDF, creates a versioned snapshot, and mirrors it to the public pressroom-pubs repository. This document traces each step and explains what service and router is responsible for what.

## The Full Flow

```
User's Workbench                 Pressroom App                   Pressroom Pubs
┌─────────────────┐            ┌─────────────────┐              ┌─────────────────┐
│ markdown file   │            │ PDF generation  │              │ versioned snapshot│
│ {slug}/publish/ │ ──────►    │ frontmatter parse │ ──────►    │ frontmatter.yaml  │
│ {slug}.md       │            │ template resolve  │ ──────►    │ body.md           │
└─────────────────┘            └─────────────────┘              └─────────────────┘
        │                                │                              ▲
        │     1. Pull                    │                              │
        │     2. Generate PDF            │                              │
        │     3. Write review copy       │                              │
        │     4. Review/PDF preview      │                              │
        │     5. Approve                 │                              │
        │                                │                              │
        │                                │  6. Snapshot               │
        │                                │  7. Mirror to pubs         │
        └────────────────────────────────┼──────────────────────────────┘
                                         ▼
                                 Response to client
```

## Step-by-Step Breakdown

### Step 1: Pull — Fetch Current State from Workbench

**What happens:** Pressroom fetches the current `.md` file from the user's ideas-workbench repository via GitHub API.

**Where it happens:**
- `app/routers/papers.py::get_paper()` — fetches via `gh_get_text()`
- `app/github.py::gh_get_text()` — makes HTTP request to GitHub

**Data flow:**
```python
md_text = await gh_get_text(IDEAS_WORKBENCH_REPO, f"{slug}/publish/{slug}.md")
```

**Returns:** Raw markdown text with embedded YAML frontmatter at the top.

---

### Step 2: Generate PDF — Convert Markdown to Typeset Document

**What happens:** The markdown content is converted to PDF using a PDF engine (Pandoc or Sile) with the user's chosen template.

**Where it happens:**
- `app/routers/preview.py::preview_pdf()` — entry point for PDF preview
- `app/services/pdf/base.py::PDFEngine` — protocol/interface
- `app/services/pdf/pandoc_engine.py::PandocEngine.generate()` — actual implementation
- `app/services/template_resolver.py::TemplateResolver.resolve_template()` — finds the template

**Data flow:**
```python
# 1. Resolve template
template = await template_resolver.resolve_template(template_name, user_id)

# 2. Parse frontmatter from markdown
frontmatter, body = parse_frontmatter(md_text)

# 3. Generate PDF
pdf_path = await get_pdf_engine().generate(
    slug=slug,
    body=body,
    frontmatter=frontmatter,
    template=template["content"]
)
```

**Dependencies:**
- Pandoc must be installed in the Docker container (handled by multi-stage build)
- LaTeX packages must be available (xelatex for XeLaTeX engine)
- Template files must exist in the user's workbench or app bundles

---

### Step 3: Write Review Copy — Save PDF to Workbench

**What happens:** The generated PDF is written to a "review" location in the workbench repository so the user can preview it.

**Where it happens:**
- `app/github.py::gh_put()` — pushes binary content to GitHub
- Path: `{slug}/publish/{slug}.pdf`

**Important:** This step creates the review copy that the user sees when they click "Preview PDF" in the UI. The PDF must exist before publishing can proceed (see Step 5 validation).

---

### Step 4: Review / PDF Preview — User Verification

**What happens:** The user views the generated PDF in their browser or downloads it for review. They check for:
- Typography quality
- Citation formatting
- Table rendering
- Page breaks
- Overall layout

**Where it happens:**
- UI serves PDF via `/api/preview/{slug}` endpoint
- `app/routers/preview.py::get_preview_pdf()` — returns FileResponse

**User action:** If satisfied, the user clicks "Publish" to proceed. If not, they edit the source markdown and regenerate.

---

### Step 5: Approve — Confirm Publication

**What happens:** When the user clicks "Publish," Pressroom validates that:
1. A version string was provided in the request
2. The review PDF exists (ensuring "Preview PDF" was run first)

**Where it happens:**
- `app/routers/publish.py::publish_paper()` — entry point for publish workflow

**Validation code:**
```python
version = body.get("version")
if not version:
    raise HTTPException(400, "version is required")

# Check that the review PDF exists before attempting to snapshot.
pdf_path = f"{slug}/publish/{slug}.pdf"
pdf_exists = await gh_get(IDEAS_WORKBENCH_REPO, pdf_path) is not None

if not pdf_exists:
    raise HTTPException(
        409,
        f"Review PDF not found at {pdf_path}.\n"
        "Click 'Preview PDF' first to generate and save the review copy."
    )
```

---

### Step 6: Snapshot — Create Versioned Copy

**What happens:** An immutable snapshot of the paper's current state is created in a versioned folder within the workbench repository.

**Where it happens:**
- `app/services/snapshot.py::create_snapshot()` — main function
- Creates directory structure: `{slug}/v{version}/`
- Writes `frontmatter.yaml` and `body.md` files

**Data flow:**
```python
snapshot_path = await create_snapshot(
    slug=slug,
    body=md_body,           # Current markdown body
    frontmatter=fields,     # Current frontmatter dict
    gate=current_gate,      # Current gate level
    user_id=user_id
)
```

**What gets written:**
```
{slug}/v0.1-exploratory/
├── frontmatter.yaml    # Parsed YAML frontmatter
└── body.md             # Raw markdown body content
```

**Key properties:**
- Snapshots are **never modified** once created
- Each gate promotion creates a new snapshot
- The version string encodes both semver and gate level (e.g., `v0.1-exploratory`)

---

### Step 7: Mirror to Pressroom-Pubs — Publish Publicly

**What happens:** The snapshot is copied from the private workbench repository to the public pressroom-pubs repository, making it visible to the world.

**Where it happens:**
- `app/services/snapshot.py::mirror_to_pubs()` — copies to pubs repo
- Uses GitHub API to clone/push to pressroom-pubs

**Data flow:**
```python
await mirror_to_pubs(
    snapshot_path=snapshot_path,
    github_token=github_token
)
```

**Operations performed:**
1. Clone/fetch pressroom-pubs repository (or use existing local copy)
2. Copy snapshot directory into repo at correct path
3. Commit and push to main branch

**Error handling:** If snapshot succeeds but mirror fails, the user gets a clear error message indicating which part succeeded and which failed — so they know the ideas-workbench snapshot is safe but pubs needs a retry.

---

## What Each Service Is Responsible For

| Service | Responsibility in Publish Flow |
|---|---|
| `services/frontmatter.py` | Parse YAML frontmatter, extract body, merge new fields |
| `services/template_resolver.py` | Find and load the user's LaTeX template |
| `services/pdf/pandoc_engine.py` | Convert markdown + template to PDF |
| `services/snapshot.py` | Create versioned snapshot directory with frontmatter.yaml and body.md |
| `github.py` | All GitHub API operations (fetch, push, list) |
| `routers/preview.py` | Serve PDF preview to browser |
| `routers/publish.py` | Orchestrate the publish endpoint |

## Version String and Gate Levels

The version string is derived from the current gate level:

| Gate | Version Pattern | Example |
|---|---|---|
| alpha | v0.1-alpha | Initial stub, title only |
| exploratory | v0.1-exploratory | Real content, thinking visible |
| draft | v0.2-draft | Structured and substantive |
| review | v0.3-review | Complete, no placeholders |
| published | v1.0-published | Final packaged version |

The version is either auto-generated from the gate or explicitly provided by the user in the publish request body:
```json
{ "version": "v0.1-exploratory" }
```

## Error Cases and Recovery

| Error | Cause | Recovery |
|---|---|---|
| 400 "version is required" | No version in publish request | Provide version string |
| 409 "Review PDF not found" | Preview PDF not generated yet | Run "Preview PDF" first |
| 500 "Snapshot failed" | Filesystem or template error | Check logs, fix template |
| 500 "Mirror failed" | GitHub API error during push | Retry publish endpoint |

## Log Points for Debugging

When troubleshooting a publish failure, check these log points:
1. `gh_get_text()` — Did the markdown file load correctly?
2. `parse_frontmatter()` — Was YAML parsed successfully?
3. `resolve_template()` — Which template was selected?
4. `PandocEngine.generate()` — Pandoc exit code and stderr output
5. `create_snapshot()` — Directory creation success
6. `mirror_to_pubs()` — GitHub API response

---

*This guide was generated from SPEC.md. For the most up-to-date information, refer to the specification document.*