from __future__ import annotations

import subprocess
from pathlib import Path

from app.models import FileChange
from app.agents.workspace import get_workspace, normalize_rel_path


def _root() -> Path:
    return get_workspace().root


def _resolve_safe(rel_path: str) -> Path:
    return get_workspace().resolve(rel_path)


def list_dir(rel_path: str = ".") -> list[str]:
    full = _resolve_safe(rel_path)
    entries: list[str] = []
    for entry in sorted(full.iterdir()):
        entries.append(f"{entry.name}/" if entry.is_dir() else entry.name)
    return entries


def read_file(rel_path: str) -> str:
    return _resolve_safe(rel_path).read_text(encoding="utf-8")


def write_file(rel_path: str, content: str) -> FileChange:
    ws = get_workspace()
    full = ws.resolve(rel_path)
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
        path=normalize_rel_path(rel_path),
        action=action,  # type: ignore[arg-type]
        linesAdded=max(0, after_lines - before_lines),
        linesRemoved=max(0, before_lines - after_lines),
    )


def search_repo(query: str, rel_path: str = ".") -> list[str]:
    root = _resolve_safe(rel_path)
    hits: list[str] = []

    def walk(directory: Path, prefix: str) -> None:
        for entry in directory.iterdir():
            if entry.name in {"node_modules", ".git", ".venv", "__pycache__"}:
                continue
            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            if entry.is_dir():
                walk(entry, rel)
            else:
                try:
                    text = entry.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if query in text or query in entry.name:
                    hits.append(rel)

    walk(root, "" if rel_path == "." else normalize_rel_path(rel_path))
    return hits


def grep_search(query: str, rel_path: str = ".") -> list[dict[str, Any]]:
    """Grep search repository files for code patterns or keywords with line numbers."""
    root = _resolve_safe(rel_path)
    cmd = f'grep -rnI --exclude-dir={{node_modules,.git,.venv,__pycache__,dist,build}} "{query}" .'
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        matches: list[dict[str, Any]] = []
        if res.stdout:
            for line in res.stdout.splitlines():
                if len(matches) >= 50:
                    break
                parts = line.split(":", 2)
                if len(parts) == 3:
                    fpath = parts[0].lstrip("./")
                    if fpath.startswith("git/") or any(ignored in fpath for ignored in ("node_modules", ".git", ".venv", "__pycache__", "dist", "build")):
                        continue
                    matches.append({
                        "file": fpath,
                        "line": int(parts[1]) if parts[1].isdigit() else 0,
                        "content": parts[2].strip(),
                    })
        return matches
    except Exception as exc:
        return [{"error": str(exc)}]



def run_shell(command: str, timeout_sec: int = 120) -> dict:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(_root()),
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


def ensure_git() -> None:
    git_dir = _root() / ".git"
    if git_dir.exists():
        return
    run_shell("git init")
    run_shell('git config user.email "loopforge@local"')
    run_shell('git config user.name "LoopForge"')
    run_shell("git add -A")
    run_shell('git commit -m "loopforge-baseline" --allow-empty')


def git_snapshot() -> str:
    ensure_git()
    run_shell("git add -A")
    status = run_shell("git status --porcelain")
    if status["stdout"].strip():
        run_shell('git commit -m "loopforge-baseline" --allow-empty')
    rev = run_shell("git rev-parse HEAD")
    return rev["stdout"].strip()


def git_rollback() -> None:
    ensure_git()
    run_shell("git checkout -- .")
    run_shell("git clean -fd")


def git_diff_stat() -> list[FileChange]:
    ensure_git()
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


def revert_files(rel_paths: list[str]) -> None:
    ensure_git()
    for rel in rel_paths:
        status = run_shell(f'git status --porcelain -- "{rel}"')
        line = status["stdout"].strip()
        if not line:
            continue
        code = line[:2]
        if "?" in code or code.strip() == "A":
            run_shell(f'git clean -fd -- "{rel}"')
        else:
            run_shell(f'git checkout -- "{rel}"')


def list_extra_file_changes(changed_paths: list[str]) -> list[str]:
    return get_workspace().extra_files_changed(changed_paths)
