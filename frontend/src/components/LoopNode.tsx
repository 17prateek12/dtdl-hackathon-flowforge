"use client";

import {
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type { NodeStatus, NodeType, WorkflowNodeConfig } from "@/lib/types";

const TYPE_STYLES: Record<
  NodeType,
  { accent: string; badge: string; icon: string }
> = {
  input: { accent: "border-sky-400", badge: "bg-sky-100 text-sky-800", icon: "IN" },
  agent: {
    accent: "border-indigo-400",
    badge: "bg-indigo-100 text-indigo-800",
    icon: "AG",
  },
  command: {
    accent: "border-amber-400",
    badge: "bg-amber-100 text-amber-900",
    icon: "$",
  },
  validator: {
    accent: "border-violet-400",
    badge: "bg-violet-100 text-violet-800",
    icon: "VA",
  },
  decision: {
    accent: "border-fuchsia-400",
    badge: "bg-fuchsia-100 text-fuchsia-800",
    icon: "?",
  },
  humanGate: {
    accent: "border-orange-400",
    badge: "bg-orange-100 text-orange-900",
    icon: "HG",
  },
  success: {
    accent: "border-emerald-400",
    badge: "bg-emerald-100 text-emerald-800",
    icon: "OK",
  },
  stop: {
    accent: "border-rose-400",
    badge: "bg-rose-100 text-rose-800",
    icon: "ST",
  },
};

const STATUS_RING: Record<NodeStatus, string> = {
  idle: "",
  running: "ring-2 ring-blue-500 ring-offset-2 animate-pulse",
  completed: "ring-2 ring-emerald-400 ring-offset-1",
  failed: "ring-2 ring-rose-500 ring-offset-1",
  waiting: "ring-2 ring-amber-400 ring-offset-2",
  skipped: "opacity-50",
};

export type LoopNodeData = WorkflowNodeConfig & {
  status?: NodeStatus;
  [key: string]: unknown;
};
export type LoopFlowNode = Node<LoopNodeData, "loopNode">;

export function LoopNode({ data, selected }: NodeProps<LoopFlowNode>) {
  const style = TYPE_STYLES[data.nodeType];
  const status = data.status || "idle";
  const showHandles = data.nodeType !== "input";
  const isDecision = data.nodeType === "decision";
  const isGate = data.nodeType === "humanGate";
  const isTerminal =
    data.nodeType === "success" || data.nodeType === "stop";

  return (
    <div
      className={`min-w-[200px] max-w-[240px] rounded-xl border-2 bg-white px-3 py-2.5 shadow-sm ${style.accent} ${STATUS_RING[status]} ${selected ? "shadow-md" : ""}`}
    >
      {/* Every node except 'input' can be a target */}
      {data.nodeType !== "input" && (
        <Handle type="target" position={Position.Left} className="!bg-slate-400" />
      )}
      {data.nodeType === "input" && (
        <Handle type="source" position={Position.Right} className="!bg-slate-400" />
      )}

      <div className="flex items-start gap-2">
        <span
          className={`mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[10px] font-bold ${style.badge}`}
        >
          {style.icon}
        </span>
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-slate-900">
            {data.label}
          </div>
          {data.description && (
            <div className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">
              {data.description}
            </div>
          )}
          <div className="mt-1.5 flex flex-wrap gap-1">
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}>
              {data.nodeType}
            </span>
            {status !== "idle" && (
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                {status}
              </span>
            )}
          </div>
        </div>
      </div>

      {showHandles && !isTerminal && !isDecision && !isGate && (
        <Handle
          type="source"
          position={Position.Right}
          id="success"
          className="!bg-emerald-500"
        />
      )}
      {isDecision && (
        <>
          <Handle
            type="source"
            position={Position.Top}
            id="pass"
            className="!bg-emerald-500"
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="fail"
            className="!bg-rose-500"
          />
        </>
      )}
      {isGate && (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="approve"
            className="!bg-emerald-500"
          />
          <Handle
            type="source"
            position={Position.Bottom}
            id="reject"
            className="!bg-rose-500"
          />
        </>
      )}
    </div>
  );
}
