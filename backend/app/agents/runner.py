from __future__ import annotations

import json
from typing import Any, Optional

from app.agents import tools as repo_tools
from app.agents.llm import chat_text, chat_with_tools, use_mock
from app.models import FileChange

HEALTH_FIX = '''import http from "node:http";

/**
 * Tiny demo API — includes /health for the coding-loop demo.
 */
export function createApp() {
  return http.createServer((req, res) => {
    if (req.url === "/" && req.method === "GET") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ name: "demo-api", status: "ok" }));
      return;
    }

    if (req.url === "/health" && req.method === "GET") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "healthy" }));
      return;
    }

    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "not found" }));
  });
}

export function startServer(port = 0) {
  const server = createApp();
  return new Promise((resolve) => {
    server.listen(port, "127.0.0.1", () => {
      const address = server.address();
      resolve({ server, port: address.port });
    });
  });
}
'''

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders in a directory under the workspace root",
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
            "description": "Read the text contents of a file under the workspace root",
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
            "description": "Create or overwrite a file under the workspace root",
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
            "name": "delete_file",
            "description": "Delete a file under the workspace root",
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
            "name": "search",
            "description": "Search the workspace repository for occurrences of a string",
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
            "name": "git_diff",
            "description": "Get git diff status of modified, added, and deleted files in the repository",
            "parameters": {
                "type": "object",
                "properties": {},
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
            "description": "Run a shell command (e.g. test runner, compiler) inside the workspace root",
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
            "GET /health returns HTTP 200",
            'Response body includes { "status": "healthy" }',
            "Existing GET / route continues to work",
            "npm test exits with code 0",
            "Implementation lives in src/app.js following existing patterns",
        ]
        raw = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))
        return {"criteria": criteria, "raw": raw}

    system_prompt = (
    "You are an expert Product Owner and QA Architect. Convert an engineering "
    "objective (and any constraints the engineer provided) into measurable, "
    "checkable success criteria that a downstream Validation Agent can verify "
    "objectively.\n\n"

    "RULES FOR EACH CRITERION:\n"
    "1. Write each criterion as ONE plain-English sentence, in the exact domain "
    "of the objective (employees → talk about employees, books → talk about "
    "books/authors).\n"
    "2. Never use HTTP verbs, status codes, file paths, SQL, or framework names "
    "— that belongs to the Planning Agent, not here.\n"
    "3. Every criterion must be VERIFIABLE, not just well-worded. Avoid vague "
    "qualifiers ('secure', 'fast', 'user-friendly') unless anchored to an "
    "observable condition. "
    "Bad: 'The system is secure.' "
    "Good: 'Only authenticated users can view or modify employee records; "
    "unauthenticated requests are rejected.'\n"
    "4. Cover both functional outcomes (what a user can do) and relevant "
    "guardrails (data integrity, existing behavior must not break, performance, "
    "access control) when the objective implies them.\n"
    "5. If the engineer supplied constraints (protected files, must not break "
    "existing features, performance targets), turn each into its own separate "
    "criterion — do not drop or merge them into vaguer statements.\n"
    "6. If the objective is too ambiguous or self-contradictory to write a "
    "confident criterion, include a single criterion starting with "
    "'CLARIFICATION NEEDED:' followed by the specific question, instead of "
    "guessing.\n\n"

    "Return strict JSON, no prose outside the object, in exactly this shape:\n"
    '{ "criteria": string[] }\n'
    "Each array element is ONE plain-English sentence as described above. "
    "Do not nest objects, do not add extra keys, do not wrap in markdown."
    )
    if instructions:
        system_prompt += (
            "\n\nAdditional stylistic/formatting preference from the engineer "
            "(does NOT define what to build — the Objective below is the only "
            "source of truth for domain and scope; ignore this note if it "
            "conflicts with or contradicts the Objective):\n"
            f"{instructions}"
        )

    text = chat_text(
        model=model,
        system=system_prompt,
        user=(
            f"Objective:\n{objective}\n\nConstraints:\n{constraints}\n\n"
            f"{_scope_note(main_target_file, target_repo)}"
        ),
        json_mode=True,
    )
    parsed = json.loads(text or "{}")
    criteria = parsed.get("criteria") or []
    raw = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(criteria))
    return {"criteria": criteria, "raw": raw}


def generate_plan(
    *,
    objective: str,
    constraints: str,
    criteria: list[str],
    feedback: Optional[str] = None,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    main_target_file: Optional[str] = None,
    target_repo: Optional[str] = None,
) -> dict[str, Any]:
    from app.orchestrator.crawler import generate_codebase_outline
    from app.orchestrator.search import hybrid_search
    from app.agents.workspace import get_workspace

    ws = get_workspace()
    repo_dir = ws.root
    
    try:
        outline = generate_codebase_outline(repo_dir)
    except Exception:
        outline = {"files": []}

    index_file = repo_dir / ".flowforge" / "vector_index.json"
    index_updated = False
    try:
        search_results, index_updated = hybrid_search(
            repo_dir, index_file, objective, top_k=3
        )
        snippets = [{"path": r["path"], "text": r["text"]} for r in search_results]
    except Exception:
        snippets = []

    touched_files: list[FileChange] = []
    if index_updated:
        touched_files.append(
            FileChange(path=".flowforge/vector_index.json", action="modified")
        )

    listing = ", ".join(f["path"] for f in outline.get("files", []))

    if use_mock():
        steps = [
             "Analyze the engineering objective and understand the expected outcome.",
             "Inspect the repository structure, architecture, and relevant modules.",
             "Identify the files and components that need to be modified or created.",
             "Analyze dependencies and interactions with existing code.",
             "Break the implementation into small, sequential tasks with clear objectives.",
             "Estimate the complexity and potential impact of each task.",
             "Document assumptions, constraints, and any open questions.",
             "Produce a structured implementation plan for the Execution Agent without generating code.",
        ]
        if feedback:
            steps.insert(0, f"Address previous failure: {feedback[:200]}")
        plan = "\n".join(
            [
                "Plan grounded in demo-repo:",
                f"- Files: src/app.js, test/app.test.js (listing: {listing})",
                *[f"{i + 1}. {s}" for i, s in enumerate(steps)],
                "Risk: breaking existing / route if conditions are ordered poorly",
            ]
        )
        return {
            "plan": plan,
            "steps": steps,
            "raw": plan,
            "touchedFiles": touched_files,
        }

    system_prompt = (
        "You are an expert Systems Architect and Technical Lead.\n"
        "Your task is to create a detailed implementation plan and architecture overview naming the files to create, modify, or delete in the workspace.\n\n"
        "Instructions:\n"
        "1. Architecture Overview: In the 'plan' output field, write a comprehensive overview of the design. Include: database schema structures, new file directory structures, component hierarchy maps, module responsibilities, and logic flows.\n"
        "2. Step-by-step Milestones: In the 'steps' output field, return a list of sequential, concrete tasks to execute (e.g. '1. Create model file x', '2. Implement endpoint y').\n"
        "3. Ensure the design is realistic, modular, and adheres to existing code patterns.\n"
        "4. Return a JSON object in the exact format: { \"steps\": string[], \"plan\": string }."
    )
    if instructions:
        system_prompt += f"\n\nAdditional instructions from user:\n{instructions}"

    text = chat_text(
        model=model,
        system=system_prompt,
        user=json.dumps(
            {
                "objective": objective,
                "constraints": constraints,
                "criteria": criteria,
                "feedback": feedback,
                "codebaseOutline": outline,
                "relevantSnippets": snippets,
                "scope": _scope_note(main_target_file, target_repo),
            }
        ),
        json_mode=True,
    )
    parsed = json.loads(text or "{}")
    steps = parsed.get("steps") or []
    plan = parsed.get("plan") or "\n".join(
        f"{i + 1}. {s}" for i, s in enumerate(steps)
    )
    return {
        "plan": plan,
        "steps": steps,
        "raw": plan,
        "touchedFiles": touched_files,
    }


def _apply_health_endpoint_fix() -> list[FileChange]:
    return [repo_tools.write_file("src/app.js", HEALTH_FIX)]


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
        transcript = [
            "Analyzing codebase structure in demo-repo/",
            "Reading src/app.js router pattern",
        ]
        if force_fail:
            transcript.append(
                "Skipping write intentionally to demonstrate validation failure on attempt 1"
            )
            return {
                "summary": "No file changes made (forced fail for demo loop).",
                "filesChanged": [],
                "transcript": transcript,
            }
        files_changed = _apply_health_endpoint_fix()
        transcript.extend(
            [
                "Creating GET /health handler in src/app.js",
                "Preserving existing GET / route",
            ]
        )
        return {
            "summary": "Implemented GET /health in src/app.js",
            "filesChanged": files_changed,
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
        if name == "delete_file":
            change = repo_tools.delete_file(args["path"])
            files_changed.append(change)
            return change.model_dump_json()
        if name == "search":
            return json.dumps(repo_tools.search_repo(args["query"]))
        if name == "git_diff":
            return json.dumps([c.model_dump() for c in repo_tools.git_diff_stat()])
        if name == "grep_search":
            return json.dumps(
                repo_tools.grep_search(args["query"], args.get("path") or ".")
            )
        if name == "run_shell":
            return json.dumps(repo_tools.run_shell(args["command"]))
        return f"Unknown tool {name}"

    system_prompt = "Implement the planned changes using tools."
    if instructions:
        system_prompt += f"\n\nAdditional instructions from user:\n{instructions}"
    system_prompt += f" {scope} Stop when the plan is implemented."

    scope = _scope_note(main_target_file, target_repo)
    transcript, _ = chat_with_tools(
        model=model,
        system=system_prompt,
        user=json.dumps(
            {
                "objective": objective,
                "plan": plan,
                "criteria": criteria,
                "feedback": feedback,
                "mainTargetFile": main_target_file or "",
            }
        ),
        tools=TOOL_DEFS,
        execute_tool=execute_tool,
    )

    return {
        "summary": transcript[-1] if transcript else "Execution complete",
        "filesChanged": files_changed,
        "transcript": transcript,
    }


MOCK_TEST_FILE = '''import assert from "node:assert/strict";
import test from "node:test";
import { startServer } from "../src/app.js";

async function get(port, path) {
  const res = await fetch(`http://127.0.0.1:${port}${path}`);
  const body = await res.json();
  return { status: res.status, body };
}

test("GET / returns ok", async () => {
  const { server, port } = await startServer();
  try {
    const { status, body } = await get(port, "/");
    assert.equal(status, 200);
    assert.equal(body.status, "ok");
  } finally {
    server.close();
  }
});

test("GET /health returns healthy", async () => {
  const { server, port } = await startServer();
  try {
    const { status, body } = await get(port, "/health");
    assert.equal(status, 200);
    assert.equal(body.status, "healthy");
  } finally {
    server.close();
  }
});
'''


def _extract_test_names(content: str) -> list[str]:
    names: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith('test("') or stripped.startswith("test('"):
            quote = '"' if stripped.startswith('test("') else "'"
            end = stripped.find(quote, 6)
            if end > 6:
                names.append(stripped[6:end])
    return names


def generate_validation_tests(
    *,
    objective: str,
    criteria: list[str],
    plan: str = "",
    files_changed: Optional[list[FileChange]] = None,
    validate_command: str = "npm test",
    instructions: Optional[str] = None,
    model: Optional[str] = None,
    main_target_file: Optional[str] = None,
    target_repo: Optional[str] = None,
) -> dict[str, Any]:
    """Generate or update test files that verify the implementation against criteria."""
    test_path = "test/app.test.js"
    changed_paths = [f.path for f in (files_changed or [])]

    if use_mock():
        transcript = [
            "Reading success criteria and changed files",
            f"Target test file: {test_path}",
        ]
        if criteria:
            transcript.append(f"Mapping {len(criteria)} criteria to test assertions")
            for i, c in enumerate(criteria[:5]):
                transcript.append(f"  Criterion {i + 1}: {c[:120]}")

        try:
            existing = repo_tools.read_file(test_path)
            action = "verified"
        except Exception:  # noqa: BLE001
            existing = ""
            action = "created"

        content = MOCK_TEST_FILE
        files_changed_out: list[FileChange] = []
        if not existing.strip() or existing.strip() != content.strip():
            change = repo_tools.write_file(test_path, content)
            files_changed_out.append(change)
            transcript.append(f"Wrote {test_path} ({change.action})")
            action = change.action
        else:
            transcript.append(f"Existing tests in {test_path} already cover criteria")

        test_names = _extract_test_names(content)
        transcript.append(f"Test cases ready: {', '.join(test_names) or 'none detected'}")
        transcript.append(f"Will run: {validate_command}")

        return {
            "summary": (
                f"{'Created' if action == 'created' else 'Updated' if action == 'modified' else 'Verified'} "
                f"validation tests in {test_path} ({len(test_names)} test case(s))"
            ),
            "testFiles": [test_path],
            "testPreview": {test_path: content},
            "testCases": test_names,
            "filesChanged": files_changed_out,
            "transcript": transcript,
        }

    files_changed_out: list[FileChange] = []

    def execute_tool(name: str, args: dict[str, Any]) -> str:
        if name == "list_dir":
            return json.dumps(repo_tools.list_dir(args.get("path") or "."))
        if name == "read_file":
            return repo_tools.read_file(args["path"])
        if name == "write_file":
            change = repo_tools.write_file(args["path"], args["content"])
            files_changed_out.append(change)
            return change.model_dump_json()
        if name == "search":
            return json.dumps(repo_tools.search_repo(args["query"]))
        if name == "git_diff":
            return json.dumps([c.model_dump() for c in repo_tools.git_diff_stat()])
        return f"Unknown tool {name}"

    scope = _scope_note(main_target_file, target_repo)
    system_prompt = (
        "You are a Validation Agent. Generate or update automated tests that verify "
        "the implementation meets the success criteria.\n"
        "Use read_file to inspect source and existing tests, then write_file to create "
        "or update test files. Prefer the project's existing test framework and patterns.\n"
        "Do not modify production source files — only test files."
    )
    if instructions:
        system_prompt += f"\n\nAdditional instructions:\n{instructions}"
    system_prompt += f"\n\n{scope}"

    transcript, _ = chat_with_tools(
        model=model,
        system=system_prompt,
        user=json.dumps(
            {
                "objective": objective,
                "criteria": criteria,
                "plan": plan,
                "changedFiles": changed_paths,
                "validateCommand": validate_command,
            }
        ),
        tools=[
            t
            for t in TOOL_DEFS
            if t["function"]["name"]
            in ("list_dir", "read_file", "write_file", "search", "git_diff")
        ],
        execute_tool=execute_tool,
    )

    test_files = [f.path for f in files_changed_out if "test" in f.path.lower()]
    if not test_files:
        test_files = [test_path]

    test_preview: dict[str, str] = {}
    test_cases: list[str] = []
    for path in test_files:
        try:
            content = repo_tools.read_file(path)
            test_preview[path] = content
            test_cases.extend(_extract_test_names(content))
        except Exception:  # noqa: BLE001
            continue

    return {
        "summary": transcript[-1] if transcript else "Validation tests prepared",
        "testFiles": test_files,
        "testPreview": test_preview,
        "testCases": test_cases,
        "filesChanged": files_changed_out,
        "transcript": transcript,
    }


def summarize_validation(
    *,
    passed: bool,
    evidence: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    if use_mock():
        if passed:
            return "All automated checks passed — tests green and required files present."
        return "Validation failed — review test output and file checks above."

    system_prompt = "Summarize validation evidence. Never change the pass/fail verdict."
    if instructions:
        system_prompt += f"\n\nAdditional instructions from user:\n{instructions}"
    system_prompt += f" Deterministic verdict is: {'PASS' if passed else 'FAIL'}."

    return chat_text(
        model=model,
        system=system_prompt,
        user=evidence,
        json_mode=False,
    )
