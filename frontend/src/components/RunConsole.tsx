"use client";

import type { ConsoleEvent, FileChange, RunRecord } from "@/lib/types";

interface Props {
  run: RunRecord | null;
  collapsed: boolean;
  onToggle: () => void;
  selectedNodeId: string | null;
}

export function RunConsole({ run, collapsed, onToggle, selectedNodeId }: Props) {
  const events = filterEvents(run?.events ?? [], selectedNodeId);
  const files = run?.filesChanged ?? [];

  return (
    <section
      className={`border-t border-slate-200 bg-slate-950 text-slate-100 ${collapsed ? "h-10" : "h-52"}`}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex h-10 w-full items-center justify-between px-3 text-left text-xs font-semibold uppercase tracking-wide text-slate-300 hover:bg-slate-900"
      >
        <span>Run Console</span>
        <span className="font-normal normal-case text-slate-500">
          {run
            ? `${run.status} · attempt ${run.attempt}/${run.maxAttempts}`
            : "idle"}{" "}
          · {collapsed ? "Expand" : "Collapse"}
        </span>
      </button>
      {!collapsed && (
        <div className="grid h-[calc(100%-2.5rem)] grid-cols-3 gap-0 border-t border-slate-800">
          <LogPane title="Messages" events={events} />
          <div className="overflow-auto border-l border-slate-800 p-2">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Files Changed
            </div>
            {files.length === 0 ? (
              <div className="text-xs text-slate-500">No file changes yet</div>
            ) : (
              <ul className="space-y-1 text-xs">
                {files.map((f) => (
                  <FileRow key={`${f.path}-${f.action}`} file={f} />
                ))}
              </ul>
            )}
          </div>
          <div className="overflow-auto border-l border-slate-800 p-2">
            <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Validation Evidence
            </div>
            <pre className="whitespace-pre-wrap font-mono text-[11px] text-slate-300">
              {run?.validationEvidence || "—"}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}

function filterEvents(events: ConsoleEvent[], nodeId: string | null) {
  if (!nodeId) return events;
  const focused = events.filter((e) => e.nodeId === nodeId);
  return focused.length ? focused : events;
}

function LogPane({ title, events }: { title: string; events: ConsoleEvent[] }) {
  return (
    <div className="overflow-auto p-2">
      <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </div>
      <ul className="space-y-1">
        {events.length === 0 && (
          <li className="text-xs text-slate-500">No events yet</li>
        )}
        {events.map((e) => (
          <li key={e.id} className="font-mono text-[11px] leading-snug">
            <span className="text-slate-500">
              {new Date(e.ts).toLocaleTimeString()}
            </span>{" "}
            <span className={levelColor(e.level)}>[{e.level}]</span>{" "}
            <span className="text-slate-200">{e.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function FileRow({ file }: { file: FileChange }) {
  return (
    <li className="flex items-center justify-between gap-2 font-mono text-slate-200">
      <span className="truncate">{file.path}</span>
      <span className="shrink-0 text-slate-500">{file.action}</span>
    </li>
  );
}

function levelColor(level: ConsoleEvent["level"]) {
  switch (level) {
    case "success":
      return "text-emerald-400";
    case "warn":
      return "text-amber-400";
    case "error":
      return "text-rose-400";
    default:
      return "text-sky-400";
  }
}
