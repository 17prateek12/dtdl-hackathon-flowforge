"use client";

import { useEffect, useRef, useState } from "react";
import type { ConsoleEvent, FileChange, RunRecord } from "@/lib/types";

// Global styles for hiding scrollbars
const scrollbarHideStyles = `
  .scrollbar-hide::-webkit-scrollbar {
    display: none;
  }
  .scrollbar-hide {
    -ms-overflow-style: none;
    scrollbar-width: none;
  }
`;

interface Props {
  run: RunRecord | null;
  collapsed: boolean;
  onToggle: () => void;
  selectedNodeId: string | null;
}

export function RunConsole({ run, collapsed, onToggle, selectedNodeId }: Props) {
  const events = filterEvents(run?.events ?? [], selectedNodeId);
  const files = run?.filesChanged ?? [];
  const [height, setHeight] = useState<number>(150);
  const [isDragging, setIsDragging] = useState(false);
  const sectionRef = useRef<HTMLDivElement>(null);

  const MIN_HEIGHT = 40;
  const MAX_HEIGHT = 800;

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!sectionRef.current) return;
      const rect = sectionRef.current.getBoundingClientRect();
      const newHeight = window.innerHeight - e.clientY;

      if (newHeight >= MIN_HEIGHT && newHeight <= MAX_HEIGHT) {
        setHeight(newHeight);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  const displayHeight = collapsed ? 40 : height;

  return (
    <>
      <style>{scrollbarHideStyles}</style>
      <section
      ref={sectionRef}
      className="border-t border-slate-200 bg-slate-950 text-slate-100 overflow-hidden flex flex-col select-none"
      style={{
        height: `${displayHeight}px`,
        transition: isDragging ? "none" : "height 150ms ease-out",
      }}
    >
      {!collapsed && (
        <div
          className="h-1 hover:bg-slate-600 cursor-ns-resize transition-colors shrink-0"
          onMouseDown={() => setIsDragging(true)}
          title="Drag to resize console"
        />
      )}

      <button
        type="button"
        onClick={onToggle}
        className="flex h-10 w-full items-center justify-between px-3 text-left font-medium text-slate-300 hover:bg-slate-900 transition-colors shrink-0"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-4 h-4 transition-transform duration-250 ${
              collapsed ? "rotate-0" : "rotate-180"
            }`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 14l-7 7m0 0l-7-7m7 7V3"
            />
          </svg>
          <span className="text-xs font-semibold uppercase tracking-wide">
            Run Console
          </span>
        </div>
        <span className="font-normal normal-case text-slate-400 text-xs">
          {run
            ? `${run.status} · ${events.length} event${events.length !== 1 ? "s" : ""}`
            : "idle"}
        </span>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-3 gap-0 border-t border-slate-800 flex-1 min-h-0 overflow-hidden">
          <LogPane title="Messages" events={events} />
          <div className="scrollbar-hide overflow-auto border-l border-slate-800 p-3">
            <div className="mb-3 text-[9px] font-semibold uppercase tracking-wide text-slate-300">
              Files Changed
            </div>
            {files.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-center">
                <div className="text-[11px] text-slate-400">No file changes yet</div>
              </div>
            ) : (
              <ul className="space-y-1">
                {files.map((f) => (
                  <FileRow key={`${f.path}-${f.action}`} file={f} />
                ))}
              </ul>
            )}
          </div>
          <div className="scrollbar-hide overflow-auto border-l border-slate-800 p-3">
            <div className="mb-3 text-[9px] font-semibold uppercase tracking-wide text-slate-300">
              Validation Evidence
            </div>
            {run?.validationEvidence ? (
              <pre className="whitespace-pre-wrap font-mono text-[10px] text-slate-300 leading-relaxed">
                {run.validationEvidence}
              </pre>
            ) : (
              <div className="flex items-center justify-center h-32 text-center">
                <div className="text-[11px] text-slate-400">No evidence yet</div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
    </>
  );
}

function filterEvents(events: ConsoleEvent[], nodeId: string | null) {
  if (!nodeId) return events;
  const focused = events.filter((e) => e.nodeId === nodeId);
  return focused.length ? focused : events;
}

function LogPane({ title, events }: { title: string; events: ConsoleEvent[] }) {
  return (
    <div className="scrollbar-hide overflow-auto p-3">
      <div className="mb-3 text-[9px] font-semibold uppercase tracking-wide text-slate-300">
        {title}
      </div>
      {events.length === 0 ? (
        <div className="flex items-center justify-center h-32 text-center">
          <div className="text-[11px] text-slate-400">No events yet</div>
        </div>
      ) : (
        <ul className="space-y-1.5">
          {events.map((e) => (
            <li key={e.id} className="font-mono text-[10px] leading-relaxed">
              <span className="text-slate-500">
                {new Date(e.ts).toLocaleTimeString()}
              </span>{" "}
              <span className={levelColor(e.level)}>[{e.level}]</span>{" "}
              <span className="text-slate-300">{e.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FileRow({ file }: { file: FileChange }) {
  return (
    <li className="flex items-center justify-between gap-2 font-mono text-slate-300 text-[10px] py-1">
      <span className="truncate">{file.path}</span>
      <span className="shrink-0 text-slate-400 text-[9px]">{file.action}</span>
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
