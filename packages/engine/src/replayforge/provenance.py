"""Source provenance shared by CLI and API reports."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_revision(path: Path) -> str | None:
    """Return the enclosing repository revision, explicitly marking a dirty worktree."""

    try:
        sha = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return f"{sha}-dirty" if dirty else sha
