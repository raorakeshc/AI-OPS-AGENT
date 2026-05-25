from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil
import os
from typing import Optional, Dict
from datetime import datetime
import json

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


@router.get("/feedback/audit")
def get_feedback_audit(since: Optional[str] = None, until: Optional[str] = None, limit: int = 100):
    """Return recent feedback audit entries.

    Query params:
    - since: ISO timestamp (inclusive)
    - until: ISO timestamp (inclusive)
    - limit: max entries to return (most recent first)
    """
    audit_path = Path(__file__).resolve().parent.parent / "data" / "audit" / "feedback_audit.log"
    if not audit_path.exists():
        return {"entries": []}

    entries = []
    try:
        with open(audit_path, "r", encoding="utf-8") as af:
            for line in af:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                ts = obj.get("timestamp")
                if ts:
                    try:
                        ts_dt = datetime.fromisoformat(ts.replace("Z", ""))
                    except Exception:
                        ts_dt = None
                else:
                    ts_dt = None

                entries.append((ts_dt, obj))

        # sort by timestamp desc (None goes last)
        entries.sort(key=lambda x: (x[0] is None, x[0]), reverse=True)

        def _in_range(ts_dt):
            if ts_dt is None:
                return True
            if since:
                try:
                    s_dt = datetime.fromisoformat(since.replace("Z", ""))
                    if ts_dt < s_dt:
                        return False
                except Exception:
                    pass
            if until:
                try:
                    u_dt = datetime.fromisoformat(until.replace("Z", ""))
                    if ts_dt > u_dt:
                        return False
                except Exception:
                    pass
            return True

        filtered = [obj for ts_dt, obj in entries if _in_range(ts_dt)]
        return {"entries": filtered[: max(0, min(limit, len(filtered)))]}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read audit log")
