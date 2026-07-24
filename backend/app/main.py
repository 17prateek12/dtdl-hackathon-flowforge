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


@app.get("/api/codebase/search")
def get_codebase_search(
    query: str,
    top_k: int = 5,
    runId: str | None = Query(None),
    repoPath: str | None = Query(None)
):
    import json
    from app.agents.workspace import get_workspace
    ws = get_workspace()
    repo_dir = ws.root
    
    if repoPath:
        from app.agents.workspace import RepoWorkspace
        ws = RepoWorkspace.create(target_repo=repoPath)
        repo_dir = ws.root
    elif runId:
        run = load_run(runId)
        if run and run.targetRepo:
            from app.agents.workspace import RepoWorkspace
            ws = RepoWorkspace.create(target_repo=run.targetRepo)
            repo_dir = ws.root
            
    index_file = repo_dir / ".flowforge" / "vector_index.json"
    
    try:
        from app.orchestrator.search import hybrid_search
        results = hybrid_search(repo_dir, index_file, query, top_k)
        serializable = []
        for r in results:
            serializable.append({
                "path": r["path"],
                "text": r["text"],
                "score": round(r["score"], 4),
                "bm25": round(r["bm25"], 4),
                "semantic": round(r["semantic"], 4)
            })
        return {"query": query, "results": serializable}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@app.get("/api/codebase/review")
def get_codebase_review(
    runId: str | None = Query(None),
    model: str | None = Query(None),
    repoPath: str | None = Query(None)
):
    import json
    from pathlib import Path
    from app.agents.workspace import get_workspace
    ws = get_workspace()
    repo_dir = ws.root
    
    if repoPath:
        from app.agents.workspace import RepoWorkspace
        ws = RepoWorkspace.create(target_repo=repoPath)
        repo_dir = ws.root
    elif runId:
        run = load_run(runId)
        if run and run.targetRepo:
            from app.agents.workspace import RepoWorkspace
            ws = RepoWorkspace.create(target_repo=run.targetRepo)
            repo_dir = ws.root

    try:
        from app.orchestrator.crawler import generate_codebase_outline
        
        outline = generate_codebase_outline(repo_dir)
        source_contents = {}
        for f in outline.get("files", []):
            path_str = f["path"]
            ext = Path(path_str).suffix.lower()
            if ext in {".js", ".ts", ".py"} and f["sizeBytes"] < 15000:
                abs_path = repo_dir / path_str
                if abs_path.exists():
                    try:
                        source_contents[path_str] = abs_path.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        pass
                        
        context = {
            "structure": outline,
            "source_files": source_contents
        }
        
        system_prompt = (
            "You are a Senior Staff Architect and Security Auditor. Perform a thorough review of the provided codebase.\n"
            "Analyze:\n"
            "1. Architecture and design patterns.\n"
            "2. Potential security issues (lack of validation, unsafe imports, secrets, etc.).\n"
            "3. Code quality, potential bugs, and readability.\n"
            "4. Recommendations and a concrete list of next actions.\n\n"
            "Format your output in professional Markdown with bullet points, emojis, and clear headings. Keep it actionable."
        )
        
        user_prompt = f"Here is the codebase outline and contents:\n\n{json.dumps(context, indent=2)[:40000]}"
        
        from app.agents.llm import chat_text
        report = chat_text(model=model, system=system_prompt, user=user_prompt)
        
        return {
            "repoPath": repo_dir.as_posix(),
            "outline": outline,
            "report": report
        }
    except Exception as e:
        err_str = str(e)
        if "OPENAI_API_KEY" in err_str or "key" in err_str.lower() or "unauthorized" in err_str.lower():
            report_lines = [
                "# 📊 Local Codebase Quality & Architecture Review (Fallback)",
                "",
                "This report was generated using local static analysis rules because no LLM API keys are configured.",
                "",
                "## 📂 Structure Overview",
                f"- **Repository Path**: `{repo_dir.as_posix()}`",
                f"- **Total Files Scanned**: {len(outline.get('files', []))}",
                ""
            ]
            
            warnings = []
            has_tests = False
            for f in outline.get("files", []):
                p = f["path"]
                if "test" in p.lower():
                    has_tests = True
                if f["sizeBytes"] > 50000:
                    warnings.append(f"⚠️ `{p}` is large ({round(f['sizeBytes']/1024, 1)} KB). Consider modularizing.")
                if "secret" in p.lower() or "password" in p.lower() or p.endswith(".env"):
                    warnings.append(f"🔒 Security: Check if `{p}` contains hardcoded secrets or credentials.")
            
            if not has_tests:
                warnings.append("⚠️ **No test files found**: Consider adding a test suite to verify correctness.")
                
            report_lines.append("## 🔍 Static Analysis Alerts")
            if warnings:
                for w in warnings:
                    report_lines.append(f"- {w}")
            else:
                report_lines.append("- ✅ No immediate critical issues detected in filename/structure analysis.")
            
            report_lines.append("")
            report_lines.append("## 💡 Architectural Recommendations")
            report_lines.append("1. **Verify environment configs**: Keep configuration keys outside source files.")
            report_lines.append("2. **Add Unit Testing**: Ensure every controller has a corresponding `.test.js` or `test_*.py` file.")
            report_lines.append("3. **Input Validation**: Ensure user parameters are sanitized before queries are executed.")
            
            report = "\n".join(report_lines)
            return {
                "repoPath": repo_dir.as_posix(),
                "outline": outline,
                "report": report
            }
        else:
            raise HTTPException(status_code=500, detail=f"Codebase review failed: {e}")
