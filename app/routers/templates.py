from fastapi import APIRouter, Depends, HTTPException

from auth import check_auth
from config import PRESSROOM_REPO
from github import gh_get_text, gh_list

router = APIRouter()

_CONFIG_FOLDER = "zz-pressroom"


@router.get("/api/templates")
async def list_templates(_: str = Depends(check_auth)):
    items = await gh_list(PRESSROOM_REPO, "templates")
    return [i["name"].replace(".md", "") for i in items if i["name"].endswith(".md")]


@router.get("/api/templates/{name}")
async def get_template(name: str, _: str = Depends(check_auth)):
    content = await gh_get_text(PRESSROOM_REPO, f"templates/{name}.md")
    if content is None:
        raise HTTPException(404, f"Template '{name}' not found")
    headers = [
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("#") and not line.startswith("<!--")
    ]
    return {"name": name, "content": content, "headers": headers}


@router.get("/api/licenses")
async def list_licenses(_: str = Depends(check_auth)):
    items = await gh_list(PRESSROOM_REPO, "licenses")
    return [i["name"].replace(".md", "") for i in items if i["name"].endswith(".md")]
