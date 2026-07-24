This project belongs to DTDL Hackathon - Team Flow Forge 

DevFlow AI lets an engineer define an outcome, not micromanage prompts. Four configurable agent roles — Success Criteria, Planning, Execution, and Validation — work through a real coding task on a visual node canvas, with every attempt, retry, and piece of evidence inspectable and bounded by human approval gates.

Built for Track B: Loop Engineering Platform.
# LoopForge

Control plane for long-running AI coding loops (Track B MVP).

## Layout

```
frontend/     # Next.js UI (React Flow workbench) — proxies /api → Python
backend/      # Python FastAPI orchestrator, agents, validation, persistence
demo-repo/    # Sandboxed coding-loop target (git baseline preserved)
data/         # Shared workflows/ + runs/ JSON persistence
docs/         # Problem statement PDF, mockups, plan notes
```

Engineers define an objective, agents propose success criteria, a human gate confirms the contract, then Planning → Execution → Command tests → Validation iterate within a retry budget. Acceptance is **deterministic** (exit codes / file checks) — an LLM never flips a red check green.

## Quick start

```bash
cp .env.example .env
npm run install:all   # frontend deps + backend/.venv

# terminal 1 — Python API
npm run dev:api

# terminal 2 — Next.js UI (proxies /api → :8000)
npm run dev:web
```

Or start both: `npm run dev`.

Open [http://localhost:3000](http://localhost:3000).  
API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Environment

Keep a single **root** `.env` (see `.env.example`). The Python backend loads it via `backend/app/paths.py`. The Next.js app loads the same file from `frontend/next.config.ts` so `LOOPFORGE_API_ORIGIN` stays in sync (default `http://127.0.0.1:8000`).

By default `MOCK_AGENTS=true` runs without API keys. Attempt 1 intentionally skips the code change so you can watch validation fail and retry; attempt 2 applies the `/health` fix.

Three model providers are supported (pick per agent in the Node Inspector):

| Provider | Env key | Default model |
|----------|---------|---------------|
| OpenAI | `OPENAI_API_KEY` | `OPENAI_MODEL=gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL=claude-sonnet-4-5` |
| Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL=gemini-2.0-flash` |

```env
MOCK_AGENTS=false
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

`GET /api/models` lists configured models and whether each key is present.
## Backend layout (`backend/app/`)

| Path | Role |
|------|------|
| `main.py` | FastAPI routes (`/api/workflows`, `/api/runs`, …) |
| `orchestrator/loop.py` | Graph walker, human gates, retry budget, rollback |
| `orchestrator/validation.py` | Deterministic command/file acceptance |
| `agents/runner.py` | Criteria / plan / execute / summarize (mock or OpenAI) |
| `agents/tools.py` | Sandboxed FS + shell + git for `demo-repo/` |
| `store/*` | JSON persistence under `data/` |

## Demo flow (~5–7 min)

1. Confirm the coding objective on the **Input** node (add `GET /health`).
2. Click **Run**.
3. Review generated success criteria in the Human Gate → **Approve** (or edit).
4. Watch Planning → Execution → `npm test` → Validation.
5. On attempt 1 (mock), validation fails; loop returns to Planning.
6. Attempt 2 implements `demo-repo/src/app.js` and tests pass.
7. Final Human Gate → **Approve** → Task Successful.
8. Inspect Run Console (messages, files changed, validation evidence).
9. **Export YAML** for the workflow config-as-code.

## Notes

- Frontend has no Next.js API routes — `/api/*` is rewritten to the Python backend
- Workflows: `data/workflows/` · Runs: `data/runs/`
- Agent tools are sandboxed to `demo-repo/`
