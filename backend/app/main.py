from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.models import HumanGateDecision, StartRunBody, Workflow
from app.orchestrator.loop import resume_run, start_run, stop_run
from app.agents.llm import list_models
from app.store.run_store import list_runs, load_run
from app.store.workflow_store import (
    export_workflow_yaml,
    load_workflow,
    save_workflow,
)

app = FastAPI(
    title="LoopForge API",
    description="Python control-plane backend for AI coding loops",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "loopforge-backend"}


@app.get("/api/models")
def get_models():
    return [
        {
            "id": m.id,
            "label": m.label,
            "provider": m.provider,
            "available": m.available,
            "envKey": m.env_key,
        }
        for m in list_models()
    ]


@app.get("/api/workflows")
def get_workflow(
    id: str = Query("default"),
    format: str | None = Query(None),
):
    if format == "yaml":
        yaml_text = export_workflow_yaml(id)
        return PlainTextResponse(
            yaml_text,
            media_type="text/yaml; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{id}.yaml"',
            },
        )
    return load_workflow(id)


@app.post("/api/workflows")
def post_workflow(body: Workflow) -> Workflow:
    return save_workflow(body)


@app.get("/api/runs")
def get_runs():
    return list_runs()


@app.post("/api/runs")
def post_run(body: StartRunBody | None = None):
    workflow_id = (body.workflowId if body else None) or "default"
    return start_run(workflow_id)


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/api/runs/{run_id}/resume")
def post_resume(run_id: str, body: HumanGateDecision):
    run = resume_run(run_id, body)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.post("/api/runs/{run_id}/stop")
def post_stop(run_id: str):
    run = stop_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
