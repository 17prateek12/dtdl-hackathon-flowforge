"use client";

import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  useNodesState,
  useEdgesState,
  type Edge,
  type Connection,
  type NodeChange,
  type EdgeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { HumanGateModal } from "@/components/HumanGateModal";
import { RAGCodebaseModal } from "@/components/RAGCodebaseModal";
import { Database } from "lucide-react";
import {
  LoopNode,
  type LoopFlowNode,
} from "@/components/LoopNode";
import { NodeInspector } from "@/components/NodeInspector";
import { NodeLibrary } from "@/components/NodeLibrary";
import { RunConsole } from "@/components/RunConsole";
import { LeftPanel } from "@/components/LeftPanel";
import type { RunRecord, Workflow, WorkflowNode, NodeType, AgentRole } from "@/lib/types";


const nodeTypes = { loopNode: LoopNode };

const DEFAULT_TEMPLATE_WORKFLOW: Workflow = {
  id: "default",
  name: "Default Coding Loop",
  maxAttempts: 3,
  nodes: [
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
        model: "mistral-small-latest",
        tools: ["Repo Reader", "Search"],
        maxRetries: 2,
        timeout: 300,
        objective: "",
        constraints: "",
        targetRepo: "",
        mainTargetFile: "",
        validateCommand: "",
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
        model: "mistral-small-latest",
        tools: ["Repo Reader", "Search"],
        maxRetries: 2,
        timeout: 300,
      },
    },
    {
      id: "gate-plan",
      type: "loopNode",
      position: { x: 540, y: 280 },
      data: {
        label: "Human Gate (Review Plan)",
        description: "Review and approve implementation plan",
        nodeType: "humanGate",
      },
    },
    {
      id: "execution",
      type: "loopNode",
      position: { x: 800, y: 280 },
      data: {
        label: "Execution Agent",
        description: "Implement changes in the codebase",
        nodeType: "agent",
        role: "execution",
        instructions:
          "Implement the planned changes in the repository. Follow coding standards and existing patterns. Prefer minimal diffs.",
        model: "mistral-small-latest",
        tools: ["File Editor", "Search", "Git", "Terminal"],
        maxRetries: 2,
        timeout: 300,
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
        fileChecks: [],
        model: "mistral-small-latest",
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
    { id: "e-planning-gate", source: "planning", target: "gate-plan" },
    {
      id: "e-gate-exec",
      source: "gate-plan",
      target: "execution",
      sourceHandle: "approve",
    },
    { id: "e-exec-val", source: "execution", target: "validation" },
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
      target: "success",
      sourceHandle: "pass",
      label: "pass",
      style: { stroke: "#22c55e", strokeDasharray: "6 4" },
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
  const [nodes, setNodes, onNodesChange] = useNodesState<LoopFlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const onDeleteNode = useCallback((nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    setSelectedId((prev) => (prev === nodeId ? null : prev));
  }, [setNodes, setEdges, setSelectedId]);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [consoleCollapsed, setConsoleCollapsed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [models, setModels] = useState<any[]>([]);
  const [isRagModalOpen, setIsRagModalOpen] = useState(false);
  const [runs, setRuns] = useState<RunRecord[]>([]);

  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch("/api/runs");
      if (res.ok) {
        const data = (await res.json()) as RunRecord[];
        setRuns(data);
      }
    } catch (err) {
      console.warn("Failed to fetch runs:", err);
    }
  }, []);

  const onCreatePipeline = useCallback(() => {
    const newWorkflow: Workflow = {
      id: `workflow-${Date.now()}`,
      name: "New Pipeline",
      maxAttempts: 3,
      nodes: [],
      edges: [],
    };
    setWorkflow(newWorkflow);
    setNodes([]);
    setEdges([]);
    setSelectedId(null);
    setRun(null);
  }, [setNodes, setEdges]);


  useEffect(() => {
    void fetchRuns();
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

        // Restore previously selected codebase from localStorage after refresh
        if (typeof window !== "undefined") {
          const savedRepo = localStorage.getItem("flowforge_selected_repo");
          const savedFilesRaw = localStorage.getItem("flowforge_selected_files");
          let savedFiles: string[] | null = null;
          if (savedFilesRaw) {
            try { savedFiles = JSON.parse(savedFilesRaw); } catch { }
          }

          if (savedRepo || savedFiles) {
            data.nodes = data.nodes.map((n) => {
              if (n.id === "criteria") {
                return {
                  ...n,
                  data: {
                    ...n.data,
                    targetRepo: savedRepo || n.data.targetRepo,
                    targetFiles: savedFiles || n.data.targetFiles,
                  },
                };
              }
              return n;
            });
          }
        }

        setWorkflow(data);
        setNodes(data.nodes.map((n) => ({
          id: n.id,
          type: "loopNode" as const,
          position: n.position,
          data: {
            ...n.data,
            status: run?.nodeStatuses[n.id] || "idle",
            onDelete: onDeleteNode,
          },
        })));
        setEdges(data.edges.map((e) => ({
          ...e,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
        })));
        setError(null);
      } catch (err) {
        console.warn("Workflow fetch error, using default template:", err);
        const data = JSON.parse(JSON.stringify(DEFAULT_TEMPLATE_WORKFLOW)) as Workflow;
        if (typeof window !== "undefined") {
          const savedRepo = localStorage.getItem("flowforge_selected_repo");
          const savedFilesRaw = localStorage.getItem("flowforge_selected_files");
          let savedFiles: string[] | null = null;
          if (savedFilesRaw) {
            try { savedFiles = JSON.parse(savedFilesRaw); } catch { }
          }
          if (savedRepo || savedFiles) {
            data.nodes = data.nodes.map((n) => {
              if (n.id === "criteria") {
                return {
                  ...n,
                  data: {
                    ...n.data,
                    targetRepo: savedRepo || n.data.targetRepo,
                    targetFiles: savedFiles || n.data.targetFiles,
                  },
                };
              }
              return n;
            });
          }
        }
        setWorkflow(data);
        setNodes(data.nodes.map((n) => ({
          id: n.id,
          type: "loopNode" as const,
          position: n.position,
          data: {
            ...n.data,
            status: "idle",
            onDelete: onDeleteNode,
          },
        })));
        setEdges(data.edges.map((e) => ({
          ...e,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
        })));
        setError(null);
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

  // Load any pipeline by ID from the backend
  const loadPipelineById = async (workflowId: string) => {
    try {
      const res = await fetch(`/api/workflows?id=${encodeURIComponent(workflowId)}`);
      if (!res.ok) throw new Error("Failed to load pipeline");
      const data = (await res.json()) as Workflow;
      setWorkflow(data);
      setNodes(
        data.nodes.map((n) => ({
          id: n.id,
          type: "loopNode" as const,
          position: n.position,
          data: { ...n.data, status: "idle", onDelete: onDeleteNode },
        }))
      );
      setEdges(
        data.edges.map((e) => ({
          ...e,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
        }))
      );
      setSelectedId(null);
      setRun(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    if (!run) return;
    if (
      run.status !== "running" &&
      run.status !== "waiting_for_human"
    ) {
      void fetchRuns();
      return;
    }
    const handle = setInterval(async () => {
      const res = await fetch(`/api/runs/${run.id}`);
      if (!res.ok) return;
      const next = (await res.json()) as RunRecord;
      setRun(next);
      if (next.status !== "running" && next.status !== "waiting_for_human") {
        void fetchRuns();
      }
    }, 800);
    return () => clearInterval(handle);
  }, [run?.id, run?.status, fetchRuns]);

  useEffect(() => {
    if (!run) {
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: { ...n.data, status: "idle" },
        })),
      );
      return;
    }
    setNodes((nds) =>
      nds.map((n) => {
        const nextStatus = run.nodeStatuses[n.id] || "idle";
        if (n.data.status !== nextStatus) {
          return {
            ...n,
            data: { ...n.data, status: nextStatus },
          };
        }
        return n;
      }),
    );
  }, [run, setNodes]);

  const selectedNode: WorkflowNode | null = useMemo(() => {
    if (!nodes || !selectedId) return null;
    const found = nodes.find((n) => n.id === selectedId);
    if (!found) return null;
    return {
      id: found.id,
      type: found.type || "loopNode",
      position: found.position,
      data: found.data as unknown as WorkflowNode["data"],
    };
  }, [nodes, selectedId]);

  const onNodeChange = useCallback(
    (nodeId: string, patch: Partial<WorkflowNode["data"]>) => {
      if (nodeId === "criteria") {
        if (patch.targetRepo !== undefined && typeof window !== "undefined") {
          localStorage.setItem("flowforge_selected_repo", patch.targetRepo || "");
        }
        if (patch.targetFiles !== undefined && typeof window !== "undefined") {
          localStorage.setItem("flowforge_selected_files", JSON.stringify(patch.targetFiles || []));
        }
      }
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId
            ? {
                ...n,
                data: {
                  ...n.data,
                  ...patch,
                } as any,
              }
            : n,
        ),
      );
    },
    [setNodes],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const newEdge: Edge = {
        id: `${connection.source}-${connection.target}`,
        source: connection.source || "",
        target: connection.target || "",
        sourceHandle: connection.sourceHandle ?? undefined,
        targetHandle: connection.targetHandle ?? undefined,
      };
      setEdges((eds) => addEdge(newEdge, eds));
    },
    [setEdges],
  );

  const onEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      if (window.confirm("Delete this connection between nodes?")) {
        setEdges((eds) => eds.filter((e) => e.id !== edge.id));
      }
    },
    [setEdges],
  );


  const saveWorkflow = async () => {
    if (!workflow) return;
    const currentWorkflow: Workflow = {
      ...workflow,
      nodes: nodes.map((n) => ({
        id: n.id,
        type: n.type || "loopNode",
        position: n.position,
        data: n.data as unknown as WorkflowNode["data"],
      })),
      edges: edges.map((e) => ({
        id: e.id,
        source: e.source,
        target: e.target,
        sourceHandle: e.sourceHandle ?? null,
        targetHandle: e.targetHandle ?? null,
        label: typeof e.label === "string" ? e.label : undefined,
        style: e.style as any,
        animated: e.animated,
      })),
    };
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentWorkflow),
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
    // Validate that agent and validator fields are not empty
    for (const node of nodes) {
      const d = node.data;
      if (!d) continue;

      const isAgentOrValidator = d.nodeType === "agent" || d.nodeType === "validator";
      if (isAgentOrValidator) {
        if (!d.label || !d.label.trim()) {
          const msg = `We cannot run the pipeline because the agent having field 'Name' is empty.`;
          setValidationError(msg);
          return;
        }
        if (!d.instructions || !d.instructions.trim()) {
          const msg = `We cannot run the pipeline because agent '${d.label}' having field 'Instructions' is empty.`;
          setValidationError(msg);
          return;
        }
        if (!d.model || !d.model.trim()) {
          const msg = `We cannot run the pipeline because agent '${d.label}' having field 'Model' is empty.`;
          setValidationError(msg);
          return;
        }
        if (d.role === "successCriteria") {
          if (!d.objective || !d.objective.trim()) {
            const msg = `We cannot run the pipeline because Success Criteria Agent having field 'Objective' is empty.`;
            setValidationError(msg);
            return;
          }
        }
      }

      if (d.nodeType === "command") {
        if (!d.command || !d.command.trim()) {
          const msg = `We cannot run the pipeline because command node '${d.label}' having field 'Command' is empty.`;
          setValidationError(msg);
          return;
        }
      }
    }

    setBusy(true);
    setError(null);
    setValidationError(null);
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
      void fetchRuns();
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
      if (res.ok) {
        setRun((await res.json()) as RunRecord);
        void fetchRuns();
      }
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
    setNodes(DEFAULT_TEMPLATE_WORKFLOW.nodes.map((n) => ({
      id: n.id,
      type: "loopNode" as const,
      position: n.position,
      data: {
        ...n.data,
        status: "idle",
        onDelete: onDeleteNode,
      },
    })));
    setEdges(DEFAULT_TEMPLATE_WORKFLOW.edges.map((e) => ({
      ...e,
      sourceHandle: e.sourceHandle ?? undefined,
      targetHandle: e.targetHandle ?? undefined,
    })));
    setSelectedId(null);
    setRun(null);
  }, [setNodes, setEdges]);

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();

    try {
      const data = e.dataTransfer.getData("application/json");
      if (!data) return;

      const { type, role } = JSON.parse(data) as { type: NodeType; role?: AgentRole };
      if (!type || !workflow) return;

      // Convert screen coordinates to flow coordinates
      const bounds = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const position = reactFlow.screenToFlowPosition({
        x: e.clientX - bounds.left,
        y: e.clientY - bounds.top,
      });

      // Generate unique ID for the new node
      const nodeId = role ? `${role}-${Date.now()}` : `${type}-${Date.now()}`;

      // Set label and defaults based on role and type
      let label = type.charAt(0).toUpperCase() + type.slice(1);
      let desc = "";
      let instructions: string | undefined = undefined;
      let tools: string[] | undefined = undefined;
      let fileChecks: string[] | undefined = undefined;

      if (type === "validator") {
        label = "Validation Agent";
        desc = "Validate changes and provide evidence";
        instructions = "Summarize validation evidence. Ensure the test files written by the execution agent are run and their output is captured. Do not override deterministic check results.";
        fileChecks = [];
      } else if (role === "successCriteria") {
        label = "Success Criteria Agent";
        desc = "Generate measurable success criteria";
        instructions = "Convert the engineering objective into measurable success criteria. Ensure the criteria are specific, verifiable and prioritized.";
        tools = ["Repo Reader", "Search"];
      } else if (role === "planning") {
        label = "Planning Agent";
        desc = "Create / revise implementation plan";
        instructions = "Create or revise a concrete implementation plan grounded in real files in the repository. Name modules, order of work, and risks.";
        tools = ["Repo Reader", "Search"];
      } else if (role === "execution") {
        label = "Execution Agent";
        desc = "Implement changes in the codebase";
        instructions = "Implement the planned changes in the repository. Follow coding standards and existing patterns. Prefer minimal diffs. IMPORTANT: You MUST write or update a test file (e.g., matching 'test_*.py' or '*.test.js') to check the functionality of the new/updated/deleted code changes. The test file must be runnable by the validation agent (e.g. via pytest or npm test).";
        tools = ["File Editor", "Search", "Git", "Terminal"];
      } else if (type === "command") {
        label = "Command";
        desc = "Run validation command";
      } else if (type === "decision") {
        label = "Decision";
        desc = "Pass / Fail?";
      } else if (type === "humanGate") {
        label = "Human Gate";
        desc = "Approve / reject gate";
      } else if (type === "success") {
        label = "Success";
        desc = "Task Successful";
      } else if (type === "stop") {
        label = "Stop";
        desc = "Stopped Safely";
      }

      // Create default node data based on type
      const nodeData: WorkflowNode["data"] = {
        label,
        description: desc,
        nodeType: type,
        role: role || (type === "validator" ? "validation" : undefined),
        instructions,
        model: (type === "agent" || type === "validator") ? "mistral-small-latest" : undefined,
        tools,
        maxRetries: (type === "agent" || type === "validator") ? 2 : undefined,
        timeout: type === "agent" ? 300 : type === "validator" ? 120 : undefined,
        command: type === "command" ? "npm test" : undefined,
        fileChecks,
        objective: role === "successCriteria" ? "" : undefined,
        constraints: role === "successCriteria" ? "" : undefined,
        targetRepo: role === "successCriteria" ? "" : undefined,
        mainTargetFile: role === "successCriteria" ? "" : undefined,
        validateCommand: role === "successCriteria" ? "" : undefined,
        targetFiles: role === "successCriteria" ? [] : undefined,
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
      setNodes((nds) => [
        ...nds,
        {
          id: newNode.id,
          type: "loopNode" as const,
          position: newNode.position,
          data: {
            ...newNode.data,
            status: "idle" as const,
            onDelete: onDeleteNode,
          },
        },
      ]);

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
          <button
            type="button"
            onClick={() => setIsRagModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-indigo-200 bg-indigo-50/70 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 transition"
          >
            <Database className="w-4 h-4 text-indigo-600" />
            Import Codebase
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
        <LeftPanel
          runs={runs}
          activeRun={run}
          onSelectRun={(selectedRun) => {
            setRun(selectedRun);
          }}
          onCreatePipeline={onCreatePipeline}
          onSavePipeline={saveWorkflow}
          onLoadPipeline={(id) => void loadPipelineById(id)}
          isSaving={busy}
        />
        <div className="relative min-w-0 flex-1" onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onEdgeClick={onEdgeClick}
            edgesReconnectable={true}
            edgesFocusable={true}
            deleteKeyCode={["Backspace", "Delete"]}
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
          </ReactFlow>
        </div>
        <NodeLibrary onLoadTemplate={onLoadTemplate} />
      </div>

      <NodeInspector
        node={selectedNode}
        onSave={(nodeId, patch) => {
          onNodeChange(nodeId, patch);
          setSelectedId(null);
        }}
        onCancel={() => setSelectedId(null)}
        models={models}
      />

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

      <RAGCodebaseModal
        isOpen={isRagModalOpen}
        onClose={() => setIsRagModalOpen(false)}
        targetRepo={
          (nodes?.find((n) => n.id === "criteria")?.data as any)?.targetRepo ||
          "./demo-repo"
        }
        targetFiles={
          (nodes?.find((n) => n.id === "criteria")?.data as any)?.targetFiles || []
        }
        onSelectTargetRepo={(repo) => {
          onNodeChange("criteria", { targetRepo: repo });
        }}
        onSelectTargetFiles={(files) => {
          onNodeChange("criteria", { targetFiles: files });
        }}
      />

      {validationError && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs">
          <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between">
              <div className="flex gap-2">
                <span className="text-rose-500 font-bold text-lg">⚠️</span>
                <div>
                  <h4 className="font-semibold text-slate-800 text-sm">Validation Error</h4>
                  <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                    {validationError}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setValidationError(null)}
                className="text-slate-400 hover:text-slate-600 p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setValidationError(null)}
                className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
