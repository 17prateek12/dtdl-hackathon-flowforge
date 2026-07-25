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
  { border: string; accentBar: string; badge: string; icon: string }
> = {
  agent: {
    border: "border-indigo-300 hover:border-indigo-400",
    accentBar: "bg-indigo-500",
    badge: "bg-indigo-50 text-indigo-700 border border-indigo-200",
    icon: "AG",
  },
  command: {
    border: "border-amber-300 hover:border-amber-400",
    accentBar: "bg-amber-500",
    badge: "bg-amber-50 text-amber-800 border border-amber-200",
    icon: "$",
  },
  validator: {
    border: "border-violet-300 hover:border-violet-400",
    accentBar: "bg-violet-500",
    badge: "bg-violet-50 text-violet-700 border border-violet-200",
    icon: "VA",
  },
  decision: {
    border: "border-fuchsia-300 hover:border-fuchsia-400",
    accentBar: "bg-fuchsia-500",
    badge: "bg-fuchsia-50 text-fuchsia-700 border border-fuchsia-200",
    icon: "?",
  },
  humanGate: {
    border: "border-orange-300 hover:border-orange-400",
    accentBar: "bg-orange-500",
    badge: "bg-orange-50 text-orange-800 border border-orange-200",
    icon: "HG",
  },
  success: {
    border: "border-emerald-300 hover:border-emerald-400",
    accentBar: "bg-emerald-500",
    badge: "bg-emerald-50 text-emerald-700 border border-emerald-200",
    icon: "OK",
  },
  stop: {
    border: "border-rose-300 hover:border-rose-400",
    accentBar: "bg-rose-500",
    badge: "bg-rose-50 text-rose-700 border border-rose-200",
    icon: "ST",
  },
};

const STATUS_RING: Record<NodeStatus, string> = {
  idle: "",
  running: "ring-2 ring-blue-500 ring-offset-2 animate-pulse",
  completed: "border-emerald-500 ring-2 ring-emerald-400/50 shadow-emerald-100",
  failed: "border-rose-500 ring-2 ring-rose-400/50",
  waiting: "border-amber-500 ring-2 ring-amber-400/50",
  skipped: "opacity-50",
};

export type LoopNodeData = WorkflowNodeConfig & {
  status?: NodeStatus;
  onDelete?: (id: string) => void;
  [key: string]: unknown;
};
export type LoopFlowNode = Node<LoopNodeData, "loopNode">;

export function LoopNode({ id, data, selected }: NodeProps<LoopFlowNode>) {
  const style = (data?.nodeType ? TYPE_STYLES[data.nodeType] : null) || {
    border: "border-slate-300",
    accentBar: "bg-slate-400",
    badge: "bg-slate-100 text-slate-700 border border-slate-200",
    icon: "??",
  };
  const status = data.status || "idle";
  const isCompleted =
    status === "completed" ||
    status === ("succeeded" as string) ||
    status === ("pass" as string) ||
    status === ("approved" as string);

  const isDecision = data.nodeType === "decision";
  const isGate = data.nodeType === "humanGate";
  const isTerminal =
    data.nodeType === "success" || data.nodeType === "stop";

  return (
    <div
      className={`group relative min-w-[210px] max-w-[250px] rounded-xl border-2 bg-white px-3.5 py-3 shadow-xs transition-all overflow-visible ${
        isCompleted ? "border-emerald-400 bg-emerald-50/10" : style.border
      } ${STATUS_RING[status] || ""} ${selected ? "shadow-md ring-2 ring-indigo-400" : ""}`}
    >
      {/* Left accent color stripe */}
      <div
        className={`absolute left-0 top-2 bottom-2 w-1 rounded-r ${
          isCompleted ? "bg-emerald-500" : style.accentBar
        }`}
      />

      {/* Top-Right Green Circle Tick Badge for ALL completed boxes */}
      {isCompleted && (
        <span
          className="absolute -top-2.5 -right-2.5 z-30 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white shadow-md ring-2 ring-white text-xs font-bold"
          title="Completed ✓"
        >
          ✓
        </span>
      )}

      {/* Delete button on hover */}
      {data.onDelete && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            data.onDelete?.(id);
          }}
          className={`absolute -right-2 -bottom-2 hidden h-5 w-5 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white shadow-sm hover:bg-rose-600 group-hover:flex z-40`}
          title="Delete node"
        >
          ✕
        </button>
      )}

      <Handle type="target" position={Position.Left} className="!bg-slate-400" />

      <div className="flex items-start gap-2.5 pl-1">
        {/* Node Icon */}
        <span
          className={`mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-[10px] font-bold ${style.badge}`}
        >
          {style.icon}
        </span>

        {/* Node Content */}
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-bold text-slate-900 leading-snug">
            {data.label}
          </div>
          {data.description && (
            <div className="mt-0.5 line-clamp-2 text-[10px] text-slate-500 leading-tight">
              {data.description}
            </div>
          )}

          {/* Bottom Pills */}
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${style.badge}`}>
              {data.nodeType}
            </span>
            {status !== "idle" && (
              <span
                className={`rounded px-1.5 py-0.5 text-[9px] font-semibold ${
                  isCompleted
                    ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                    : "bg-slate-100 text-slate-600 border border-slate-200"
                }`}
              >
                {status}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Handles */}
      {!isTerminal && !isDecision && !isGate && (
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
