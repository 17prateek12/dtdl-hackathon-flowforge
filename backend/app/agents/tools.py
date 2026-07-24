from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import FileChange
from app.paths import DEMO_REPO_DIR


def _resolve_safe(rel_path: str) -> Path:
    cleaned = rel_path.lstrip("/").replace("\\", "/")
    if ".." in cleaned.split("/"):
        raise ValueError("Path traversal is not allowed")
    full = (DEMO_REPO_DIR / cleaned).resolve()
    if not str(full).startswith(str(DEMO_REPO_DIR.resolve())):
        raise ValueError("Path escapes demo-repo sandbox")
    return full


def list_dir(rel_path: str = ".") -> list[str]:
    full = _resolve_safe(rel_path)
    entries: list[str] = []
    for entry in sorted(full.iterdir()):
        entries.append(f"{entry.name}/" if entry.is_dir() else entry.name)
    return entries


def read_file(rel_path: str) -> str:
    return _resolve_safe(rel_path).read_text(encoding="utf-8")


def write_file(rel_path: str, content: str) -> FileChange:
    full = _resolve_safe(rel_path)
    action: str = "created"
    before = ""
    if full.exists():
        action = "modified"
        before = full.read_text(encoding="utf-8")
    else:
        full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    before_lines = len(before.splitlines()) if before else 0
    after_lines = len(content.splitlines())
    return FileChange(
        path=rel_path,
        action=action,  # type: ignore[arg-type]
        linesAdded=max(0, after_lines - before_lines),
        linesRemoved=max(0, before_lines - after_lines),
    )


def search_repo(query: str, rel_path: str = ".") -> list[str]:
    root = _resolve_safe(rel_path)
    hits: list[str] = []

    def walk(directory: Path, prefix: str) -> None:
        for entry in directory.iterdir():
            if entry.name in {"node_modules", ".git"}:
                continue
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            if entry.is_dir():
                walk(entry, rel)
            else:
                text = entry.read_text(encoding="utf-8", errors="ignore")
                if query in text or query in entry.name:
                    hits.append(rel)

    walk(root, "" if rel_path == "." else rel_path)
    return hits


def run_shell(command: str, timeout_sec: int = 120) -> dict:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(DEMO_REPO_DIR),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return {
            "exitCode": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exitCode": 1,
            "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": f"Command timed out after {timeout_sec}s",
        }


def ensure_demo_git() -> None:
    git_dir = DEMO_REPO_DIR / ".git"
    if git_dir.exists():
        return
    run_shell("git init")
    run_shell('git config user.email "loopforge@local"')
    run_shell('git config user.name "LoopForge"')
    run_shell("git add -A")
    run_shell('git commit -m "baseline: demo API without /health" --allow-empty')


def git_snapshot() -> str:
    ensure_demo_git()
    run_shell("git add -A")
    status = run_shell("git status --porcelain")
    if status["stdout"].strip():
        run_shell('git commit -m "loopforge-baseline" --allow-empty')
    rev = run_shell("git rev-parse HEAD")
    return rev["stdout"].strip()


def git_rollback() -> None:
    ensure_demo_git()
    run_shell("git checkout -- .")
    run_shell("git clean -fd")


def git_diff_stat() -> list[FileChange]:
    ensure_demo_git()
    status = run_shell("git status --porcelain")
    changes: list[FileChange] = []
    for line in status["stdout"].splitlines():
        if not line.strip():
            continue
        code = line[:2].strip()
        file_path = line[3:].strip()
        action = "modified"
        if "A" in code or code == "??":
            action = "created"
        if "D" in code:
            action = "deleted"
        changes.append(FileChange(path=file_path, action=action))  # type: ignore[arg-type]
    return changes
