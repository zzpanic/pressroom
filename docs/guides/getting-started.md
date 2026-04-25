# Getting Started with Pressroom

> **Revision:** Generated from docs/SPEC.md on 2026-04-25
>
> This guide is written for new developers and AI coding assistants approaching the Pressroom codebase for the first time.

## What is Pressroom?

Pressroom is a multi-user web application that manages the review, PDF generation, and publication of ideas from user-specific "Ideas Workbenches." It allows authors to write papers in markdown with YAML frontmatter, preview generated PDFs, and publish versioned snapshots to a public repository — all through a browser interface.

In short: Pressroom turns markdown documents into professionally typeset PDFs and publishes them as versioned snapshots.

## Why Does Pressroom Exist?

The project was built to solve a specific problem: researchers and writers need to produce well-formatted academic papers from plain markdown text, with version tracking and public publishing capabilities. Pressroom provides:

1. **A web UI** for writing and editing paper metadata
2. **PDF generation** using Pandoc (or optionally Sile) with customizable LaTeX templates
3. **Version snapshots** that create immutable copies of papers at each gate level
4. **Public publishing** that mirrors snapshots to a public repository

## The Three-Repo Architecture

Pressroom is built around three GitHub repositories, each with a distinct responsibility:

| Repository | Visibility | Purpose |
|---|---|---|
| `ideas-workbench` (per-user) | Private | Where authors write and edit their papers |
| `pressroom` (public) | Public | The app source code itself |
| `pressroom-pubs` (per-user) | Public | Where published snapshots are stored |

**Why three repos?** This separation allows content to remain private while the app code and published output remain public. Each user gets their own isolated workbench and pubs repo.

## How to Run It Locally with Docker

### Prerequisites

- Docker and Docker Compose installed
- GitHub personal access tokens for your repos

### Step 1: Configure Environment Variables

Copy `.env.example` to a new `.env` file and fill in the required values:

```bash
cp .env.example .env
```

At minimum, you need:
- `IDEAS_WORKBENCH_GIT_TOKEN` — your GitHub token for the workbench repo
- `PRESSROOM_PUBS_GIT_TOKEN` — your GitHub token for the pubs repo
- `APP_USER` and `APP_PASSWORD` — login credentials for the web UI

### Step 2: Start the Container

```bash
docker compose up -d
```

This builds the Docker image (using the multi-stage build in `app/Dockerfile`) and starts the container on port 8000.

### Step 3: Access the Application

Open your browser to `http://localhost:8000`. Log in with the credentials you configured.

### Stopping the Application

```bash
docker compose down
```

Data in `/app/data` persists across restarts via the Docker named volume `pressroom-data`.

## The Gate Model Explained Simply

A **gate** represents how mature an idea is. Think of it like a progress meter:

| Gate | What It Means | What's Expected |
|---|---|---|
| **alpha** | Just started | Title and stubs only |
| **exploratory** | Thinking visible | Real content with placeholders |
| **draft** | Getting serious | Structured, substantive content |
| **review** | Nearly done | Complete, no unresolved items |
| **published** | Live! | Final, packaged version |

Each gate promotion creates a new **snapshot** — an immutable copy of the paper at that point in time. The version string (e.g., `v0.1-exploratory`) encodes both the development phase and current gate.

## Where to Look: Codebase Map

```
pressroom/
├── app/                              # Application code
│   ├── main.py                       # FastAPI entry point, /api/health endpoint
│   ├── auth.py                       # Authentication (HTTP Basic + JWT stubs)
│   ├── config.py                     # Environment variable management
│   ├── database.py                   # SQLite schema and connection management
│   ├── github.py                     # GitHub API abstraction layer
│   ├── logging_config.py             # Structured JSON logging setup
│   ├── models.py                     # Pydantic request/response models
│   ├── routers/                      # HTTP endpoint definitions
│   │   ├── papers.py                 # Paper CRUD endpoints
│   │   ├── publish.py                # Publish and snapshot endpoints
│   │   ├── templates.py              # Template listing/upload
│   │   └── preview.py                # PDF preview generation
│   └── services/                     # Business logic
│       ├── frontmatter.py            # YAML parsing/writing
│       ├── pdf/                      # PDF generation engines
│       │   ├── base.py               # PDFEngine protocol (interface)
│       │   ├── pandoc_engine.py     # Pandoc + XeLaTeX implementation
│       │   └── sile_engine.py       # Sile stub
│       ├── snapshot.py               # Snapshot creation and mirroring
│       └── publishers/             # Extensible publish formats
│           ├── base.py
│           ├── pdf.py
│           └── blog.py
├── tests/                            # Test suite
│   ├── conftest.py                   # Shared fixtures
│   ├── test_frontmatter.py           # Frontmatter parsing tests
│   ├── test_auth.py                  # Auth unit tests
│   └── integration/                  # Integration tests
├── docs/
│   ├── SPEC.md                       # Full system specification
│   ├── index.html                    # HTML rendering of SPEC
│   └── guides/                       # Developer guides (this directory)
├── templates/                        # Default LaTeX template
│   └── whitepaper.md                 # Template preview
├── docker-compose.yml                # Container orchestration
└── app/Dockerfile                    # Multi-stage Docker build
```

### Key Files to Understand

| File | Why It Matters |
|---|---|
| `app/config.py` | All configuration flows through here — env vars, validation |
| `app/github.py` | Every GitHub API call goes through these functions |
| `app/routers/publish.py` | The publish workflow entry point |
| `app/services/pdf/pandoc_engine.py` | The main PDF generation logic |
| `app/services/snapshot.py` | Creates versioned snapshots and mirrors to pubs |

## Next Steps

- Read [`docs/architecture.md`](./architecture.md) for a deep dive into the three-layer architecture
- Read [`docs/guides/publishing-workflow.md`](./publishing-workflow.md) for the step-by-step publish flow
- Read [`docs/SPEC.md`](../SPEC.md) for the full system specification

---

*This guide was generated from SPEC.md. For the most up-to-date information, refer to the specification document.*