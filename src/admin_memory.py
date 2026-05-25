from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil
import os
from typing import Optional, Dict

router = APIRouter(prefix="/admin", tags=["admin"])

ROOT_MEM = Path(__file__).resolve().parent.parent / "memories"


class MemoryResetRequest(BaseModel):
    scope: str  # one of 'session', 'user', 'repo', 'all'
    identifier: Optional[str] = None  # optional id within scope (e.g., thread id)


def _scope_path(scope: str) -> Path:
    if scope == "all":
        return ROOT_MEM
    return ROOT_MEM / scope


def _safe_delete_path(path: Path) -> int:
    """Delete files under path. Returns number of files removed."""
    if not path.exists():
        return 0
    removed = 0
    if path.is_file():
        path.unlink()
        return 1

    for p in path.iterdir():
        if p.is_file():
            p.unlink()
            removed += 1
        elif p.is_dir():
            shutil.rmtree(p)
            removed += 1
    return removed


@router.post("/memory/reset")
def reset_memory(req: MemoryResetRequest) -> Dict[str, int]:
    scope = req.scope.lower()
    if scope not in ("session", "user", "repo", "all"):
        raise HTTPException(status_code=400, detail="Invalid scope")

    root = _scope_path(scope)
    if req.identifier:
        # delete matching files or subfolders that contain the identifier
        count = 0
        if not root.exists():
            return {"removed": 0}
        for p in root.rglob(f"*{req.identifier}*"):
            try:
                if p.is_file():
                    p.unlink()
                    count += 1
                else:
                    shutil.rmtree(p)
                    count += 1
            except Exception:
                continue
        return {"removed": count}

    removed = _safe_delete_path(root)
    return {"removed": removed}


@router.get("/memory/list")
def list_memory() -> Dict[str, int]:
    result = {}
    for scope in ("session", "user", "repo"):
        p = ROOT_MEM / scope
        if not p.exists():
            result[scope] = 0
            continue
        count = sum(1 for _ in p.rglob("*"))
        result[scope] = count
    return result
