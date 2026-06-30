"""Changelog API — reads and writes the CHANGELOG.md file.

This module provides endpoints for the web frontend to:
  - Read the full changelog markdown (public, no auth required)
  - Append a new version entry (authenticated, admin only)

The changelog is stored as a plain markdown file (``backend/app/CHANGELOG.md``)
with each version separated by ``---``.
"""

import os
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/app", tags=["Changelog"])

# ── File path ──────────────────────────────────────────────────────

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def _read_changelog() -> str:
    """Read the current changelog content."""
    if not CHANGELOG_PATH.exists():
        return "# PDA 更新日志\n"
    return CHANGELOG_PATH.read_text(encoding="utf-8")


def _write_changelog(content: str) -> None:
    """Write the full changelog content to file."""
    CHANGELOG_PATH.write_text(content, encoding="utf-8")


# ── Schemas ────────────────────────────────────────────────────────


class ChangelogEntry(BaseModel):
    version: str
    notes: str
    date: Optional[str] = None


class ChangelogResponse(BaseModel):
    content: str


# ── Endpoints ──────────────────────────────────────────────────────


@router.get("/changelog", response_model=ChangelogResponse)
async def get_changelog():
    """Public endpoint — returns the raw CHANGELOG.md content.

    No authentication required so the PDA download page can display
    the full version history.
    """
    content = _read_changelog()
    return ChangelogResponse(content=content)


@router.post("/changelog", status_code=status.HTTP_201_CREATED)
async def append_changelog(
    entry: ChangelogEntry,
    current_user: User = Depends(get_current_user),
):
    """Append a new version entry to the changelog.

    The new entry is inserted at the top of the file (newest first).
    Requires authentication (admin / logged-in user).
    """
    version_str = entry.version.strip()
    notes_str = entry.notes.strip()

    if not version_str:
        raise HTTPException(status_code=400, detail="版本号不能为空")
    if not notes_str:
        raise HTTPException(status_code=400, detail="更新说明不能为空")

    # Use provided date or today
    entry_date = entry.date or date.today().isoformat()

    # Build the new version block
    new_block_lines = [
        f"## v{version_str} ({entry_date})",
    ]
    for line in notes_str.split("\n"):
        line = line.strip()
        if line:
            # Ensure it starts with "- " for consistency
            if not line.startswith("-"):
                line = f"- {line}"
            new_block_lines.append(line)

    new_block = "\n".join(new_block_lines)

    # Read existing content and prepend the new block
    current = _read_changelog()

    # Find the first "## v" line to insert before it (newest first)
    lines = current.split("\n")
    insert_idx = None
    for i, line in enumerate(lines):
        if line.startswith("## v"):
            insert_idx = i
            break

    if insert_idx is not None:
        # Insert the new block before the first version entry, after the title
        new_lines = lines[:insert_idx] + [new_block, "", "---", ""] + lines[insert_idx:]
    else:
        # No existing versions, just append
        if current.rstrip():
            new_lines = [current.rstrip(), "", "---", "", new_block]
        else:
            new_lines = ["# PDA 更新日志", "", new_block]

    new_content = "\n".join(new_lines)
    _write_changelog(new_content)

    return {"message": "更新日志已追加", "version": version_str}
