from __future__ import annotations

import json
from copy import deepcopy

import yaml

from app.models import Workflow
from app.paths import WORKFLOWS_DIR, workflow_path

DEFAULT_WORKFLOW: dict = {
    "id": "default",
    "name": "New Workflow",
    "maxAttempts": 3,
    "nodes": [
        {
            "id": "input",
            "type": "loopNode",
            "position": {"x": 40, "y": 180},
            "data": {
                "label": "Coding Objective",
                "description": "Objective and constraints",
                "nodeType": "input",
                "objective": (
                    'Add a GET /health endpoint that returns JSON { status: "healthy" } '
                    "with HTTP 200, and ensure unit tests pass."
                ),
                "constraints": (
                    "Focus changes on the main target file. Other files may be "
                    "changed if needed, but will require human approval."
                ),
                "targetRepo": "demo-repo",
                "mainTargetFile": "src/app.js",
                "validateCommand": "npm test",
            },
        },
        {
            "id": "criteria",
            "type": "loopNode",
            "position": {"x": 280, "y": 80},
            "data": {
                "label": "Success Criteria Agent",
                "description": "Generate measurable success criteria",
                "nodeType": "agent",
                "role": "successCriteria",
                "instructions": (
                    "Convert the engineering objective into measurable success criteria. "
                    "Ensure the criteria are specific, verifiable and prioritized."
                ),
                "model": "mistral-small-latest",
                "tools": ["Repo Reader", "Search"],
                "maxRetries": 2,
                "timeout": 300,
            },
        },
        {
            "id": "gate-criteria",
            "type": "loopNode",
            "position": {"x": 540, "y": 80},
            "data": {
                "label": "Human Gate (Review)",
                "description": "Review and approve success criteria",
                "nodeType": "humanGate",
            },
        },
        {
            "id": "planning",
            "type": "loopNode",
            "position": {"x": 280, "y": 280},
            "data": {
                "label": "Planning Agent",
                "description": "Create / revise implementation plan",
                "nodeType": "agent",
                "role": "planning",
                "instructions": (
                    "Create or revise a concrete implementation plan grounded in real "
                    "files in the repository. Name modules, order of work, and risks."
                ),
                "model": "mistral-small-latest",
                "tools": ["Repo Reader", "Search"],
                "maxRetries": 2,
                "timeout": 300,
            },
        },
        {
            "id": "execution",
            "type": "loopNode",
            "position": {"x": 540, "y": 280},
            "data": {
                "label": "Execution Agent",
                "description": "Implement changes in the codebase",
                "nodeType": "agent",
                "role": "execution",
                "instructions": (
                    "Implement the planned changes in the repository. Follow coding "
                    "standards and existing patterns. Prefer minimal diffs."
                ),
                "model": "mistral-small-latest",
                "tools": ["File Editor", "Search", "Git", "Terminal"],
                "maxRetries": 2,
                "timeout": 300,
            },
        },
        {
            "id": "command",
            "type": "loopNode",
            "position": {"x": 800, "y": 280},
            "data": {
                "label": "Run Tests",
                "description": "npm test",
                "nodeType": "command",
                "command": "npm test",
                "timeout": 120,
            },
        },
        {
            "id": "validation",
            "type": "loopNode",
            "position": {"x": 1060, "y": 280},
            "data": {
                "label": "Validation Agent",
                "description": "Validate changes and provide evidence",
                "nodeType": "validator",
                "role": "validation",
                "instructions": (
                    "Summarize validation evidence. Do not override deterministic "
                    "check results."
                ),
                "fileChecks": ["src/app.js"],
                "model": "mistral-small-latest",
                "maxRetries": 1,
                "timeout": 120,
            },
        },
        {
            "id": "decision",
            "type": "loopNode",
            "position": {"x": 1320, "y": 280},
            "data": {
                "label": "Decision",
                "description": "Pass / Fail?",
                "nodeType": "decision",
            },
        },
        {
            "id": "gate-final",
            "type": "loopNode",
            "position": {"x": 1320, "y": 80},
            "data": {
                "label": "Human Gate (Approve)",
                "description": "Approve completion",
                "nodeType": "humanGate",
            },
        },
        {
            "id": "success",
            "type": "loopNode",
            "position": {"x": 1580, "y": 40},
            "data": {
                "label": "Success",
                "description": "Task Successful",
                "nodeType": "success",
            },
        },
        {
            "id": "stop",
            "type": "loopNode",
            "position": {"x": 1580, "y": 200},
            "data": {
                "label": "Stop",
                "description": "Stopped Safely",
                "nodeType": "stop",
            },
        },
    ],
    "edges": [
        {"id": "e-input-criteria", "source": "input", "target": "criteria"},
        {
            "id": "e-criteria-gate",
            "source": "criteria",
            "target": "gate-criteria",
            "sourceHandle": "success",
        },
        {
            "id": "e-gate-planning",
            "source": "gate-criteria",
            "target": "planning",
            "sourceHandle": "approve",
        },
        {
            "id": "e-gate-stop1",
            "source": "gate-criteria",
            "target": "stop",
            "sourceHandle": "reject",
            "label": "reject",
            "style": {"stroke": "#ef4444", "strokeDasharray": "6 4"},
        },
        {"id": "e-planning-exec", "source": "planning", "target": "execution"},
        {"id": "e-exec-cmd", "source": "execution", "target": "command"},
        {"id": "e-cmd-val", "source": "command", "target": "validation"},
        {"id": "e-val-decision", "source": "validation", "target": "decision"},
        {
            "id": "e-decision-fail",
            "source": "decision",
            "target": "planning",
            "sourceHandle": "fail",
            "label": "fail → retry",
            "style": {"stroke": "#ef4444", "strokeDasharray": "6 4"},
            "animated": True,
        },
        {
            "id": "e-decision-pass",
            "source": "decision",
            "target": "gate-final",
            "sourceHandle": "pass",
            "label": "pass",
            "style": {"stroke": "#22c55e", "strokeDasharray": "6 4"},
        },
        {
            "id": "e-final-success",
            "source": "gate-final",
            "target": "success",
            "sourceHandle": "approve",
            "style": {"stroke": "#22c55e"},
        },
        {
            "id": "e-final-stop",
            "source": "gate-final",
            "target": "stop",
            "sourceHandle": "reject",
            "label": "reject",
            "style": {"stroke": "#ef4444", "strokeDasharray": "6 4"},
        },
    ],
}


def _ensure_dirs() -> None:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def load_workflow(workflow_id: str = "default") -> Workflow:
    _ensure_dirs()
    path = workflow_path(workflow_id)
    if path.exists():
        return Workflow.model_validate(json.loads(path.read_text()))
    workflow = Workflow.model_validate(deepcopy(DEFAULT_WORKFLOW))
    save_workflow(workflow)
    return workflow


def save_workflow(workflow: Workflow) -> Workflow:
    _ensure_dirs()
    path = workflow_path(workflow.id)
    path.write_text(workflow.model_dump_json(indent=2))
    return workflow


def export_workflow_yaml(workflow_id: str = "default") -> str:
    workflow = load_workflow(workflow_id)
    return yaml.safe_dump(
        workflow.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
