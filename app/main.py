"""
Pressroom — Independent Ideas Publishing Workbench
FastAPI application
"""

import os
import json
import base64
import subprocess
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

# ── Config ────────────────────────────────────────────────────────────────────

GITHUB_TOKEN    = os.environ["GITHUB_TOKEN"]
GITHUB_REPO     = os.environ["GITHUB_REPO"]         # papers repo e.g. zzpanic/ideas-workbench
PRESSROOM_REPO  = os.environ["PRESSROOM_REPO"]      # app repo e.g. zzpanic/pressroom
GITHUB_BRANCH   = os.environ.get("GITHUB_BRANCH", "main")
ZENODO_TOKEN    = os.environ.get("ZENODO_TOKEN", "")
APP_USER        = os.environ.get("APP_USER", "admin")
APP_PASSWORD    = os.environ.get("APP_PASSWORD", "pressroom")
AUTHOR_NAME     = os.environ.get("AUTHOR_NAME", "")
AUTHOR_EMAIL    = os.environ.get("AUTHOR_EMAIL", "")
AUTHOR_GITHUB   = os.environ.get("AUTHOR_GITHUB", "")

GITHUB_API  = "https://api.github.com"
HEADERS     = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

TEMP_DIR = Path("/tmp/pressroom")
TEMP_DIR.mkdir(exist_ok=True)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Pressroom")
security = HTTPBasic()

app.mount("/static", StaticFiles(directory="/app/static"), name="static")


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username.encode(), APP_USER.encode())
    ok_pass = secrets.compare_digest(credentials.password.encode(), APP_PASSWORD.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── GitHub helpers ────────────────────────────────────────────────────────────

async def gh_get(repo: str, path: str) -> Optional[dict]:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


async def gh_get_text(repo: str, path: str) -> Optional[str]:
    data = await gh_get(repo, path)
    if data is None:
        return None
    return base64.b64decode(data["content"]).decode("utf-8")


async def gh_put(repo: str, path: str, content: str, message: str, sha: Optional[str] = None):
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    async with httpx.AsyncClient() as client:
        r = await client.put(url, headers=HEADERS, json=payload)
    r.raise_for_status()
    return r.json()


async def gh_list(repo: str, path: str) -> list:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}?ref={GITHUB_BRANCH}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=HEADERS)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else []


async def gh_trigger_action(basename: str, version: str):
    """Trigger publish workflow in pressroom repo."""
    url = f"{GITHUB_API}/repos/{PRESSROOM_REPO}/actions/workflows/publish.yml/dispatches"
    payload = {
        "ref": GITHUB_BRANCH,
        "inputs": {"basename": basename, "version": version},
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, headers=HEADERS, json=payload)
    r.raise_for_status()


def build_pandoc_meta(manifest: dict) -> dict:
    """Extract flat metadata fields for Pandoc — no nested objects."""
    return {
        "title":    manifest.get("title", "Untitled"),
        "author":   manifest.get("author", ""),
        "email":    manifest.get("email", ""),
        "date":     manifest.get("date_modified", datetime.utcnow().strftime("%Y-%m-%d")),
        "version":  manifest.get("version", ""),
        "gate":     manifest.get("gate", ""),
        "license":  manifest.get("license", ""),
        "abstract": manifest.get("abstract", ""),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(_: str = Depends(check_auth)):
    html = Path("/app/static/index.html").read_text()
    return HTMLResponse(html)


@app.get("/api/config")
async def get_config(_: str = Depends(check_auth)):
    return {
        "author_name":   AUTHOR_NAME,
        "author_email":  AUTHOR_EMAIL,
        "author_github": AUTHOR_GITHUB,
        "github_repo":   GITHUB_REPO,
        "pressroom_repo": PRESSROOM_REPO,
    }


@app.get("/api/templates")
async def list_templates(_: str = Depends(check_auth)):
    """List available templates from pressroom repo."""
    items = await gh_list(PRESSROOM_REPO, "templates")
    return [i["name"].replace(".md", "") for i in items if i["name"].endswith(".md")]


@app.get("/api/templates/{name}")
async def get_template(name: str, _: str = Depends(check_auth)):
    """Return template content and extracted headers from pressroom repo."""
    content = await gh_get_text(PRESSROOM_REPO, f"templates/{name}.md")
    if content is None:
        raise HTTPException(404, f"Template {name} not found")
    headers = [
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("#") and not line.startswith("<!--")
    ]
    return {"name": name, "content": content, "headers": headers}


@app.get("/api/licenses")
async def list_licenses(_: str = Depends(check_auth)):
    """List available licenses from pressroom repo."""
    items = await gh_list(PRESSROOM_REPO, "licenses")
    return [i["name"].replace(".md", "") for i in items if i["name"].endswith(".md")]


@app.get("/api/papers")
async def list_papers(_: str = Depends(check_auth)):
    """List all paper folders from ideas-workbench root."""
    items = await gh_list(GITHUB_REPO, "")
    return [i["name"] for i in items if i["type"] == "dir" and not i["name"].startswith(".")]


@app.get("/api/papers/{basename}")
async def get_paper(basename: str, _: str = Depends(check_auth)):
    """Load publish/manifest.json for a paper."""
    manifest_raw = await gh_get_text(GITHUB_REPO, f"{basename}/publish/manifest.json")
    paper_exists = await gh_get(GITHUB_REPO, f"{basename}/publish/paper.md") is not None

    manifest = json.loads(manifest_raw) if manifest_raw else {}

    if not manifest.get("author"):
        manifest["author"]         = AUTHOR_NAME
        manifest["email"]          = AUTHOR_EMAIL
        manifest["author_github"]  = AUTHOR_GITHUB

    return {
        "basename":     basename,
        "manifest":     manifest,
        "paper_exists": paper_exists,
    }


@app.get("/api/papers/{basename}/versions")
async def get_versions(basename: str, _: str = Depends(check_auth)):
    """List published version folders for a paper."""
    items = await gh_list(GITHUB_REPO, basename)
    versions = [
        i["name"] for i in items
        if i["type"] == "dir" and i["name"] not in ("publish",)
    ]
    return sorted(versions)


@app.post("/api/papers/{basename}/manifest")
async def save_manifest(basename: str, request: Request, _: str = Depends(check_auth)):
    """Write publish/manifest.json to ideas-workbench."""
    manifest = await request.json()
    manifest["date_modified"] = datetime.utcnow().strftime("%Y-%m-%d")

    content = json.dumps(manifest, indent=2)
    path    = f"{basename}/publish/manifest.json"

    existing = await gh_get(GITHUB_REPO, path)
    sha      = existing["sha"] if existing else None

    await gh_put(
        GITHUB_REPO,
        path,
        content,
        f"pressroom: update manifest for {basename}",
        sha=sha,
    )
    return {"ok": True}


@app.post("/api/papers/{basename}/publish")
async def publish_paper(basename: str, request: Request, _: str = Depends(check_auth)):
    """Trigger the publish workflow in pressroom."""
    body    = await request.json()
    version = body.get("version")
    if not version:
        raise HTTPException(400, "version required")
    await gh_trigger_action(basename, version)
    return {"ok": True, "message": f"Publish triggered for {basename} {version}"}


@app.get("/api/preview/{basename}")
async def preview_pdf(basename: str, _: str = Depends(check_auth)):
    """Fetch paper.md, manifest, and latex template at runtime. Run Pandoc. Return PDF."""

    # fetch paper
    paper_md = await gh_get_text(GITHUB_REPO, f"{basename}/publish/paper.md")
    if paper_md is None:
        raise HTTPException(404, f"publish/paper.md not found for {basename}")

    # fetch manifest
    manifest_raw = await gh_get_text(GITHUB_REPO, f"{basename}/publish/manifest.json")
    manifest     = json.loads(manifest_raw) if manifest_raw else {}

    # fetch latex template at runtime from pressroom
    template_name = manifest.get("template", "whitepaper")
    latex_raw     = await gh_get_text(PRESSROOM_REPO, f"pandoc/{template_name}.latex")
    if latex_raw is None:
        raise HTTPException(404, f"pandoc/{template_name}.latex not found in pressroom")

    # write temp files
    work_dir = TEMP_DIR / basename
    work_dir.mkdir(exist_ok=True)

    paper_path    = work_dir / "paper.md"
    meta_path     = work_dir / "meta.yaml"
    template_path = work_dir / f"{template_name}.latex"
    output_path   = work_dir / "paper.pdf"

    paper_path.write_text(paper_md)
    template_path.write_text(latex_raw)

    # write flat YAML metadata — no nested objects
    pandoc_meta = build_pandoc_meta(manifest)
    meta_path.write_text(yaml.dump(pandoc_meta, allow_unicode=True))

    cmd = [
        "pandoc", str(paper_path),
        "--template",      str(template_path),
        "--metadata-file", str(meta_path),
        "--pdf-engine=xelatex",
        "-o", str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise HTTPException(500, f"Pandoc error:\n{result.stderr}")

    return FileResponse(
        output_path,
        media_type="application/pdf",
        filename=f"{basename}-preview.pdf",
    )


@app.get("/api/preview/{basename}/download")
async def download_pdf(basename: str, _: str = Depends(check_auth)):
    """Return last generated preview PDF as a download."""
    output_path = TEMP_DIR / basename / "paper.pdf"
    if not output_path.exists():
        raise HTTPException(404, "No preview generated yet — run preview first")
    return FileResponse(
        output_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{basename}-preview.pdf"'},
    )
