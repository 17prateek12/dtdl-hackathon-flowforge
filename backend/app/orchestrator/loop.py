from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agents import runner as agents
from app.agents import tools as repo_tools
from app.agents.workspace import RepoWorkspace, bind_workspace, normalize_rel_path, parse_target_files
from app.models import (
    FileChange,
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
    format_validation_report,
    resolve_smart_validation,
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


def _workspace_for_run(run: RunRecord) -> RepoWorkspace:
    return RepoWorkspace.create(
        target_repo=run.targetRepo or None,
        main_target_file=run.mainTargetFile or None,
    )


def _resolve_main_target(input_node: WorkflowNode) -> str:
    main = (input_node.data.mainTargetFile or "").strip()
    if main:
        return normalize_rel_path(main)
    raw_files = input_node.data.targetFiles
    if raw_files:
        parsed = parse_target_files(raw_files)
        if parsed:
            return parsed[0]
    return ""


def _extra_file_reason(
    path: str,
    *,
    transcript: list[str],
    plan: str,
) -> str:
    name = path.rsplit("/", 1)[-1]
    for line in transcript:
        if path in line or name in line:
            return line.strip()[:240]
    for line in plan.splitlines():
        if path in line or name in line:
            return line.strip()[:240]
    return "Agent changed this file while implementing the plan."


def _extra_files_summary(run: RunRecord, extra_files: list[str]) -> str:
    receipt = run.receipts.get("execution")
    transcript = list(receipt.commands or []) if receipt else []
    lines = [
        f"The agent changed files outside the main target ({run.mainTargetFile or 'not set'}).",
        "Review each file and approve or reject the extra changes.",
        "Rejecting will roll back all execution changes and generate a new plan.",
        "",
    ]
    for path in extra_files:
        change = next((f for f in run.filesChanged if f.path == path), None)
        action = change.action if change else "modified"
        reason = _extra_file_reason(path, transcript=transcript, plan=run.plan)
        lines.extend(
            [
                f"• {path} ({action})",
                f"  Reason: {reason}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _unapproved_extra_files(run: RunRecord, changed_paths: list[str]) -> list[str]:
    extra = repo_tools.list_extra_file_changes(changed_paths)
    approved = set(run.approvedExtraFiles or [])
    return [path for path in extra if path not in approved]


def _merge_files_changed(run: RunRecord, incoming: list[FileChange]) -> None:
    rank = {"deleted": 4, "created": 3, "modified": 2, "verified": 1}
    for f in incoming:
        existing = next((x for x in run.filesChanged if x.path == f.path), None)
        if existing:
            if rank.get(f.action, 0) > rank.get(existing.action, 0):
                existing.action = f.action
            if f.linesAdded is not None:
                existing.linesAdded = f.linesAdded
            if f.linesRemoved is not None:
                existing.linesRemoved = f.linesRemoved
        else:
            run.filesChanged.append(f)


def _merge_activity_files(run: RunRecord) -> None:
    """List files agents read, indexed, or validated — even without a git diff."""
    if run.receipts.get("planning"):
        _merge_files_changed(
            run,
            [FileChange(path=".flowforge/vector_index.json", action="verified")],
        )

    for path in run.mainTargetFile, "test/app.test.js":
        if not path:
            continue
        if run.receipts.get("validation") or run.receipts.get("execution"):
            try:
                repo_tools.read_file(path)
                _merge_files_changed(
                    run, [FileChange(path=path, action="verified")]
                )
            except Exception:  # noqa: BLE001
                continue


def _sync_files_from_git(run: RunRecord) -> None:
    _refresh_files_changed(run)


def _refresh_files_changed(run: RunRecord) -> None:
    if run.baselineCommit:
        _merge_files_changed(run, repo_tools.git_diff_since(run.baselineCommit))
    else:
        _merge_files_changed(run, repo_tools.git_diff_stat())
    for receipt in run.receipts.values():
        if receipt.filesChanged:
            _merge_files_changed(run, list(receipt.filesChanged))
    _merge_activity_files(run)


def _format_files_changed_summary(files: list[FileChange]) -> str:
    if not files:
        return "(none)"
    parts: list[str] = []
    for f in files:
        label = f.path
        if f.action == "verified":
            label = f"{f.path} (verified)"
        elif f.action != "modified":
            label = f"{f.path} ({f.action})"
        parts.append(label)
    return ", ".join(parts)


def start_run(workflow_id: str = "default", workflow: Optional["Workflow"] = None) -> RunRecord:
    from app.models import Workflow as WorkflowModel
    if workflow is None:
        workflow = load_workflow(workflow_id)
    input_node = _find_node(workflow, "input")

    objective = (input_node.data.objective or "").strip()
    if not objective:
        raise ValueError(
            "No objective provided. Please fill in the 'Coding Objective' field in the Input node before running."
        )

    main_target = _resolve_main_target(input_node)

    workspace = RepoWorkspace.create(
        target_repo=input_node.data.targetRepo,
        main_target_file=main_target or None,
    )
    bind_workspace(workspace)
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
        targetRepo=str(workspace.root),
        mainTargetFile=workspace.main_target_file or "",
        targetFiles=[workspace.main_target_file] if workspace.main_target_file else [],
        validateCommand=input_node.data.validateCommand or "",
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
    if run.mainTargetFile:
        append_event(
            run,
            level="info",
            node_id="input",
            message=f"Main target file: {run.mainTargetFile}",
        )
    append_event(
        run,
        level="info",
        node_id="input",
        message=f"Target codebase: {run.targetRepo}",
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
        _active[run.id] = {"stopped": False, "workspace": workspace}
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
    gate_kind = run.pendingGate.kind
    append_event(
        run, level="info", node_id=gate_id, message=f"Human decision: {decision.action}"
    )

    if decision.action == "edit" and decision.editedText:
        if gate_kind == "criteria":
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
        elif gate_kind == "plan":
            run.plan = decision.editedText
            append_event(
                run,
                level="info",
                node_id=gate_id,
                message="Architecture Plan edited by human",
            )

    if decision.action == "reject":
        if gate_kind == "extra_files":
            extra = run.pendingGate.extraFiles or []
            receipt = run.receipts.get(gate_id)
            exec_paths = [
                f.path for f in (receipt.filesChanged if receipt and receipt.filesChanged else [])
            ]
            if not exec_paths:
                exec_paths = [f.path for f in run.filesChanged]

            if exec_paths:
                repo_tools.revert_files(exec_paths)
                reverted = set(exec_paths)
                run.filesChanged = [f for f in run.filesChanged if f.path not in reverted]

            user_note = (decision.feedback or decision.editedText or "").strip()
            run.validationEvidence = (
                "Human rejected extra file changes"
                + (f" ({', '.join(extra)})" if extra else "")
                + ". All code changes from the last execution were rolled back. "
                "Create a new plan that better matches the objective."
                + (f"\n\nHuman instructions:\n{user_note}" if user_note else "")
            )

            _set_status(run, gate_id, "idle")
            run.receipts[gate_id] = NodeExecutionReceipt(
                nodeId=gate_id,
                status="skipped",
                output="Rolled back — replanning after extra-file rejection",
                finishedAt=_now(),
            )
            run.pendingGate = None
            run.status = "running"
            append_event(
                run,
                level="warn",
                node_id=gate_id,
                message=(
                    "Extra file changes rejected; rolled back execution and "
                    "returning to planning"
                    + (f" — note: {user_note[:120]}" if user_note else "")
                ),
            )
            _flush(run)
            ws = _workspace_for_run(run)
            bind_workspace(ws)
            with _lock:
                _active[run.id] = {"stopped": False, "workspace": ws}
            _spawn(run.id, "planning", "restart")
            return run

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

    if gate_kind == "extra_files":
        approved = run.pendingGate.extraFiles or []
        if approved:
            merged = list(dict.fromkeys([*(run.approvedExtraFiles or []), *approved]))
            run.approvedExtraFiles = merged
        run.pendingGate = None
        run.status = "running"
        _set_status(run, gate_id, "completed")
        append_event(
            run,
            level="success",
            node_id=gate_id,
            message="Extra file changes approved",
        )
        _flush(run)
        ws = _workspace_for_run(run)
        bind_workspace(ws)
        with _lock:
            _active[run.id] = {"stopped": False, "workspace": ws}
        _spawn(run.id, gate_id)
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

    ws = _workspace_for_run(run)
    bind_workspace(ws)
    with _lock:
        _active[run.id] = {"stopped": False, "workspace": ws}
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
    with _lock:
        ws = _active.get(run_id, {}).get("workspace")
    bind_workspace(ws if ws else _workspace_for_run(run))
    workflow = load_workflow(run.workflowId)

    if from_node_id and via_handle == "restart":
        queue = [from_node_id]
    elif from_node_id and via_handle:
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
                    main_target_file=run.mainTargetFile or None,
                    target_repo=run.targetRepo,
                )
                run.criteria = result["criteria"]
                for i, c in enumerate(run.criteria):
                    append_event(
                        run,
                        level="info",
                        node_id=node_id,
                        message=f"Criterion {i + 1}: {c}",
                    )
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
                    main_target_file=run.mainTargetFile or None,
                    target_repo=run.targetRepo,
                )
                run.plan = result["plan"]
                for f in result.get("touchedFiles") or []:
                    _merge_files_changed(run, [f])
                
                append_event(
                    run,
                    level="info",
                    node_id=node_id,
                    message="--- Architecture & Design Overview ---",
                )
                for line in str(result["plan"] or "").split("\n"):
                    trimmed = line.strip()
                    if trimmed:
                        append_event(
                            run,
                            level="info",
                            node_id=node_id,
                            message=trimmed,
                        )
                
                append_event(
                    run,
                    level="info",
                    node_id=node_id,
                    message="--- Implementation Milestones ---",
                )
                for i, step in enumerate(result.get("steps") or []):
                    append_event(
                        run,
                        level="info",
                        node_id=node_id,
                        message=f"Step {i + 1}: {step}",
                    )

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
                _refresh_files_changed(run)
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
                    main_target_file=run.mainTargetFile or None,
                    target_repo=run.targetRepo,
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
                _refresh_files_changed(run)
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed",
                    output=result["summary"],
                    filesChanged=list(run.filesChanged),
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
                    message=f"Execution finished ({len(run.filesChanged)} file changes)",
                )
                _flush(run)

                extra = _unapproved_extra_files(
                    run, [f.path for f in run.filesChanged]
                )
                if extra and run.mainTargetFile:
                    run.pendingGate = PendingHumanGate(
                        nodeId=node_id,
                        kind="extra_files",
                        title="Approve changes to additional files",
                        summary=_extra_files_summary(run, extra),
                        extraFiles=extra,
                    )
                    _set_status(run, node_id, "waiting")
                    run.status = "waiting_for_human"
                    append_event(
                        run,
                        level="warn",
                        node_id=node_id,
                        message=(
                            "Paused for approval: agent changed files outside "
                            f"{run.mainTargetFile} → {', '.join(extra)}"
                        ),
                    )
                    _flush(run)
                    return

                queue.extend(_next_targets(workflow, node_id))

            elif ntype == "command":
                smart = resolve_smart_validation(
                    validate_command=run.validateCommand or node.data.command,
                    objective=run.objective,
                    main_target_file=run.mainTargetFile or None,
                    files_changed=run.filesChanged,
                    file_checks=None,
                    criteria=run.criteria,
                )
                cmd = smart.command
                append_event(
                    run,
                    level="info",
                    node_id=node_id,
                    message=f"Smart validate: {smart.rationale}",
                )
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
                smart = resolve_smart_validation(
                    validate_command=run.validateCommand or node.data.command,
                    objective=run.objective,
                    main_target_file=run.mainTargetFile or None,
                    files_changed=run.filesChanged,
                    file_checks=node.data.fileChecks,
                    criteria=run.criteria,
                )
                test_result = agents.generate_validation_tests(
                    objective=run.objective,
                    criteria=run.criteria,
                    plan=run.plan,
                    files_changed=run.filesChanged,
                    validate_command=smart.command,
                    instructions=node.data.instructions,
                    model=node.data.model,
                    main_target_file=run.mainTargetFile or None,
                    target_repo=run.targetRepo,
                )
                for f in test_result.get("filesChanged") or []:
                    existing = next(
                        (x for x in run.filesChanged if x.path == f.path), None
                    )
                    if existing:
                        existing.action = f.action
                        existing.linesAdded = f.linesAdded
                        existing.linesRemoved = f.linesRemoved
                    else:
                        run.filesChanged.append(f)
                for path in test_result.get("testFiles") or []:
                    _merge_files_changed(
                        run, [FileChange(path=path, action="verified")]
                    )
                _refresh_files_changed(run)
                for line in test_result.get("transcript") or []:
                    append_event(
                        run, level="info", node_id=node_id, message=line
                    )
                append_event(
                    run,
                    level="info",
                    node_id=node_id,
                    message=test_result.get("summary", "Tests prepared"),
                )
                append_event(
                    run,
                    level="info",
                    node_id=node_id,
                    message=f"Smart validate: {smart.rationale}",
                )

                if last_command is None or last_command.command != smart.command:
                    last_command = run_command_node(
                        smart.command, node.data.timeout or 120
                    )

                det = deterministic_validate(
                    command_result=last_command,
                    file_checks=smart.file_checks
                    or ([run.mainTargetFile] if run.mainTargetFile else None),
                )
                last_validation_passed = det["passed"]
                summary = agents.summarize_validation(
                    passed=det["passed"],
                    evidence=det["evidence"],
                    instructions=node.data.instructions,
                    model=node.data.model,
                )
                report = format_validation_report(
                    test_generation=test_result,
                    command_result=last_command,
                    validation=det,
                    summary=summary,
                    files_changed=run.filesChanged,
                    smart_plan=smart,
                )
                run.validationEvidence = report
                run.receipts[node_id] = NodeExecutionReceipt(
                    nodeId=node_id,
                    status="completed" if det["passed"] else "failed",
                    output=summary,
                    evidence=report,
                    commands=test_result.get("transcript"),
                    filesChanged=list(run.filesChanged),
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
                        f"Validation PASSED — {len(test_result.get('testCases') or [])} test case(s) verified"
                        if det["passed"]
                        else "Validation FAILED — see output panel for details"
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
                if node_id == "gate-criteria":
                    kind = "criteria"
                    title = "Review & Approve Success Criteria"
                    summary = "\n".join(
                        f"{i + 1}. {c}" for i, c in enumerate(run.criteria)
                    )
                    editable = summary
                elif node_id == "gate-plan":
                    kind = "plan"
                    title = "Review & Approve Architecture Plan"
                    summary = run.plan
                    editable = run.plan
                else:
                    kind = "final"
                    title = "Approve Completion"
                    _refresh_files_changed(run)
                    criteria_lines = [f"  • {c}" for c in run.criteria[:4]]
                    if len(run.criteria) > 4:
                        criteria_lines.append(
                            f"  • … and {len(run.criteria) - 4} more"
                        )
                    summary = "\n".join(
                        [
                            f"Attempt {run.attempt}/{run.maxAttempts}",
                            "",
                            "Success criteria:",
                            *criteria_lines,
                            "",
                            run.validationEvidence or "(none)",
                            "",
                            "Files changed: "
                            + _format_files_changed_summary(run.filesChanged),
                        ]
                    )
                    editable = None
                run.pendingGate = PendingHumanGate(
                    nodeId=node_id,
                    kind=kind,
                    title=title,
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
