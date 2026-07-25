from __future__ import annotations

import json
from copy import deepcopy

import yaml

from app.models import Workflow
from app.paths import WORKFLOWS_DIR, workflow_path

try:
    from app.store.mysql_db import (
        save_workflow_to_mysql as _mysql_save_workflow,
        rename_workflow_in_mysql as _mysql_rename_workflow,
        delete_workflow_from_mysql as _mysql_delete_workflow,
    )
except Exception:
    _mysql_save_workflow = None  # type: ignore[assignment]
    _mysql_rename_workflow = None  # type: ignore[assignment]
    _mysql_delete_workflow = None  # type: ignore[assignment]

DEFAULT_WORKFLOW: dict = {
    "id": "default",
    "name": "New Workflow",
    "maxAttempts": 3,
    "nodes": [
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
            "id": "gate-plan",
            "type": "loopNode",
            "position": {"x": 540, "y": 280},
            "data": {
                "label": "Human Gate (Review Plan)",
                "description": "Review and approve implementation plan",
                "nodeType": "humanGate",
            },
        },
        {
            "id": "execution",
            "type": "loopNode",
            "position": {"x": 800, "y": 280},
            "data": {
                "label": "Execution Agent",
                "description": "Implement changes in the codebase",
                "nodeType": "agent",
                "role": "execution",
                "instructions": (
                    "Implement the planned changes in the repository. Follow coding "
                    "standards and existing patterns. Prefer minimal diffs. IMPORTANT: "
                    "You MUST write or update a test file (e.g., matching 'test_*.py' or "
                    "'*.test.js') to check the functionality of the new/updated/deleted code changes. "
                    "The test file must be runnable by the validation agent (e.g. via pytest or npm test)."
                ),
                "model": "mistral-small-latest",
                "tools": ["File Editor", "Search", "Git", "Terminal"],
                "maxRetries": 2,
                "timeout": 300,
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
                    "Summarize validation evidence. Ensure the test files written by the "
                    "execution agent are run and their output is captured. Do not override "
                    "deterministic check results."
                ),
                "fileChecks": [],
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
        {"id": "e-planning-gate", "source": "planning", "target": "gate-plan"},
        {
            "id": "e-gate-exec",
            "source": "gate-plan",
            "target": "execution",
            "sourceHandle": "approve",
        },
        {"id": "e-exec-val", "source": "execution", "target": "validation"},
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
            "target": "success",
            "sourceHandle": "pass",
            "label": "pass",
            "style": {"stroke": "#22c55e", "strokeDasharray": "6 4"},
        },
    ],
}


def _ensure_dirs() -> None:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


def load_workflow(workflow_id: str = "default") -> Workflow:
    _ensure_dirs()
    path = workflow_path(workflow_id)
    if path.exists():
        try:
            return Workflow.model_validate(json.loads(path.read_text()))
        except Exception as err:
            print(f"[WorkflowStore] Error parsing {path}, resetting to default: {err}")
    try:
        workflow = Workflow.model_validate(deepcopy(DEFAULT_WORKFLOW))
        save_workflow(workflow)
        return workflow
    except Exception as err:
        print(f"[WorkflowStore] Fallback to DEFAULT_WORKFLOW failed: {err}")
        return Workflow.model_construct(
            id="default",
            name="New Workflow",
            maxAttempts=3,
            nodes=[],
            edges=[],
        )


def save_workflow(workflow: Workflow) -> Workflow:
    _ensure_dirs()
    path = workflow_path(workflow.id)
    path.write_text(workflow.model_dump_json(indent=2))
    if _mysql_save_workflow:
        try:
            _mysql_save_workflow(workflow)
        except Exception as err:
            print(f"[WorkflowStore] MySQL sync failed (non-fatal): {err}")
    return workflow


def rename_workflow(workflow_id: str, new_name: str) -> None:
    _ensure_dirs()
    path = workflow_path(workflow_id)
    if path.exists():
        try:
            data = json.loads(path.read_text())
            data["name"] = new_name
            path.write_text(json.dumps(data, indent=2))
        except Exception as err:
            print(f"[WorkflowStore] Error updating file {path}: {err}")
    if _mysql_rename_workflow:
        try:
            _mysql_rename_workflow(workflow_id, new_name)
        except Exception as err:
            print(f"[WorkflowStore] MySQL rename failed: {err}")


def delete_workflow(workflow_id: str) -> None:
    _ensure_dirs()
    path = workflow_path(workflow_id)
    if path.exists():
        try:
            path.unlink()
        except Exception as err:
            print(f"[WorkflowStore] Error removing file {path}: {err}")
    if _mysql_delete_workflow:
        try:
            _mysql_delete_workflow(workflow_id)
        except Exception as err:
            print(f"[WorkflowStore] MySQL delete failed: {err}")


def export_workflow_yaml(workflow_id: str = "default") -> str:

    workflow = load_workflow(workflow_id)
    return yaml.safe_dump(
        workflow.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
