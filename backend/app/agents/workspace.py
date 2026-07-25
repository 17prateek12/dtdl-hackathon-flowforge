from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.paths import DEMO_REPO_DIR, ROOT

_current: ContextVar[Optional["RepoWorkspace"]] = ContextVar("repo_workspace", default=None)


def normalize_rel_path(rel_path: str, root: Optional[Path] = None) -> str:
    """Normalize a path to a workspace-relative path.

    LLMs often pass absolute paths like `/Users/.../repo/index.html`. Naively
    stripping the leading slash would nest files under `Users/...` inside the
    workspace. When ``root`` is known, absolute paths under that root (and the
    common "absolute without leading slash" form) are remapped correctly.
    """
    cleaned = (rel_path or "").strip().replace("\\", "/")
    if not cleaned or cleaned == ".":
        return "."

    root_resolved = root.resolve() if root is not None else None

    # Absolute path → relative to workspace root when possible
    candidate = Path(cleaned).expanduser()
    if candidate.is_absolute() and root_resolved is not None:
        try:
            rel = candidate.resolve().relative_to(root_resolved)
            text = str(rel).replace("\\", "/")
            if ".." in text.split("/"):
                raise ValueError("Path traversal is not allowed")
            return text
        except ValueError as exc:
            if "Path traversal" in str(exc):
                raise
            raise ValueError(
                f"Path escapes target codebase sandbox: {cleaned}"
            ) from exc

    cleaned = cleaned.lstrip("/")
    if ".." in cleaned.split("/"):
        raise ValueError("Path traversal is not allowed")

    # Absolute path with leading slash already stripped, e.g.
    # Users/me/project/index.html when root is /Users/me/project
    if root_resolved is not None:
        root_noslash = str(root_resolved).replace("\\", "/").lstrip("/")
        if cleaned == root_noslash:
            return "."
        prefix = root_noslash + "/"
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]

    return cleaned or "."


def parse_target_files(raw: Optional[str | list[str]]) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        lines = raw
    else:
        lines = raw.replace(",", "\n").splitlines()
    out: list[str] = []
    for line in lines:
        text = normalize_rel_path(line)
        if text and text != ".":
            out.append(text)
    return out


@dataclass
class RepoWorkspace:
    root: Path
    main_target_file: Optional[str] = None

    @classmethod
    def default(cls) -> "RepoWorkspace":
        return cls(root=DEMO_REPO_DIR.resolve(), main_target_file="src/app.js")

    @classmethod
    def create(
        cls,
        target_repo: Optional[str] = None,
        main_target_file: Optional[str] = None,
        target_files: Optional[str | list[str]] = None,
    ) -> "RepoWorkspace":
        if not target_repo or not str(target_repo).strip():
            root = DEMO_REPO_DIR.resolve()
        else:
            p = Path(str(target_repo).strip()).expanduser()
            if not p.is_absolute():
                p = (ROOT / p).resolve()
            else:
                p = p.resolve()
            if not p.is_dir():
                raise ValueError(f"Target codebase not found: {p}")
            root = p

        main = main_target_file or ""
        if not main and target_files:
            parsed = parse_target_files(target_files)
            main = parsed[0] if parsed else ""
        main_norm = normalize_rel_path(main, root=root) if main else None
        if main_norm == ".":
            main_norm = None
        return cls(root=root, main_target_file=main_norm)

    def to_rel(self, rel_path: str) -> str:
        return normalize_rel_path(rel_path or ".", root=self.root)

    def resolve(self, rel_path: str) -> Path:
        cleaned = self.to_rel(rel_path)
        full = (self.root / cleaned).resolve()
        root = self.root.resolve()
        if full != root and not str(full).startswith(str(root) + "/"):
            raise ValueError("Path escapes target codebase sandbox")
        return full

    def extra_files_changed(self, changed_paths: list[str]) -> list[str]:
        if not self.main_target_file:
            return []
        main = self.to_rel(self.main_target_file)
        extra: list[str] = []
        for path in changed_paths:
            norm = self.to_rel(path)
            if norm != main:
                extra.append(norm)
        return extra


def bind_workspace(workspace: RepoWorkspace) -> None:
    _current.set(workspace)


def get_workspace() -> RepoWorkspace:
    ws = _current.get()
    return ws if ws is not None else RepoWorkspace.default()


def clear_workspace() -> None:
    _current.set(None)
