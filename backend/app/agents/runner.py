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


def generate_success_criteria(
    *,
    objective: str,
    constraints: str,
    instructions: Optional[str] = None,
    model: Optional[str] = None,
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

    text = chat_text(
        model=model,
        system=instructions
        or "Convert the engineering objective into measurable success criteria. Return JSON { criteria: string[] }.",
        user=f"Objective:\n{objective}\n\nConstraints:\n{constraints}",
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
) -> dict[str, Any]:
    listing = ", ".join(repo_tools.list_dir("."))
    app_src = repo_tools.read_file("src/app.js")

    if use_mock():
        steps = [
            "Read src/app.js and understand the HTTP router pattern",
            "Add a GET /health branch returning JSON { status: 'healthy' }",
            "Keep the existing GET / route unchanged",
            "Run npm test and fix until green",
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
        return {"plan": plan, "steps": steps, "raw": plan}

    text = chat_text(
        model=model,
        system=instructions
        or "Create a concrete implementation plan naming real files. Return JSON { steps: string[], plan: string }.",
        user=json.dumps(
            {
                "objective": objective,
                "constraints": constraints,
                "criteria": criteria,
                "feedback": feedback,
                "repoListing": listing,
                "appJs": app_src,
            }
        ),
        json_mode=True,
    )
    parsed = json.loads(text or "{}")
    steps = parsed.get("steps") or []
    plan = parsed.get("plan") or "\n".join(
        f"{i + 1}. {s}" for i, s in enumerate(steps)
    )
    return {"plan": plan, "steps": steps, "raw": plan}


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
        if name == "search":
            return json.dumps(repo_tools.search_repo(args["query"]))
        if name == "run_shell":
            return json.dumps(repo_tools.run_shell(args["command"]))
        return f"Unknown tool {name}"

    transcript, _ = chat_with_tools(
        model=model,
        system=(
            instructions
            or "Implement the planned changes using tools. Stay inside demo-repo."
        )
        + " Prefer editing src/app.js. Stop when the plan is implemented.",
        user=json.dumps(
            {
                "objective": objective,
                "plan": plan,
                "criteria": criteria,
                "feedback": feedback,
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

    return chat_text(
        model=model,
        system=(
            instructions
            or "Summarize validation evidence. Never change the pass/fail verdict."
        )
        + f" Deterministic verdict is: {'PASS' if passed else 'FAIL'}.",
        user=evidence,
        json_mode=False,
    )
