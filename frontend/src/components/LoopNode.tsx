"use client";

import {
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import type { NodeStatus, NodeType, WorkflowNodeConfig } from "@/lib/types";

const animationStyles = `
  @keyframes node-pulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
    50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
  }
  
  @keyframes node-shake {
    0%, 100% { transform: translateX(0); }
    10%, 30%, 50%, 70%, 90% { transform: translateX(-3px); }
    20%, 40%, 60%, 80% { transform: translateX(3px); }
  }
  
  @keyframes node-success-flash {
    0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.8); }
    100% { box-shadow: 0 0 0 12px rgba(34, 197, 94, 0); }
  }
  
  @keyframes checkmark-draw {
    0% { stroke-dashoffset: 50; opacity: 0; }
    50% { opacity: 1; }
    100% { stroke-dashoffset: 0; opacity: 1; }
  }
  
  .node-running {
    animation: node-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
  }
  
  .node-failed {
    animation: node-shake 0.5s cubic-bezier(0.36, 0, 0.66, 1) 0.2s;
  }
  
  .node-success {
    animation: node-success-flash 0.6s cubic-bezier(0.4, 0, 0.6, 1);
  }
  
  .checkmark-icon {
    stroke-dasharray: 50;
    stroke-dashoffset: 50;
    animation: checkmark-draw 0.5s ease-in-out 0.1s forwards;
  }
`;

const TYPE_STYLES: Record<
  NodeType,
  { stripe: string; badge: string; ring: string }
> = {
  input: {
    stripe: "bg-sky-500",
    badge: "bg-sky-50 text-sky-700 ring-sky-100",
    ring: "ring-sky-200",
  },
  agent: {
    stripe: "bg-indigo-500",
    badge: "bg-indigo-50 text-indigo-700 ring-indigo-100",
    ring: "ring-indigo-200",
  },
  command: {
    stripe: "bg-amber-500",
    badge: "bg-amber-50 text-amber-800 ring-amber-100",
    ring: "ring-amber-200",
  },
  validator: {
    stripe: "bg-violet-500",
    badge: "bg-violet-50 text-violet-700 ring-violet-100",
    ring: "ring-violet-200",
  },
  decision: {
    stripe: "bg-fuchsia-500",
    badge: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-100",
    ring: "ring-fuchsia-200",
  },
  humanGate: {
    stripe: "bg-orange-500",
    badge: "bg-orange-50 text-orange-800 ring-orange-100",
    ring: "ring-orange-200",
  },
  success: {
    stripe: "bg-emerald-500",
    badge: "bg-emerald-50 text-emerald-700 ring-emerald-100",
    ring: "ring-emerald-200",
  },
  stop: {
    stripe: "bg-rose-500",
    badge: "bg-rose-50 text-rose-700 ring-rose-100",
    ring: "ring-rose-200",
  },
};

const STATUS_RING: Record<NodeStatus, string> = {
  idle: "",
  running: "node-running",
  completed: "node-success ring-2 ring-emerald-400 ring-offset-1",
  failed: "node-failed ring-2 ring-rose-500 ring-offset-1",
  waiting: "ring-2 ring-amber-400 ring-offset-2",
  skipped: "opacity-50",
};

function NodeIcon({ nodeType }: { nodeType: NodeType }) {
  const className = "h-3.5 w-3.5";
  switch (nodeType) {
    case "input":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
      );
    case "agent":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
        </svg>
      );
    case "command":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    case "validator":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
      );
    case "decision":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case "humanGate":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      );
    case "success":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      );
    case "stop":
      return (
        <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
        </svg>
      );
  }
}

export type LoopNodeData = WorkflowNodeConfig & {
  status?: NodeStatus;
  [key: string]: unknown;
};
export type LoopFlowNode = Node<LoopNodeData, "loopNode">;

export function LoopNode({ data, selected }: NodeProps<LoopFlowNode>) {
  const style = TYPE_STYLES[data.nodeType];
  const status = data.status || "idle";
  const isInput = data.nodeType === "input";
  const isDecision = data.nodeType === "decision";
  const isGate = data.nodeType === "humanGate";
  const isTerminal =
    data.nodeType === "success" || data.nodeType === "stop";
  const isSucceeded = status === "completed";
  const hasTarget = !isInput;
  const hasDefaultSource =
    !isInput && !isTerminal && !isDecision && !isGate;

  const handleClass =
    "!z-10 !h-3 !w-3 !border-2 !border-white !shadow-sm";

  return (
    <>
      <style>{animationStyles}</style>
      <div
        className={`relative flex min-w-[200px] max-w-[240px] overflow-visible rounded-xl border border-slate-200/90 bg-white shadow-sm transition-all ${STATUS_RING[status]} ${selected ? `shadow-md ring-2 ${style.ring} ring-offset-1` : "hover:shadow-md"}`}
      >
        {hasTarget && (
          <Handle
            type="target"
            position={Position.Left}
            className={`${handleClass} !bg-slate-400`}
          />
        )}
        {isInput && (
          <Handle
            type="source"
            position={Position.Right}
            id="out"
            className={`${handleClass} !bg-sky-500`}
          />
        )}
        {hasDefaultSource && (
          <Handle
            type="source"
            position={Position.Right}
            id="success"
            className={`${handleClass} !bg-emerald-500`}
          />
        )}
        {isDecision && (
          <>
            <Handle
              type="source"
              position={Position.Top}
              id="pass"
              className={`${handleClass} !bg-emerald-500`}
            />
            <Handle
              type="source"
              position={Position.Bottom}
              id="fail"
              className={`${handleClass} !bg-rose-500`}
            />
          </>
        )}
        {isGate && (
          <>
            <Handle
              type="source"
              position={Position.Right}
              id="approve"
              className={`${handleClass} !bg-emerald-500`}
            />
            <Handle
              type="source"
              position={Position.Bottom}
              id="reject"
              className={`${handleClass} !bg-rose-500`}
            />
          </>
        )}

        <div className={`w-1 shrink-0 ${style.stripe}`} />
        <div className="relative min-w-0 flex-1 px-3 py-2.5">
          <div className="flex items-start gap-2">
            <span
              className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ring-1 ${style.badge}`}
            >
              <NodeIcon nodeType={data.nodeType} />
            </span>
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-slate-900">
                {data.label}
              </div>
              {data.description && (
                <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-slate-500">
                  {data.description}
                </div>
              )}
              <div className="mt-1.5 flex flex-wrap gap-1">
                <span
                  className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ring-1 ${style.badge}`}
                >
                  {data.nodeType}
                </span>
                {status !== "idle" && (
                  <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                    {status}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      {isSucceeded && (
        <div className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500 shadow-sm">
          <svg className="checkmark-icon h-5 w-5 stroke-white text-white" fill="none" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}
    </>
  );
}
