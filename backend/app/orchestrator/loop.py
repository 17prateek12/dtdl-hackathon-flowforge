from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agents import runner as agents
from app.agents import tools as repo_tools
from app.models import (
    HumanGateDecision,
    NodeExecutionReceipt,
    PendingHumanGate,
    RunRecord,
    Workflow,
    WorkflowNode,
)
from app.orchestrator.validation import (
    CommandResult,
    deterministic_validate,
    run_command_node,
)
from app.store.run_store import append_event, load_run, save_run
from app.store.workflow_store import load_workflow

_active: dict[str, dict] = {}
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _find_node(workflow: Workflow, node_id: str) -> WorkflowNode:
    for node in workflow.nodes:
        if node.id == node_id:
            return node
    raise ValueError(f"Node not found: {node_id}")


def _next_targets(
    workflow: Workflow, source_id: str, handle: Optional[str] = None
) -> list[str]:
    targets: list[str] = []
    for edge in workflow.edges:
        if edge.source != source_id:
            continue
        if handle is None:
            if edge.sourceHandle in (None, "success"):
                targets.append(edge.target)
        elif edge.sourceHandle == handle or (
            edge.sourceHandle is None and handle == "success"
        ):
            targets.append(edge.target)
    return targets


def _set_status(run: RunRecord, node_id: str, status: str) -> None:
    run.nodeStatuses[node_id] = status  # type: ignore[assignment]
    run.currentNodeId = node_id


def _flush(run: RunRecord) -> None:
    save_run(run)


def _spawn(run_id: str, from_node_id: Optional[str] = None, via_handle: Optional[str] = None) -> None:
    thread = threading.Thread(
        target=continue_run,
        args=(run_id, from_node_id, via_handle),
        daemon=True,
    )
    thread.start()


def start_run(workflow_id: str = "default") -> RunRecord:
    workflow = load_workflow(workflow_id)
    input_node = _find_node(workflow, "input")
    baseline = repo_tools.git_snapshot()

    node_statuses = {n.id: "idle" for n in workflow.nodes}
    run = RunRecord(
        id=str(uuid.uuid4()),
        workflowId=workflow.id,
        status="running",
        attempt=1,
        maxAttempts=workflow.maxAttempts,
        nodeStatuses=node_statuses,  # type: ignore[arg-type]
        receipts={},
        events=[],
        filesChanged=[],
        objective=input_node.data.objective or "",
        constraints=input_node.data.constraints or "",
        criteria=[],
        plan="",
        startedAt=_now(),
        updatedAt=_now(),
        baselineCommit=baseline,
    )

    append_event(
        run,
        level="info",
        node_id="input",
        message=f"Objective received: {run.objective}",
    )
    _set_status(run, "input", "completed")
    run.receipts["input"] = NodeExecutionReceipt(
        nodeId="input",
        status="completed",
        output=run.objective,
        finishedAt=_now(),
    )
    _flush(run)

    with _lock:
        _active[run.id] = {"stopped": False}
    _spawn(run.id)
    return run


def stop_run(run_id: str) -> Optional[RunRecord]:
    with _lock:
        if run_id in _active:
            _active[run_id]["stopped"] = True
    run = load_run(run_id)
    if not run:
        return None
    if run.status in ("running", "waiting_for_human"):
        run.status = "stopped"
        run.finishedAt = _now()
        append_event(run, level="warn", message="Run stopped by user")
        repo_tools.git_rollback()
        append_event(
            run,
            level="info",
            message="Workspace rolled back to baseline (green state)",
        )
        _set_status(run, "stop", "completed")
        _flush(run)
    return run


def resume_run(run_id: str, decision: HumanGateDecision) -> Optional[RunRecord]:
    run = load_run(run_id)
    if not run or not run.pendingGate:
        return run

    gate_id = run.pendingGate.nodeId
    append_event(
        run, level="info", node_id=gate_id, message=f"Human decision: {decision.action}"
    )

    if decision.action == "edit" and decision.editedText:
        if run.pendingGate.kind == "criteria":
            cleaned: list[str] = []
            for line in decision.editedText.splitlines():
                text = line.strip()
                if not text:
                    continue
                if text[0].isdigit() and ". " in text:
                    text = text.split(". ", 1)[1]
                cleaned.append(text)
            run.criteria = cleaned
            append_event(
                run,
                level="info",
                node_id=gate_id,
                message=f"Criteria edited ({len(run.criteria)} items)",
            )

    if decision.action == "reject":
        _set_status(run, gate_id, "completed")
        run.receipts[gate_id] = NodeExecutionReceipt(
            nodeId=gate_id,
            status="completed",
            output="Rejected by human",
            finishedAt=_now(),
        )
        run.pendingGate = None
        run.status = "stopped"
        _set_status(run, "stop", "completed")
        run.finishedAt = _now()
        repo_tools.git_rollback()
        append_event(
            run,
            level="warn",
            message="Stopped Safely after human rejection; workspace rolled back",
        )
        _flush(run)
        return run

    _set_status(run, gate_id, "completed")
    run.receipts[gate_id] = NodeExecutionReceipt(
        nodeId=gate_id,
        status="completed",
        output="Edited & approved" if decision.action == "edit" else "Approved",
        finishedAt=_now(),
    )
    run.pendingGate = None
    run.status = "running"
    _flush(run)

    with _lock:
        _active[run.id] = {"stopped": False}
    _spawn(run.id, gate_id, "approve")
    return run


def _stopped(run_id: str, run: RunRecord) -> bool:
    with _lock:
        stopped = bool(_active.get(run_id, {}).get("stopped"))
    if stopped:
        run.status = "stopped"
        run.finishedAt = _now()
        _flush(run)
        return True
    return False


def continue_run(
    run_id: str,
    from_node_id: Optional[str] = None,
    via_handle: Optional[str] = None,
) -> None:
    run = load_run(run_id)
    if not run:
        return
    workflow = load_workflow(run.workflowId)

    if from_node_id and via_handle:
        queue = _next_targets(workflow, from_node_id, via_handle)
    elif from_node_id:
        queue = _next_targets(workflow, from_node_id)
    else:
        queue = ["criteria"]

    last_command: Optional[CommandResult] = None
    last_validation_passed: Optional[bool] = None

    while queue:
        if _stopped(run_id, run):
            return

        node_id = queue.pop(0)
        node = _find_node(workflow, node_id)
        _set_status(run, node_id, "running")
        append_event(
            run, level="info", node_id=node_id, message=f"Running: {node.data.label}"
        )
        _flush(run)
        started_at = _now()

        try:
            ntype = node.data.nodeType

            if ntype == "agent" and node.data.role == "successCriteria":
                result = agents.generate_success_criteria(
                    objective=run.objective,
                    constraints=run.constraints,
                    instructions=node.data.instructions,
                    model=node.data.model,
                )
                run.criteria = result["criteria"]
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed",
                    output=result["raw"],
                    startedAt=started_at,
                    finishedAt=_now(),
                )
                _set_status(run, node_id, "completed")
                append_event(
                    run,
                    level="success",
                    node_id=node_id,
                    message=f"Generated {len(result['criteria'])} success criteria",
                )
                _flush(run)
                queue.extend(_next_targets(workflow, node_id, "success"))

            elif ntype == "agent" and node.data.role == "planning":
                result = agents.generate_plan(
                    objective=run.objective,
                    constraints=run.constraints,
                    criteria=run.criteria,
                    feedback=run.validationEvidence,
                    instructions=node.data.instructions,
                    model=node.data.model,
                )
                run.plan = result["plan"]
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed",
                    output=result["plan"],
                    startedAt=started_at,
                    finishedAt=_now(),
                )
                _set_status(run, node_id, "completed")
                append_event(
                    run,
                    level="success",
                    node_id=node_id,
                    message=f"Plan ready ({len(result['steps']) or 'n'} steps)",
                )
                _flush(run)
                queue.extend(_next_targets(workflow, node_id))

            elif ntype == "agent" and node.data.role == "execution":
                force_fail = (
                    os.getenv("MOCK_AGENTS", "true").lower() == "true"
                    and run.attempt == 1
                )
                result = agents.execute_changes(
                    objective=run.objective,
                    plan=run.plan,
                    criteria=run.criteria,
                    feedback=run.validationEvidence,
                    instructions=node.data.instructions,
                    model=node.data.model,
                    force_fail=force_fail,
                )
                files = result["filesChanged"] or repo_tools.git_diff_stat()
                for f in files:
                    existing = next(
                        (x for x in run.filesChanged if x.path == f.path), None
                    )
                    if existing:
                        existing.action = f.action
                        existing.linesAdded = f.linesAdded
                        existing.linesRemoved = f.linesRemoved
                    else:
                        run.filesChanged.append(f)
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed",
                    output=result["summary"],
                    filesChanged=files,
                    commands=result["transcript"],
                    startedAt=started_at,
                    finishedAt=_now(),
                )
                _set_status(run, node_id, "completed")
                for line in result["transcript"]:
                    append_event(run, level="info", node_id=node_id, message=line)
                append_event(
                    run,
                    level="success",
                    node_id=node_id,
                    message=f"Execution finished ({len(files)} file changes)",
                )
                _flush(run)
                queue.extend(_next_targets(workflow, node_id))

            elif ntype == "command":
                cmd = node.data.command or "npm test"
                last_command = run_command_node(cmd, node.data.timeout or 120)
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed" if last_command.passed else "failed",
                    output=f"exit {last_command.exit_code}",
                    evidence="\n".join(
                        x for x in [last_command.stdout, last_command.stderr] if x
                    ),
                    commands=[cmd],
                    startedAt=started_at,
                    finishedAt=_now(),
                )
                _set_status(
                    run, node_id, "completed" if last_command.passed else "failed"
                )
                append_event(
                    run,
                    level="success" if last_command.passed else "error",
                    node_id=node_id,
                    message=f"$ {cmd} → exit {last_command.exit_code}",
                )
                _flush(run)
                queue.extend(_next_targets(workflow, node_id))

            elif ntype == "validator":
                if last_command is None:
                    last_command = CommandResult(
                        exit_code=1,
                        stdout="",
                        stderr="No command result available",
                        command="(none)",
                    )
                det = deterministic_validate(
                    command_result=last_command,
                    file_checks=node.data.fileChecks,
                )
                last_validation_passed = det["passed"]
                run.validationEvidence = det["evidence"]
                summary = agents.summarize_validation(
                    passed=det["passed"],
                    evidence=det["evidence"],
                    instructions=node.data.instructions,
                    model=node.data.model,
                )
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed" if det["passed"] else "failed",
                    output=summary,
                    evidence=det["evidence"],
                    startedAt=started_at,
                    finishedAt=_now(),
                    retryReason=None
                    if det["passed"]
                    else "Deterministic checks failed",
                )
                _set_status(
                    run, node_id, "completed" if det["passed"] else "failed"
                )
                append_event(
                    run,
                    level="success" if det["passed"] else "error",
                    node_id=node_id,
                    message=(
                        "Validation PASSED (deterministic)"
                        if det["passed"]
                        else "Validation FAILED (deterministic) — feeding evidence back"
                    ),
                )
                _flush(run)
                queue.extend(_next_targets(workflow, node_id))

            elif ntype == "decision":
                passed = last_validation_passed is True
                _set_status(run, node_id, "completed")
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed",
                    output="pass" if passed else "fail",
                    finishedAt=_now(),
                )
                if passed:
                    append_event(
                        run,
                        level="success",
                        node_id=node_id,
                        message="Decision: PASS → human approval",
                    )
                    _flush(run)
                    queue.extend(_next_targets(workflow, node_id, "pass"))
                else:
                    if run.attempt >= run.maxAttempts:
                        append_event(
                            run,
                            level="warn",
                            node_id=node_id,
                            message=(
                                f"Attempts exhausted ({run.attempt}/"
                                f"{run.maxAttempts}) → Stopped Safely"
                            ),
                        )
                        repo_tools.git_rollback()
                        append_event(
                            run,
                            level="info",
                            message="Rolled back workspace to green baseline",
                        )
                        _set_status(run, "stop", "completed")
                        run.status = "stopped"
                        run.finishedAt = _now()
                        _flush(run)
                        return
                    run.attempt += 1
                    append_event(
                        run,
                        level="warn",
                        node_id=node_id,
                        message=(
                            f"Decision: FAIL → retry planning "
                            f"(attempt {run.attempt}/{run.maxAttempts})"
                        ),
                    )
                    _flush(run)
                    queue.extend(_next_targets(workflow, node_id, "fail"))

            elif ntype == "humanGate":
                kind = "criteria" if node_id == "gate-criteria" else "final"
                if kind == "criteria":
                    summary = "\n".join(
                        f"{i + 1}. {c}" for i, c in enumerate(run.criteria)
                    )
                    editable = summary
                else:
                    summary = "\n".join(
                        [
                            f"Attempt {run.attempt}/{run.maxAttempts}",
                            "",
                            "Criteria:",
                            *[f"- {c}" for c in run.criteria],
                            "",
                            "Validation evidence:",
                            run.validationEvidence or "(none)",
                            "",
                            "Files changed: "
                            + (
                                ", ".join(f.path for f in run.filesChanged)
                                or "(none)"
                            ),
                        ]
                    )
                    editable = None
                run.pendingGate = PendingHumanGate(
                    nodeId=node_id,
                    kind=kind,
                    title=(
                        "Review & Approve Success Criteria"
                        if kind == "criteria"
                        else "Approve Completion"
                    ),
                    summary=summary,
                    editableText=editable,
                )
                _set_status(run, node_id, "waiting")
                run.status = "waiting_for_human"
                append_event(
                    run,
                    level="warn",
                    node_id=node_id,
                    message=f"Paused for human gate: {run.pendingGate.title}",
                )
                _flush(run)
                return

            elif ntype == "success":
                _set_status(run, node_id, "completed")
                run.status = "succeeded"
                run.finishedAt = _now()
                append_event(
                    run, level="success", node_id=node_id, message="Task Successful"
                )
                _flush(run)
                return

            elif ntype == "stop":
                _set_status(run, node_id, "completed")
                run.status = "stopped"
                run.finishedAt = _now()
                append_event(
                    run, level="warn", node_id=node_id, message="Stopped Safely"
                )
                _flush(run)
                return

            else:
                _set_status(run, node_id, "completed")
                queue.extend(_next_targets(workflow, node_id))

        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            _set_status(run, node_id, "failed")
            run.receipts[node_id] = NodeExecutionReceipt(
                nodeId=node_id,
                status="failed",
                output=message,
                startedAt=started_at,
                finishedAt=_now(),
            )
            append_event(run, level="error", node_id=node_id, message=message)
            run.status = "failed"
            run.lastError = message
            run.finishedAt = _now()
            _flush(run)
            return
