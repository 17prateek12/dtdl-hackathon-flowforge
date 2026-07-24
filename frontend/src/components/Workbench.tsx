"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { HumanGateModal } from "@/components/HumanGateModal";
import {
  LoopNode,
  type LoopFlowNode,
} from "@/components/LoopNode";
import { NodeInspector, type ModelOption } from "@/components/NodeInspector";
import { NodeLibrary } from "@/components/NodeLibrary";
import { RunConsole } from "@/components/RunConsole";
import type { RunRecord, Workflow, WorkflowNode } from "@/lib/types";

const nodeTypes = { loopNode: LoopNode };

function statusLabel(status: RunRecord["status"] | "idle") {
  switch (status) {
    case "running":
      return "Running";
    case "waiting_for_human":
      return "Waiting for human";
    case "succeeded":
      return "Succeeded";
    case "stopped":
      return "Stopped Safely";
    case "failed":
      return "Failed";
    default:
      return "Idle";
  }
}

export function Workbench() {
  return (
    <ReactFlowProvider>
      <WorkbenchInner />
    </ReactFlowProvider>
  );
}

function WorkbenchInner() {
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>("criteria");
  const [run, setRun] = useState<RunRecord | null>(null);
  const [consoleCollapsed, setConsoleCollapsed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);

  useEffect(() => {
    void (async () => {
      const res = await fetch("/api/workflows");
      const data = (await res.json()) as Workflow;
      setWorkflow(data);
    })();
    void (async () => {
      try {
        const res = await fetch("/api/models");
        if (res.ok) setModels((await res.json()) as ModelOption[]);
      } catch {
        /* optional */
      }
    })();
  }, []);

  useEffect(() => {
    if (!run) return;
    if (
      run.status !== "running" &&
      run.status !== "waiting_for_human"
    ) {
      return;
    }
    const handle = setInterval(async () => {
      const res = await fetch(`/api/runs/${run.id}`);
      if (!res.ok) return;
      const next = (await res.json()) as RunRecord;
      setRun(next);
    }, 800);
    return () => clearInterval(handle);
  }, [run?.id, run?.status]);

  const nodes: LoopFlowNode[] = useMemo(() => {
    if (!workflow) return [];
    return workflow.nodes.map((n) => ({
      id: n.id,
      type: "loopNode" as const,
      position: n.position,
      data: {
        ...n.data,
        status: run?.nodeStatuses[n.id] || "idle",
      },
    }));
  }, [workflow, run]);

  const edges: Edge[] = useMemo(() => workflow?.edges ?? [], [workflow]);

  const selectedNode: WorkflowNode | null = useMemo(() => {
    if (!workflow || !selectedId) return null;
    return workflow.nodes.find((n) => n.id === selectedId) ?? null;
  }, [workflow, selectedId]);

  const onNodeChange = useCallback(
    (nodeId: string, patch: Partial<WorkflowNode["data"]>) => {
      setWorkflow((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: prev.nodes.map((n) =>
            n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n,
          ),
        };
      });
    },
    [],
  );

  const saveWorkflow = async () => {
    if (!workflow) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(workflow),
      });
      if (!res.ok) throw new Error("Failed to save workflow");
      const saved = (await res.json()) as Workflow;
      setWorkflow(saved);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const exportYaml = () => {
    window.open("/api/workflows?format=yaml", "_blank");
  };

  const startRun = async () => {
    setBusy(true);
    setError(null);
    try {
      await saveWorkflow();
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflowId: workflow?.id || "default" }),
      });
      if (!res.ok) throw new Error("Failed to start run");
      const next = (await res.json()) as RunRecord;
      setRun(next);
      setConsoleCollapsed(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const stopRun = async () => {
    if (!run) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/runs/${run.id}/stop`, { method: "POST" });
      if (res.ok) setRun((await res.json()) as RunRecord);
    } finally {
      setBusy(false);
    }
  };

  const onGateDecide = async (payload: {
    action: "approve" | "reject" | "edit";
    editedText?: string;
    feedback?: string;
  }) => {
    if (!run) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/runs/${run.id}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Failed to resume run");
      setRun((await res.json()) as RunRecord);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const runStatus = run?.status ?? "idle";

  return (
    <div className="flex h-screen flex-col bg-[#f4f6fb] text-slate-900">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
            LF
          </div>
          <div>
            <div className="text-sm font-semibold tracking-tight">
              LoopForge{" "}
              <span className="font-normal text-slate-500">
                AI Coding Workbench
              </span>
            </div>
            <div className="text-xs text-slate-500">
              {workflow?.name || "Loading…"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="mr-2 hidden text-xs text-slate-500 sm:inline">
            {statusLabel(runStatus)}
            {run ? ` · Attempt ${run.attempt}/${run.maxAttempts}` : ""}
          </span>
          <button
            type="button"
            onClick={() => void saveWorkflow()}
            disabled={busy || !workflow}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
          >
            Save
          </button>
          <button
            type="button"
            onClick={exportYaml}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
          >
            Export YAML
          </button>
          <button
            type="button"
            onClick={() => void startRun()}
            disabled={
              busy ||
              !workflow ||
              runStatus === "running" ||
              runStatus === "waiting_for_human"
            }
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            Run
          </button>
          <button
            type="button"
            onClick={() => void stopRun()}
            disabled={
              busy ||
              !run ||
              (runStatus !== "running" && runStatus !== "waiting_for_human")
            }
            className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-1.5 text-sm font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50"
          >
            Stop
          </button>
        </div>
      </header>

      {error && (
        <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <NodeLibrary />
        <div className="relative min-w-0 flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            nodesDraggable
            nodesConnectable={false}
            elementsSelectable
            onNodeClick={(_, node) => setSelectedId(node.id)}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={18} size={1} color="#e2e8f0" />
            <Controls />
            <MiniMap
              pannable
              zoomable
              className="!bg-white !border !border-slate-200"
            />
          </ReactFlow>
        </div>
        <NodeInspector
          node={selectedNode}
          models={models}
          onChange={onNodeChange}
        />
      </div>

      <RunConsole
        run={run}
        collapsed={consoleCollapsed}
        onToggle={() => setConsoleCollapsed((v) => !v)}
        selectedNodeId={selectedId}
      />

      <HumanGateModal
        gate={run?.pendingGate ?? null}
        busy={busy}
        onDecide={(p) => void onGateDecide(p)}
      />
    </div>
  );
}
