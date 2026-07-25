from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.agents import tools as repo_tools
from app.agents.workspace import get_workspace


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    command: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass
class SmartValidationPlan:
    command: str
    file_checks: list[str]
    rationale: str


_SKIP_DIR_NAMES = {
    ".git",
    ".flowforge",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "qdrant_db",
}

_FILE_NAME_RE = re.compile(
    r"(?P<name>[A-Za-z0-9_./-]+\.(?:html|css|js|jsx|ts|tsx|py|json|md|txt))",
    re.IGNORECASE,
)


def run_command_node(command: str, timeout_sec: int = 120) -> CommandResult:
    result = repo_tools.run_shell(command, timeout_sec)
    return CommandResult(
        exit_code=result["exitCode"],
        stdout=result["stdout"],
        stderr=result["stderr"],
        command=command,
    )


def _workspace_root() -> Path:
    return get_workspace().root.resolve()


def _iter_workspace_files(max_files: int = 400) -> list[Path]:
    root = _workspace_root()
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        out.append(path)
        if len(out) >= max_files:
            break
    return out


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(_workspace_root())).replace("\\", "/")


def _locate_by_basename(basename: str) -> Optional[str]:
    """Find a file by basename; prefer shallower / root-closer paths."""
    name = basename.strip().replace("\\", "/").lstrip("./")
    if not name:
        return None
    root = _workspace_root()
    direct = root / name
    if direct.is_file():
        return _rel(direct)

    needle = name.rsplit("/", 1)[-1].lower()
    hits: list[Path] = []
    for path in _iter_workspace_files():
        if path.name.lower() == needle:
            hits.append(path)
    if not hits:
        return None
    hits.sort(key=lambda p: (len(p.relative_to(root).parts), str(p).lower()))
    return _rel(hits[0])


def _extract_filenames(*texts: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in _FILE_NAME_RE.finditer(text):
            name = match.group("name").lstrip("./")
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(name)
    return found


def _parse_ls_targets(command: str) -> list[str]:
    parts = command.strip().split()
    if not parts:
        return []
    if parts[0] != "ls":
        return []
    targets: list[str] = []
    for token in parts[1:]:
        if token.startswith("-"):
            continue
        targets.append(token.lstrip("./"))
    return targets


def _has_package_json() -> bool:
    return (_workspace_root() / "package.json").is_file()


def _npm_test_script() -> Optional[str]:
    pkg = _workspace_root() / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    scripts = data.get("scripts") or {}
    if isinstance(scripts, dict) and scripts.get("test"):
        return "npm test"
    return None


def _looks_html_css_case(
    *,
    objective: str,
    files_changed: list[str],
    candidates: list[str],
) -> bool:
    blob = " ".join([objective, *files_changed, *candidates]).lower()
    htmlish = any(x in blob for x in (".html", "html", "css", "styles.css", "shopping"))
    has_node_tests = _npm_test_script() is not None
    if htmlish and not has_node_tests:
        return True
    if htmlish and any(x.endswith((".html", ".css")) for x in candidates + files_changed):
        # Prefer file checks over npm when the work product is clearly static pages
        if "npm" in objective.lower() and "no js" not in objective.lower():
            return False
        if "only html" in objective.lower() or "only css" in objective.lower():
            return True
        if any(x.endswith((".html", ".css")) for x in files_changed):
            return True
    return False


def _existence_command(paths: list[str]) -> str:
    if not paths:
        return "true"
    checks = " && ".join(f'test -f "{p}"' for p in paths)
    listing = " && ".join(f'echo "OK {p}"' for p in paths)
    return f"{checks} && {listing}"


def resolve_smart_validation(
    *,
    validate_command: Optional[str] = None,
    objective: str = "",
    main_target_file: Optional[str] = None,
    files_changed: Optional[list] = None,
    file_checks: Optional[list[str]] = None,
    criteria: Optional[list[str]] = None,
) -> SmartValidationPlan:
    """
    Infer a sensible validate command + file checks from the workspace,
    objective, and files changed. User-provided commands are honored when
    possible, but brittle `ls a b` checks are rewritten to real paths.
    """
    changed_paths: list[str] = []
    for item in files_changed or []:
        if hasattr(item, "path"):
            path = str(getattr(item, "path") or "")
        elif isinstance(item, dict):
            path = str(item.get("path") or "")
        else:
            path = str(item)
        path = path.replace("\\", "/").lstrip("./")
        if not path or path.startswith(".flowforge/") or "/.flowforge/" in path:
            continue
        if path.startswith("Users/") and "Desktop" in path:
            # stray absolute-without-slash artifact; skip
            continue
        changed_paths.append(path)

    criteria_text = "\n".join(criteria or [])
    user_cmd = (validate_command or "").strip()
    mentioned = _extract_filenames(
        user_cmd,
        objective,
        criteria_text,
        " ".join(changed_paths),
        main_target_file or "",
        " ".join(file_checks or []),
    )

    # Seed expected basenames
    expected: list[str] = []
    for name in [
        *(file_checks or []),
        *(_parse_ls_targets(user_cmd) if user_cmd.startswith("ls ") else []),
        *mentioned,
        *(( [main_target_file] if main_target_file else [])),
        *changed_paths,
    ]:
        clean = (name or "").replace("\\", "/").lstrip("./")
        if not clean or clean in expected:
            continue
        if clean.startswith(".flowforge"):
            continue
        expected.append(clean)

    resolved_checks: list[str] = []
    missing: list[str] = []
    for name in expected:
        located = _locate_by_basename(name)
        if located:
            if located not in resolved_checks:
                resolved_checks.append(located)
        else:
            # keep exact relative path if it looks intentional and exists later check
            if "/" in name and (_workspace_root() / name).is_file():
                if name not in resolved_checks:
                    resolved_checks.append(name)
            else:
                missing.append(name)

    html_case = _looks_html_css_case(
        objective=objective,
        files_changed=changed_paths,
        candidates=expected,
    )
    npm_cmd = _npm_test_script()
    rationale_parts: list[str] = []

    # Prefer smart file-existence for static HTML/CSS work
    if html_case:
        # Ensure common shopping artifacts if mentioned
        blob = (objective + " " + criteria_text).lower()
        for basename in ("index.html", "styles.css", "style.css"):
            if basename in blob:
                located = _locate_by_basename(basename)
                if located and located not in resolved_checks:
                    resolved_checks.append(located)
        if not resolved_checks and main_target_file:
            located = _locate_by_basename(main_target_file)
            if located:
                resolved_checks.append(located)
        command = _existence_command(resolved_checks)
        rationale_parts.append(
            "Detected HTML/CSS-style task; verifying output files exist "
            f"({', '.join(resolved_checks) or 'none found'})."
        )
        if user_cmd and user_cmd != command:
            rationale_parts.append(f"Rewrote validate command from `{user_cmd}`.")
        return SmartValidationPlan(
            command=command,
            file_checks=resolved_checks,
            rationale=" ".join(rationale_parts),
        )

    # User gave an ls-style check → rewrite to real paths
    if user_cmd.startswith("ls "):
        command = _existence_command(resolved_checks) if resolved_checks else user_cmd
        rationale_parts.append(
            f"Interpreted `{user_cmd}` as file checks → "
            f"{', '.join(resolved_checks) or 'no matching files yet'}."
        )
        return SmartValidationPlan(
            command=command,
            file_checks=resolved_checks
            or ([main_target_file] if main_target_file else []),
            rationale=" ".join(rationale_parts),
        )

    # Explicit non-ls user command (e.g. npm test)
    if user_cmd and user_cmd.lower() not in {"auto", "smart", "default"}:
        checks = resolved_checks or (
            [main_target_file] if main_target_file else []
        )
        # Drop stale defaults like src/app.js when file is absent and task isn't JS
        checks = [
            c
            for c in checks
            if _locate_by_basename(c) is not None
            or (_workspace_root() / c).is_file()
        ]
        if main_target_file:
            located = _locate_by_basename(main_target_file)
            if located and located not in checks:
                checks.append(located)
        rationale_parts.append(f"Using user validate command `{user_cmd}`.")
        return SmartValidationPlan(
            command=user_cmd,
            file_checks=checks,
            rationale=" ".join(rationale_parts),
        )

    # Auto mode
    if npm_cmd:
        checks: list[str] = []
        if main_target_file:
            located = _locate_by_basename(main_target_file)
            if located:
                checks.append(located)
        rationale_parts.append("Found package.json test script; using `npm test`.")
        return SmartValidationPlan(
            command=npm_cmd,
            file_checks=checks,
            rationale=" ".join(rationale_parts),
        )

    if (_workspace_root() / "pytest.ini").is_file() or any(
        p.name.startswith("test_") and p.suffix == ".py" for p in _iter_workspace_files(80)
    ):
        return SmartValidationPlan(
            command="python -m pytest -q",
            file_checks=resolved_checks,
            rationale="Detected Python tests; using pytest.",
        )

    if resolved_checks:
        return SmartValidationPlan(
            command=_existence_command(resolved_checks),
            file_checks=resolved_checks,
            rationale="No test runner found; verifying changed/required files exist.",
        )

    if main_target_file:
        located = _locate_by_basename(main_target_file) or main_target_file
        return SmartValidationPlan(
            command=_existence_command([located]),
            file_checks=[located],
            rationale=f"Fallback: verify main target `{located}` exists.",
        )

    return SmartValidationPlan(
        command="true",
        file_checks=[],
        rationale="No validate signals found; no-op command.",
    )


def deterministic_validate(
    *,
    command_result: CommandResult,
    file_checks: Optional[list[str]] = None,
) -> dict:
    file_check_results: list[dict] = []
    for rel in file_checks or []:
        located = _locate_by_basename(rel) if rel else None
        path = located or rel
        try:
            if located or (_workspace_root() / rel).is_file():
                # Prefer read via tools when under workspace
                try:
                    repo_tools.read_file(path)
                    file_check_results.append(
                        {"path": path, "exists": True, "requested": rel}
                    )
                except Exception:  # noqa: BLE001
                    exists = (_workspace_root() / path).is_file()
                    file_check_results.append(
                        {"path": path, "exists": exists, "requested": rel}
                    )
            else:
                file_check_results.append(
                    {"path": rel, "exists": False, "requested": rel}
                )
        except Exception:  # noqa: BLE001
            file_check_results.append(
                {"path": rel, "exists": False, "requested": rel}
            )

    files_ok = all(f["exists"] for f in file_check_results) if file_check_results else True
    command_passed = command_result.passed
    passed = command_passed and files_ok

    evidence_parts = [
        f"Command: {command_result.command}",
        f"Exit code: {command_result.exit_code} ({'PASS' if command_passed else 'FAIL'})",
        f"stdout:\n{command_result.stdout[:2000]}"
        if command_result.stdout
        else "stdout: (empty)",
        f"stderr:\n{command_result.stderr[:2000]}"
        if command_result.stderr
        else "stderr: (empty)",
        *[
            f"File check {f.get('requested') or f['path']}"
            + (f" → {f['path']}" if f.get("requested") and f.get("requested") != f["path"] else "")
            + f": {'exists' if f['exists'] else 'MISSING'}"
            for f in file_check_results
        ],
        f"Deterministic verdict: {'PASS' if passed else 'FAIL'}",
    ]
    return {
        "passed": passed,
        "evidence": "\n".join(evidence_parts),
        "commandPassed": command_passed,
        "fileCheckResults": file_check_results,
    }


def _parse_test_run_summary(stdout: str) -> str:
    passed = failed = total = None
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("# pass "):
            passed = stripped.split()[-1]
        elif stripped.startswith("# fail "):
            failed = stripped.split()[-1]
        elif stripped.startswith("# tests "):
            total = stripped.split()[-1]
        elif "OK " in stripped and stripped.startswith("OK "):
            return "required files present"
    if passed is not None and failed is not None:
        if total is not None:
            return f"{passed}/{total} tests passed, {failed} failed"
        return f"{passed} passed, {failed} failed"
    if not stdout.strip():
        return "no output"
    return stdout.strip().splitlines()[0][:80]


def _extract_subtest_lines(stdout: str, limit: int = 6) -> list[str]:
    seen: set[str] = set()
    hits: list[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        name: str | None = None
        if stripped.startswith("# Subtest:"):
            name = stripped.replace("# Subtest:", "", 1).strip()
        elif stripped.startswith("ok ") and " - " in stripped:
            name = stripped.split(" - ", 1)[1].strip()
        elif stripped.startswith("OK "):
            name = stripped
        if name and name not in seen:
            seen.add(name)
            hits.append(name)
        if len(hits) >= limit:
            break
    return hits


def format_validation_report(
    *,
    test_generation: dict,
    command_result: CommandResult,
    validation: dict,
    summary: str,
    files_changed: list | None = None,
    smart_plan: SmartValidationPlan | None = None,
) -> str:
    passed = validation["passed"]
    verdict = "PASS" if passed else "FAIL"
    test_cases = test_generation.get("testCases") or []
    test_files = test_generation.get("testFiles") or []

    lines = [
        f"=== VALIDATION {verdict} ===",
        "",
        "How code was checked:",
        "  1. Smart validator inferred the right checks for this task",
        "  2. Validation Agent prepared tests for the success criteria",
        "  3. Checks ran via shell command + required files on disk",
        "",
    ]

    if smart_plan:
        lines.extend(
            [
                "--- Smart validate plan ---",
                smart_plan.rationale,
                f"Command: {smart_plan.command}",
                f"Files: {', '.join(smart_plan.file_checks) or '(none)'}",
                "",
            ]
        )

    lines.extend(
        [
            "--- Test generation ---",
            test_generation.get("summary", "Tests prepared"),
        ]
    )

    if test_files:
        lines.append(f"Test file: {', '.join(test_files)}")

    transcript = test_generation.get("transcript") or []
    for step in transcript[:4]:
        lines.append(f"  → {step}")

    if test_cases:
        lines.append("")
        lines.append("Test cases:")
        for name in test_cases:
            lines.append(f"  • {name}")

    lines.extend([
        "",
        "--- Test run ---",
        f"Command: {command_result.command}",
        f"Exit code: {command_result.exit_code} ({'PASS' if command_result.passed else 'FAIL'})",
        f"Summary: {_parse_test_run_summary(command_result.stdout)}",
    ])

    highlights = _extract_subtest_lines(command_result.stdout)
    if highlights:
        lines.append("Results:")
        for name in highlights:
            lines.append(f"  ✓ {name}")

    file_results = validation.get("fileCheckResults") or []
    if file_results:
        lines.append("")
        lines.append("--- File checks ---")
        for f in file_results:
            status = "exists" if f["exists"] else "MISSING"
            label = f["path"]
            requested = f.get("requested")
            if requested and requested != label:
                label = f"{requested} → {label}"
            lines.append(f"  • {label}: {status}")

    lines.extend([
        "",
        "--- Summary ---",
        summary.strip() or f"Validation {verdict.lower()} — all checks complete.",
        "",
        f"Overall verdict: {verdict}",
    ])
    return "\n".join(lines)
