from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from app.models import ConsoleEvent, RunRecord
from app.paths import RUNS_DIR, run_path

_memory: dict[str, RunRecord] = {}


def _ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def save_run(run: RunRecord) -> RunRecord:
    _ensure_dirs()
    run.updatedAt = datetime.now(timezone.utc).isoformat()
    _memory[run.id] = run
    run_path(run.id).write_text(run.model_dump_json(indent=2), encoding="utf-8")
    return run


def load_run(run_id: str) -> Optional[RunRecord]:
    if run_id in _memory:
        return _memory[run_id]
    path = run_path(run_id)
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return None
        run = RunRecord.model_validate(json.loads(content))
        _memory[run_id] = run
        return run
    except Exception:
        return None


def list_runs() -> list[RunRecord]:
    _ensure_dirs()
    runs: list[RunRecord] = []
    for path in RUNS_DIR.glob("*.json"):
        run = load_run(path.stem)
        if run:
            runs.append(run)
    runs.sort(key=lambda r: r.startedAt, reverse=True)
    return runs


def append_event(
    run: RunRecord,
    *,
    level: str,
    message: str,
    node_id: Optional[str] = None,
) -> ConsoleEvent:
    event = ConsoleEvent(
        id=f"evt_{len(run.events) + 1}_{int(datetime.now().timestamp() * 1000)}",
        ts=datetime.now(timezone.utc).isoformat(),
        level=level,  # type: ignore[arg-type]
        nodeId=node_id,
        message=message,
    )
    run.events.append(event)
    return event
