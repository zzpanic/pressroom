# config.py
# ─────────────────────────────────────────────────────────────────────────────
# All environment variables and app-wide constants live here.
# Every other file imports from this module — nothing reads os.environ directly
# except this file.  That means if an env var name ever changes, you only have
# to update it in one place.
#
# Set these in your Dockge stack.env file (copy .env.example and fill in real
# values).  The app will refuse to start if a required variable is missing.
# ─────────────────────────────────────────────────────────────────────────────

import os
from pathlib import Path


# ── Ideas Workbench ───────────────────────────────────────────────────────────
# The private GitHub repo that holds your ideas, drafts, and publish folders.
# This token needs repo scope (read + write) on ideas-workbench.

IDEAS_WORKBENCH_GIT_USER  = os.environ.get("IDEAS_WORKBENCH_GIT_USER", "")
IDEAS_WORKBENCH_GIT_TOKEN = os.environ["IDEAS_WORKBENCH_GIT_TOKEN"]
IDEAS_WORKBENCH_REPO      = os.environ["IDEAS_WORKBENCH_REPO"]   # e.g. zzpanic/ideas-workbench


# ── Pressroom Pubs ────────────────────────────────────────────────────────────
# The public GitHub repo that receives versioned, published snapshots.
# This token needs repo scope (read + write) on pressroom-pubs.

PRESSROOM_PUBS_GIT_USER   = os.environ.get("PRESSROOM_PUBS_GIT_USER", "")
PRESSROOM_PUBS_GIT_TOKEN  = os.environ["PRESSROOM_PUBS_GIT_TOKEN"]
PRESSROOM_PUBS_REPO       = os.environ["PRESSROOM_PUBS_REPO"]    # e.g. zzpanic/pressroom-pubs


# ── Pressroom App Repo ────────────────────────────────────────────────────────
# The public repo containing this app's source code.
# Used to fetch LaTeX templates and prompt templates at runtime.
# Read-only — the workbench token is fine here since pressroom is public.

PRESSROOM_REPO = os.environ.get("PRESSROOM_REPO", "zzpanic/pressroom")


# ── Git Branch ────────────────────────────────────────────────────────────────
# Which branch to read from and write to in all three repos.
# You almost certainly want "main".

GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")


# ── App Authentication ────────────────────────────────────────────────────────
# Username and password for the Pressroom web UI.
# Change these from the defaults before exposing the app to any network.

APP_USER     = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "pressroom")


# ── GitHub API ────────────────────────────────────────────────────────────────
# Base URL for the GitHub REST API.  Unlikely to ever need changing.

GITHUB_API = "https://api.github.com"


# ── Temp Directory ────────────────────────────────────────────────────────────
# Where Pandoc working files are written during PDF generation.
# This is inside the Docker container — nothing here survives a restart.

TEMP_DIR = Path("/tmp/pressroom")
TEMP_DIR.mkdir(exist_ok=True)
