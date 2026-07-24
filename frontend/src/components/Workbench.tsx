"use client";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  addEdge,
  type Edge,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { HumanGateModal } from "@/components/HumanGateModal";
import {
  LoopNode,
  type LoopFlowNode,
} from "@/components/LoopNode";
import { NodeInspector } from "@/components/NodeInspector";
import { NodeLibrary } from "@/components/NodeLibrary";
import { RunConsole } from "@/components/RunConsole";
import type { RunRecord, Workflow, WorkflowNode, NodeType } from "@/lib/types";

const nodeTypes = { loopNode: LoopNode };

const DEFAULT_TEMPLATE_WORKFLOW: Workflow = {
  id: "default",
  name: "Default Coding Loop",
  maxAttempts: 3,
  nodes: [
    {
      id: "input",
      type: "loopNode",
      position: { x: 40, y: 180 },
      data: {
        label: "Coding Objective",
        description: "Objective and constraints",
        nodeType: "input",
        objective: "",
        constraints: "",
      },
    },
    {
      id: "criteria",
      type: "loopNode",
      position: { x: 280, y: 80 },
      data: {
        label: "Success Criteria Agent",
        description: "Generate measurable success criteria",
        nodeType: "agent",
        role: "successCriteria",
        instructions:
          "Convert the engineering objective into measurable success criteria. Ensure the criteria are specific, verifiable and prioritized.",
        model: "gpt-4o-mini",
        tools: ["Repo Reader", "Search"],
        maxRetries: 2,
        timeout: 300,
      },
    },
    {
      id: "gate-criteria",
      type: "loopNode",
      position: { x: 540, y: 80 },
      data: {
        label: "Human Gate (Review)",
        description: "Review and approve success criteria",
        nodeType: "humanGate",
      },
    },
    {
      id: "planning",
      type: "loopNode",
      position: { x: 280, y: 280 },
      data: {
        label: "Planning Agent",
        description: "Create / revise implementation plan",
        nodeType: "agent",
        role: "planning",
        instructions:
          "Create or revise a concrete implementation plan grounded in real files in the repository. Name modules, order of work, and risks.",
        model: "gpt-4o-mini",
        tools: ["Repo Reader", "Search"],
        maxRetries: 2,
        timeout: 300,
      },
    },
    {
      id: "execution",
      type: "loopNode",
      position: { x: 540, y: 280 },
      data: {
        label: "Execution Agent",
        description: "Implement changes in the codebase",
        nodeType: "agent",
        role: "execution",
        instructions:
          "Implement the planned changes in the repository. Follow coding standards and existing patterns. Prefer minimal diffs.",
        model: "gpt-4o-mini",
        tools: ["File Editor", "Search", "Git", "Terminal"],
        maxRetries: 2,
        timeout: 300,
      },
    },
    {
      id: "command",
      type: "loopNode",
      position: { x: 800, y: 280 },
      data: {
        label: "Run Tests",
        description: "npm test",
        nodeType: "command",
        command: "npm test",
        timeout: 120,
      },
    },
    {
      id: "validation",
      type: "loopNode",
      position: { x: 1060, y: 280 },
      data: {
        label: "Validation Agent",
        description: "Validate changes and provide evidence",
        nodeType: "validator",
        role: "validation",
        instructions:
          "Summarize validation evidence. Do not override deterministic check results.",
        fileChecks: ["src/app.js"],
        model: "gpt-4o-mini",
        maxRetries: 1,
        timeout: 120,
      },
    },
    {
      id: "decision",
      type: "loopNode",
      position: { x: 1320, y: 280 },
      data: {
        label: "Decision",
        description: "Pass / Fail?",
        nodeType: "decision",
      },
    },
    {
      id: "gate-final",
      type: "loopNode",
      position: { x: 1320, y: 80 },
      data: {
        label: "Human Gate (Approve)",
        description: "Approve completion",
        nodeType: "humanGate",
      },
    },
    {
      id: "success",
      type: "loopNode",
      position: { x: 1580, y: 40 },
      data: {
        label: "Success",
        description: "Task Successful",
        nodeType: "success",
      },
    },
    {
      id: "stop",
      type: "loopNode",
      position: { x: 1580, y: 200 },
      data: {
        label: "Stop",
        description: "Stopped Safely",
        nodeType: "stop",
      },
    },
  ],
  edges: [
    { id: "e-input-criteria", source: "input", target: "criteria" },
    {
      id: "e-criteria-gate",
      source: "criteria",
      target: "gate-criteria",
      sourceHandle: "success",
    },
    {
      id: "e-gate-planning",
      source: "gate-criteria",
      target: "planning",
      sourceHandle: "approve",
    },
    {
      id: "e-gate-stop1",
      source: "gate-criteria",
      target: "stop",
      sourceHandle: "reject",
      label: "reject",
      style: { stroke: "#ef4444", strokeDasharray: "6 4" },
    },
    { id: "e-planning-exec", source: "planning", target: "execution" },
    { id: "e-exec-cmd", source: "execution", target: "command" },
    { id: "e-cmd-val", source: "command", target: "validation" },
    { id: "e-val-decision", source: "validation", target: "decision" },
    {
      id: "e-decision-fail",
      source: "decision",
      target: "planning",
      sourceHandle: "fail",
      label: "fail → retry",
      style: { stroke: "#ef4444", strokeDasharray: "6 4" },
      animated: true,
    },
    {
      id: "e-decision-pass",
      source: "decision",
      target: "gate-final",
      sourceHandle: "pass",
      label: "pass",
      style: { stroke: "#22c55e", strokeDasharray: "6 4" },
    },
    {
      id: "e-final-success",
      source: "gate-final",
      target: "success",
      sourceHandle: "approve",
      style: { stroke: "#22c55e" },
    },
    {
      id: "e-final-stop",
      source: "gate-final",
      target: "stop",
      sourceHandle: "reject",
      label: "reject",
      style: { stroke: "#ef4444", strokeDasharray: "6 4" },
    },
  ],
};

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
  const reactFlow = useReactFlow();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>("criteria");
  const [run, setRun] = useState<RunRecord | null>(null);
  const [consoleCollapsed, setConsoleCollapsed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<any[]>([]);

  useEffect(() => {
    void (async () => {
      try {
        const res = await fetch("/api/workflows");
        if (!res.ok) {
          throw new Error(`Failed to load workflow (${res.status})`);
        }
        const data = (await res.json()) as Workflow;
        if (!Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
          throw new Error("Invalid workflow response from server");
        }
        setWorkflow(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    void (async () => {
      try {
        const res = await fetch("/api/models");
        if (res.ok) setModels((await res.json()) as any[]);
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
    if (!workflow?.nodes) return [];
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
    if (!workflow?.nodes || !selectedId) return null;
    return workflow.nodes.find((n) => n.id === selectedId) ?? null;
  }, [workflow, selectedId]);

  const onNodeChange = useCallback(
    (nodeId: string, patch: Partial<WorkflowNode["data"]>) => {
      setWorkflow((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: (prev.nodes ?? []).map((n) =>
            n.id === nodeId ? { ...n, data: { ...n.data, ...patch } } : n,
          ),
        };
      });
    },
    [],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      setWorkflow((prev) => {
        if (!prev) return prev;
        const newEdge = {
          id: `${connection.source}-${connection.target}`,
          source: connection.source || "",
          target: connection.target || "",
          sourceHandle: connection.sourceHandle,
          targetHandle: connection.targetHandle,
          label: undefined,
          style: undefined,
          animated: undefined,
        };
        return {
          ...prev,
          edges: addEdge(newEdge, prev.edges ?? []),
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

  const onLoadTemplate = useCallback(() => {
    setWorkflow(DEFAULT_TEMPLATE_WORKFLOW);
    setSelectedId("input");
    setRun(null);
  }, []);

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    
    try {
      const data = e.dataTransfer.getData("application/json");
      if (!data) return;
      
      const { type } = JSON.parse(data) as { type: NodeType };
      if (!type || !workflow) return;

      const position = reactFlow.screenToFlowPosition({
        x: e.clientX,
        y: e.clientY,
      });

      // Generate unique ID for the new node
      const nodeId = `${type}-${Date.now()}`;
      
      // Create default node data based on type
      const nodeData: WorkflowNode["data"] = {
        label: type.charAt(0).toUpperCase() + type.slice(1),
        description: "",
        nodeType: type,
        role: undefined,
        instructions: undefined,
        model: undefined,
        tools: undefined,
        maxRetries: undefined,
        timeout: undefined,
        command: undefined,
        fileChecks: undefined,
        objective: undefined,
        constraints: undefined,
      };

      // Create new node
      const newNode: WorkflowNode = {
        id: nodeId,
        type: "loopNode",
        position,
        data: nodeData,
      };

      // Add to workflow
      setWorkflow((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          nodes: [...(prev.nodes ?? []), newNode],
        };
      });

      // Select the new node
      setSelectedId(nodeId);
    } catch (err) {
      console.error("Drop error:", err);
    }
  };

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
        <NodeLibrary onLoadTemplate={onLoadTemplate} />
        <div className="relative min-w-0 flex-1" onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            nodesDraggable
            nodesConnectable
            elementsSelectable
            onNodeClick={(_, node) => setSelectedId(node.id)}
            onConnect={onConnect}
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
        <NodeInspector node={selectedNode} onChange={onNodeChange} />
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
