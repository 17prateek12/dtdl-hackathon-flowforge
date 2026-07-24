"use client";

import { useState } from "react";

const LIBRARY = [
  { type: "input", label: "Input", hint: "Objective & constraints" },
  { type: "agent", label: "Agent", hint: "Criteria / plan / execute" },
  { type: "command", label: "Command", hint: "Build, test, shell" },
  { type: "validator", label: "Validator", hint: "Deterministic checks" },
  { type: "decision", label: "Decision", hint: "Pass / fail routing" },
  { type: "humanGate", label: "Human Gate", hint: "Approval pause" },
  { type: "success", label: "Success", hint: "Task successful" },
  { type: "stop", label: "Stop", hint: "Stopped safely" },
];

interface Props {
  onLoadTemplate?: () => void;
  runId?: string | null;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

function CollapseIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      {direction === "left" ? (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
      )}
    </svg>
  );
}

export function NodeLibrary({
  onLoadTemplate,
  runId,
  collapsed = false,
  onToggleCollapse,
}: Props) {
  const [repoPath, setRepoPath] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  const [reviewReport, setReviewReport] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);

  const handleDragStart = (e: React.DragEvent, item: typeof LIBRARY[0]) => {
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("application/json", JSON.stringify({ type: item.type }));
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const url = `/api/codebase/search?query=${encodeURIComponent(searchQuery)}${repoPath ? `&repoPath=${encodeURIComponent(repoPath)}` : runId ? `&runId=${runId}` : ""}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.results || []);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSearching(false);
    }
  };

  const handleReview = async () => {
    setReviewing(true);
    try {
      const url = `/api/codebase/review?${repoPath ? `repoPath=${encodeURIComponent(repoPath)}` : runId ? `runId=${runId}` : ""}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setReviewReport(data.report);
        setShowReviewModal(true);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setReviewing(false);
    }
  };

  if (collapsed) {
    return (
      <aside className="flex w-11 shrink-0 flex-col items-center border-r border-slate-200 bg-slate-50 py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          title="Show node library"
          className="rounded-md p-1.5 text-slate-500 hover:bg-white hover:text-slate-800 hover:shadow-sm transition-colors"
        >
          <CollapseIcon direction="right" />
        </button>
        <span
          className="mt-6 text-[9px] font-semibold uppercase tracking-widest text-slate-400"
          style={{ writingMode: "vertical-rl", textOrientation: "mixed" }}
        >
          Library
        </span>
      </aside>
    );
  }

  return (
    <>
      <aside className="relative flex w-64 shrink-0 flex-col border-r border-slate-200 bg-slate-50 overflow-y-auto transition-[width] duration-200">
        <button
          type="button"
          onClick={onToggleCollapse}
          title="Hide node library"
          className="absolute right-2 top-2 z-10 rounded-md p-1 text-slate-400 hover:bg-white hover:text-slate-700 hover:shadow-sm transition-colors"
        >
          <CollapseIcon direction="left" />
        </button>
        <div className="border-b border-slate-200 px-3 py-2.5 pr-10">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Node Library
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            Drag nodes to canvas
          </p>
        </div>
        <div className="space-y-1 p-2">
          {LIBRARY.map((item) => (
            <div
              key={item.type}
              draggable
              onDragStart={(e) => handleDragStart(e, item)}
              className="cursor-move rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 hover:bg-slate-100 active:opacity-75"
            >
              <div className="text-xs font-medium text-slate-800">{item.label}</div>
              <div className="text-[10px] text-slate-500 leading-tight">{item.hint}</div>
            </div>
          ))}
        </div>

        <div className="border-t border-slate-200 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Target Codebase Path
          </div>
          <input
            type="text"
            placeholder="Absolute folder path (e.g. C:/my-repo)"
            value={repoPath}
            onChange={(e) => setRepoPath(e.target.value)}
            className="w-full rounded border border-slate-200 px-2 py-1.5 text-xs text-slate-700 bg-white shadow-sm focus:border-indigo-500 focus:outline-none"
          />
        </div>

        <div className="border-t border-slate-200 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Templates
          </div>
          <button
            type="button"
            onClick={() => onLoadTemplate?.()}
            className="mt-2 w-full rounded-lg border border-dashed border-slate-300 bg-white px-2.5 py-2 text-[11px] text-slate-600 hover:border-slate-400 hover:bg-slate-50 active:opacity-75"
          >
            Default four-agent coding loop
          </button>
        </div>

        <div className="border-t border-slate-200 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Codebase Audit
          </div>
          <button
            type="button"
            onClick={handleReview}
            disabled={reviewing}
            className="mt-2 w-full rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-medium py-1.5 px-3 text-[11px] disabled:opacity-50 transition-colors"
          >
            {reviewing ? "Auditing codebase..." : "📊 Run Architectural Audit"}
          </button>
        </div>

        <div className="border-t border-slate-200 p-3 flex-1">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">
            Codebase Search (RAG)
          </div>
          <form onSubmit={handleSearch} className="flex gap-1.5">
            <input
              type="text"
              placeholder="Search code concepts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 rounded border border-slate-200 px-2 py-1 text-xs"
            />
            <button
              type="submit"
              disabled={searching}
              className="bg-slate-800 hover:bg-slate-900 text-white rounded px-2 py-1 text-xs disabled:opacity-50"
            >
              🔍
            </button>
          </form>

          {searchResults.length > 0 && (
            <div className="mt-3 space-y-2 max-h-60 overflow-y-auto pr-1">
              <div className="text-[10px] text-slate-400">Top matches:</div>
              {searchResults.map((r, i) => (
                <div key={i} className="border-b border-slate-200 pb-1.5 text-[10px]">
                  <div className="font-semibold text-slate-700 truncate" title={r.path}>
                    📄 {r.path.split("/").pop()}
                  </div>
                  <div className="text-[9px] text-indigo-600 font-mono">
                    Score: {r.score}
                  </div>
                  <pre className="mt-1 bg-white p-1 border rounded text-[9px] font-mono whitespace-pre-wrap max-h-20 overflow-y-auto">
                    {r.text}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      {showReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="flex h-[85vh] w-full max-w-3xl flex-col rounded-xl border border-slate-200 bg-white shadow-xl animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
              <div>
                <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                  📊 Codebase Quality & Security Review
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Static analysis & LLM audit results
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowReviewModal(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6 scrollbar-hide">
              <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-slate-800 bg-slate-50 p-4 border rounded-lg border-slate-100">
                {reviewReport}
              </pre>
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50 px-6 py-4 rounded-b-xl">
              <button
                type="button"
                onClick={() => setShowReviewModal(false)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Close Report
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
