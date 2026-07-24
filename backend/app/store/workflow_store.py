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
            "position": {"x": 80, "y": 400},
            "data": {
                "label": "Coding Objective",
                "description": "Objective and constraints",
                "nodeType": "input",
                "objective": "",
                "constraints": "",
                "targetRepo": None,
                "mainTargetFile": None,
                "validateCommand": None,
            },
        },
        {
            "id": "criteria",
            "type": "loopNode",
            "position": {"x": 460, "y": 100},
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
            "position": {"x": 840, "y": 100},
            "data": {
                "label": "Human Gate (Review)",
                "description": "Review and approve success criteria",
                "nodeType": "humanGate",
            },
        },
        {
            "id": "planning",
            "type": "loopNode",
            "position": {"x": 460, "y": 400},
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
            "id": "gate-plan",
            "type": "loopNode",
            "position": {"x": 840, "y": 400},
            "data": {
                "label": "Review & Approve Plan",
                "description": "Approve architecture and steps",
                "nodeType": "humanGate",
            },
        },
        {
            "id": "execution",
            "type": "loopNode",
            "position": {"x": 1200, "y": 400},
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
            "position": {"x": 1520, "y": 400},
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
            "position": {"x": 1520, "y": 700},
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
            "position": {"x": 1200, "y": 700},
            "data": {
                "label": "Decision",
                "description": "Pass / Fail?",
                "nodeType": "decision",
            },
        },
        {
            "id": "gate-final",
            "type": "loopNode",
            "position": {"x": 840, "y": 700},
            "data": {
                "label": "Human Gate (Approve)",
                "description": "Approve completion",
                "nodeType": "humanGate",
            },
        },
        {
            "id": "success",
            "type": "loopNode",
            "position": {"x": 460, "y": 700},
            "data": {
                "label": "Success",
                "description": "Task Successful",
                "nodeType": "success",
            },
        },
        {
            "id": "stop",
            "type": "loopNode",
            "position": {"x": 1280, "y": 100},
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
        {
            "id": "e-planning-gate-plan",
            "source": "planning",
            "target": "gate-plan",
            "sourceHandle": "success",
        },
        {
            "id": "e-gate-plan-exec",
            "source": "gate-plan",
            "target": "execution",
            "sourceHandle": "approve",
        },
        {
            "id": "e-gate-plan-stop",
            "source": "gate-plan",
            "target": "stop",
            "sourceHandle": "reject",
            "label": "reject",
            "style": {"stroke": "#ef4444", "strokeDasharray": "6 4"},
        },
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
        return Workflow.model_validate(json.loads(path.read_text(encoding="utf-8")))
    workflow = Workflow.model_validate(deepcopy(DEFAULT_WORKFLOW))
    save_workflow(workflow)
    return workflow


def save_workflow(workflow: Workflow) -> Workflow:
    _ensure_dirs()
    path = workflow_path(workflow.id)
    path.write_text(workflow.model_dump_json(indent=2), encoding="utf-8")
    return workflow


def reset_workflow(workflow_id: str = "default") -> Workflow:
    """Restore a workflow to the in-code default template, discarding any
    edits that were previously auto-saved over it (e.g. via startRun's
    save-then-run flow). This is the fix for stray node edits — like a
    test 'instructions' string typed into a node — silently becoming the
    permanent seed template on disk."""
    workflow = Workflow.model_validate(deepcopy(DEFAULT_WORKFLOW))
    workflow.id = workflow_id
    return save_workflow(workflow)


def export_workflow_yaml(workflow_id: str = "default") -> str:
    workflow = load_workflow(workflow_id)
    return yaml.safe_dump(
        workflow.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
