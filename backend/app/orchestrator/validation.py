from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.agents import tools as repo_tools


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    command: str

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


def run_command_node(command: str, timeout_sec: int = 120) -> CommandResult:
    result = repo_tools.run_shell(command, timeout_sec)
    return CommandResult(
        exit_code=result["exitCode"],
        stdout=result["stdout"],
        stderr=result["stderr"],
        command=command,
    )


def deterministic_validate(
    *,
    command_result: CommandResult,
    file_checks: Optional[list[str]] = None,
) -> dict:
    file_check_results: list[dict] = []
    for rel in file_checks or []:
        try:
            repo_tools.read_file(rel)
            file_check_results.append({"path": rel, "exists": True})
        except Exception:  # noqa: BLE001
            file_check_results.append({"path": rel, "exists": False})

    files_ok = all(f["exists"] for f in file_check_results)
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
            f"File check {f['path']}: {'exists' if f['exists'] else 'MISSING'}"
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
) -> str:
    passed = validation["passed"]
    verdict = "PASS" if passed else "FAIL"
    test_cases = test_generation.get("testCases") or []
    test_files = test_generation.get("testFiles") or []

    lines = [
        f"=== VALIDATION {verdict} ===",
        "",
        "How code was checked:",
        "  1. Validation Agent prepared tests for the success criteria",
        "  2. Test suite ran via shell command",
        "  3. Required source files were verified on disk",
        "",
        "--- Test generation ---",
        test_generation.get("summary", "Tests prepared"),
    ]

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
            lines.append(f"  • {f['path']}: {status}")

    lines.extend([
        "",
        "--- Summary ---",
        summary.strip() or f"Validation {verdict.lower()} — all checks complete.",
        "",
        f"Overall verdict: {verdict}",
    ])
    return "\n".join(lines)
