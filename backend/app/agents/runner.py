from __future__ import annotations

import json
from typing import Any, Optional

from app.agents import tools as repo_tools
from app.agents.llm import chat_text, chat_with_tools, use_mock
from app.models import FileChange

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files in a directory under demo-repo",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file under demo-repo",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file under demo-repo",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search demo-repo for a string",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Grep search repository files for code patterns, function names, endpoints, or keywords with line numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword or pattern to grep for"},
                    "path": {"type": "string", "description": "Directory path to search in (default .)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a shell command inside demo-repo",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
]


def _scope_note(
    main_target_file: Optional[str] = None,
    target_repo: Optional[str] = None,
) -> str:
    parts: list[str] = []
    if target_repo:
        parts.append(f"Target codebase: {target_repo}")
    if main_target_file:
        parts.append(
            f"Primary file to modify: {main_target_file}. "
            "You may change other files if needed (e.g. tests or imports), but "
            "changes outside the primary file require human approval before the run continues."
        )
    return "\n".join(parts)


from app.agents import langchain_agents
from app.agents import tools as repo_tools
from app.agents.llm import chat_text, chat_with_tools, use_mock
from app.models import FileChange


def generate_success_criteria(
    *,
    objective: str,
    constraints: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    main_target_file: Optional[str] = None,
    target_repo: Optional[str] = None,
) -> dict[str, Any]:
    if use_mock():
        criteria = [
            f"Fulfill primary objective: {objective}",
            f"Adhere strictly to constraints: {constraints}" if constraints else "Maintain codebase patterns and pass tests",
            "Ensure implementation is fully verified and tests pass with exit code 0",
        ]
        raw = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))
        return {"criteria": criteria, "raw": raw}

    scope_note = _scope_note(main_target_file, target_repo)
    return langchain_agents.run_langchain_success_criteria(
        objective=objective,
        constraints=constraints,
        instructions=instructions,
        model=model,
        scope_note=scope_note,
    )



def generate_plan(
    *,
    objective: str,
    constraints: str,
    criteria: list[str],
    feedback: Optional[str] = None,
    coding_feedback: Optional[str] = None,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    main_target_file: Optional[str] = None,
    target_repo: Optional[str] = None,
) -> dict[str, Any]:
    listing = ", ".join(repo_tools.list_dir("."))
    sample_path = main_target_file or "package.json"
    try:
        sample_src = repo_tools.read_file(sample_path)
    except Exception:  # noqa: BLE001
        sample_src = "(file not readable)"

    if use_mock():
        crit_lines = "\n".join(f"  - {c}" for c in criteria) if criteria else "  - Fulfill primary objective and pass all validation checks."
        target_str = main_target_file or "codebase"
        steps = [
            f"Inspect repository structure in {target_repo or '.'} and analyze target file ({target_str})",
            "Implement solution logic for each approved success criterion",
            "Verify implementation against all approved success criteria",
        ]
        if feedback:
            steps.insert(0, f"Address failure feedback: {feedback[:200]}")
        if coding_feedback:
            steps.insert(0, f"Address coding agent feedback: {coding_feedback[:200]}")
            
        plan_blocks = [
            f"# Architectural Implementation Plan",
            f"**Target Workspace**: `{target_repo or '.'}`",
            f"**Target Files**: `{target_str}`",
            "",
            "## 1. Approved Success Criteria",
            crit_lines,
            "",
        ]
        if coding_feedback:
            plan_blocks.extend([
                "## Previous Coding Agent Attempts",
                coding_feedback,
                "",
            ])
        plan_blocks.extend([
            "## 2. Step-by-Step Execution Sequence",
            "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)),
            "",
            "## 3. Verification & Testing Strategy",
            "- Execute automated test commands to confirm expected outcomes.",
            "- Validate that all modified files adhere to project specifications.",
        ])
        plan = "\n".join(plan_blocks)
        return {"plan": plan, "steps": steps, "raw": plan}

    return langchain_agents.run_langchain_planning(
        objective=objective,
        constraints=constraints,
        criteria=criteria,
        feedback=feedback,
        coding_feedback=coding_feedback,
        instructions=instructions,
        model=model,
        repo_listing=listing,
        sample_path=sample_path,
        sample_src=sample_src,
        scope_note=_scope_note(main_target_file, target_repo),
    )


def execute_changes(
    *,
    objective: str,
    plan: str,
    criteria: list[str],
    feedback: Optional[str] = None,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    force_fail: bool = False,
    main_target_file: Optional[str] = None,
    target_repo: Optional[str] = None,
) -> dict[str, Any]:
    if use_mock():
        target = main_target_file or "codebase"
        transcript = [
            f"Analyzing codebase structure in {target_repo or '.'}",
            f"Inspecting code context for objective: {objective[:100]}",
        ]
        if force_fail:
            transcript.append(
                "Skipping file modification (forced failure state)."
            )
            return {
                "summary": "No file changes made (forced fail for demo loop).",
                "filesChanged": [],
                "transcript": transcript,
            }
        transcript.append(f"Successfully applied changes for objective: {objective[:100]}")
        return {
            "summary": f"Executed changes for objective: {objective[:100]}",
            "filesChanged": [],
            "transcript": transcript,
        }

    files_changed: list[FileChange] = []

    def execute_tool(name: str, args: dict[str, Any]) -> str:
        if name == "list_dir":
            return json.dumps(repo_tools.list_dir(args.get("path") or "."))
        if name == "read_file":
            return repo_tools.read_file(args["path"])
        if name == "write_file":
            change = repo_tools.write_file(args["path"], args["content"])
            files_changed.append(change)
            return change.model_dump_json()
        if name == "search":
            return json.dumps(repo_tools.search_repo(args["query"]))
        if name == "grep_search":
            return json.dumps(repo_tools.grep_search(args["query"], args.get("path") or "."))
        if name == "run_shell":
            return json.dumps(repo_tools.run_shell(args["command"]))
        return f"Unknown tool {name}"

    res = langchain_agents.run_langchain_execution(
        objective=objective,
        plan=plan,
        criteria=criteria,
        feedback=feedback,
        instructions=instructions,
        model=model,
        execute_tool_func=execute_tool,
        tools_defs=TOOL_DEFS,
        scope_note=_scope_note(main_target_file, target_repo),
    )
    res["filesChanged"] = files_changed
    return res


def summarize_validation(
    *,
    passed: bool,
    evidence: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    if use_mock():
        prefix = "Validation PASSED." if passed else "Validation FAILED."
        return f"{prefix}\n{evidence}"

    return langchain_agents.run_langchain_validation(
        passed=passed,
        evidence=evidence,
        instructions=instructions,
        model=model,
    )

