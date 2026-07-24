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
