"use client";

const LIBRARY = [
  { type: "agent", role: "successCriteria", label: "Success Criteria Agent", hint: "Generate success criteria" },
  { type: "agent", role: "planning", label: "Planning Agent", hint: "Create implementation plan" },
  { type: "agent", role: "execution", label: "Execution Agent", hint: "Implement codebase changes" },
  { type: "command", label: "Command", hint: "Build, test, shell" },
  { type: "validator", label: "Validator", hint: "Deterministic checks" },
  { type: "decision", label: "Decision", hint: "Pass / fail routing" },
  { type: "humanGate", label: "Human Gate", hint: "Approval pause" },
  { type: "success", label: "Success", hint: "Task successful" },
  { type: "stop", label: "Stop", hint: "Stopped safely" },
];

interface Props {
  onLoadTemplate?: () => void;
}

export function NodeLibrary({ onLoadTemplate }: Props) {
  const handleDragStart = (e: React.DragEvent, item: typeof LIBRARY[0]) => {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("application/json", JSON.stringify({ type: item.type, role: item.role }));
  };

  return (
    <aside className="flex w-60 shrink-0 flex-col border-l border-slate-200 bg-slate-50">
      <div className="border-b border-slate-200 px-3 py-2.5">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Node Library
        </div>
        <p className="mt-1 text-[11px] text-slate-400">
          Drag nodes to canvas
        </p>
      </div>
      <div className="flex-1 space-y-1 overflow-auto p-2">
        {LIBRARY.map((item) => (
          <div
            key={item.role ? `${item.type}-${item.role}` : item.type}
            draggable
            onDragStart={(e) => handleDragStart(e, item)}
            className="cursor-move rounded-lg border border-slate-200 bg-white px-2.5 py-2 hover:bg-slate-100 active:opacity-75"
          >
            <div className="text-sm font-medium text-slate-800">{item.label}</div>
            <div className="text-[11px] text-slate-500">{item.hint}</div>
          </div>
        ))}
      </div>
      <div className="border-t border-slate-200 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Templates
        </div>
        <button
          type="button"
          onClick={onLoadTemplate}
          className="mt-2 w-full rounded-lg border border-dashed border-slate-300 bg-white px-2.5 py-3 text-[11px] text-slate-600 hover:border-slate-400 hover:bg-slate-50 active:opacity-75"
        >
          Default four-agent coding loop
        </button>
      </div>
    </aside>
  );
}
