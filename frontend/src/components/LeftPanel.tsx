"use client";

import { useState, useEffect } from "react";
import type { RunRecord } from "@/lib/types";

interface SavedWorkflow {
  id: string;
  name: string;
  updatedAt: string | null;
}

interface Props {
  runs: RunRecord[];
  activeRun: RunRecord | null;
  onSelectRun: (run: RunRecord) => void;
  onCreatePipeline: () => void;
  onSavePipeline: () => void;
  onLoadPipeline?: (id: string) => void;
  isSaving: boolean;
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2.5}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
    </svg>
  );
}

function Section({
  title,
  children,
  defaultOpen = true,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="space-y-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded px-0.5 py-0.5 hover:bg-slate-100 transition-colors group"
      >
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 group-hover:text-slate-500">
          {title}
        </span>
        <ChevronIcon open={open} />
      </button>
      {open && <div className="space-y-1.5">{children}</div>}
    </div>
  );
}

export function LeftPanel({
  runs,
  activeRun,
  onSelectRun,
  onCreatePipeline,
  onSavePipeline,
  onLoadPipeline,
  isSaving,
}: Props) {
  const [savedWorkflows, setSavedWorkflows] = useState<SavedWorkflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [actionBusy, setActionBusy] = useState(false);

  // Fetch saved pipelines from MySQL via backend
  const fetchSavedWorkflows = async () => {
    try {
      const res = await fetch("/api/workflows/list");
      if (res.ok) {
        const data = (await res.json()) as SavedWorkflow[];
        setSavedWorkflows(data);
      }
    } catch {
      // non-fatal
    }
  };

  useEffect(() => {
    void fetchSavedWorkflows();
  }, []);

  // Refresh saved list after saving
  const handleSave = async () => {
    await onSavePipeline();
    setTimeout(() => void fetchSavedWorkflows(), 600);
  };

  const handleRenameSubmit = async (wf: SavedWorkflow) => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === wf.name) {
      setEditingId(null);
      return;
    }
    setActionBusy(true);
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(wf.id)}/rename`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });
      if (res.ok) {
        setSavedWorkflows((prev) =>
          prev.map((item) => (item.id === wf.id ? { ...item, name: trimmed } : item))
        );
      }
    } catch (err) {
      console.error("Failed to rename workflow:", err);
    } finally {
      setActionBusy(false);
      setEditingId(null);
    }
  };

  const handleDelete = async (wf: SavedWorkflow) => {
    if (!confirm(`Are you sure you want to delete pipeline "${wf.name}"?`)) {
      return;
    }
    setActionBusy(true);
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(wf.id)}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSavedWorkflows((prev) => prev.filter((item) => item.id !== wf.id));
        if (selectedWorkflowId === wf.id) {
          setSelectedWorkflowId(null);
        }
      }
    } catch (err) {
      console.error("Failed to delete workflow:", err);
    } finally {
      setActionBusy(false);
    }
  };

  const getStatusBadge = (status: RunRecord["status"]) => {
    switch (status) {
      case "succeeded":
        return "bg-emerald-100 text-emerald-800 border-emerald-200";
      case "failed":
        return "bg-rose-100 text-rose-800 border-rose-200";
      case "stopped":
        return "bg-amber-100 text-amber-800 border-amber-200";
      case "running":
        return "bg-blue-100 text-blue-800 border-blue-200 animate-pulse";
      case "waiting_for_human":
        return "bg-indigo-100 text-indigo-800 border-indigo-200";
      default:
        return "bg-slate-100 text-slate-800 border-slate-200";
    }
  };

  const getVerdictLabel = (status: RunRecord["status"]) => {
    switch (status) {
      case "succeeded": return "SUCCESS";
      case "failed": return "FAILED";
      case "stopped": return "STOPPED";
      case "running": return "RUNNING";
      case "waiting_for_human": return "WAITING";
      default: return "IDLE";
    }
  };

  const formatRunLabel = (run: RunRecord) => {
    try {
      const date = new Date(run.startedAt);
      const timeStr = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
      return `Run #${run.id.slice(-4)} (${timeStr})`;
    } catch {
      return `Run #${run.id.slice(-4)}`;
    }
  };

  const formatUpdatedAt = (iso: string | null) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
        d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-slate-200 bg-white">
      {/* Title */}
      <div className="border-b border-slate-200 px-4 py-3 bg-slate-50">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Orchestration Control
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">

        {/* ── Pipeline Setup ─────────────────────────────── */}
        <Section title="Pipeline Setup" defaultOpen={true}>
          <button
            type="button"
            onClick={onCreatePipeline}
            className="w-full rounded-lg bg-indigo-50 border border-indigo-200 px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 active:opacity-75 transition-all text-left flex items-center gap-2"
          >
            <span className="text-base leading-none">＋</span>
            <span>Create New Pipeline</span>
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="w-full rounded-lg bg-slate-800 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700 active:opacity-75 disabled:opacity-50 transition-all text-left flex items-center justify-between gap-2"
          >
            <span className="flex items-center gap-2">
              <span>💾</span>
              <span>Save Canvas</span>
            </span>
            {isSaving && (
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
            )}
          </button>
        </Section>

        {/* ── Saved Pipelines ────────────────────────────── */}
        <Section title="Saved Pipelines" defaultOpen={true}>
          {savedWorkflows.length > 0 ? (
            <div className="space-y-1.5 max-h-[26vh] overflow-y-auto pr-0.5">
              {savedWorkflows.map((wf) => {
                const isSelected = selectedWorkflowId === wf.id;
                const isEditing = editingId === wf.id;

                return (
                  <div
                    key={wf.id}
                    className={`rounded-lg border text-xs transition-all overflow-hidden ${
                      isSelected
                        ? "border-indigo-300 bg-indigo-50/40 shadow-sm"
                        : "border-slate-100 bg-white hover:border-slate-200"
                    }`}
                  >
                    {/* Item Main Bar */}
                    {isEditing ? (
                      <div className="p-2 space-y-2 bg-indigo-50/60">
                        <input
                          type="text"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void handleRenameSubmit(wf);
                            if (e.key === "Escape") setEditingId(null);
                          }}
                          className="w-full rounded border border-indigo-300 px-2 py-1 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                          placeholder="New pipeline name..."
                          autoFocus
                          disabled={actionBusy}
                        />
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => setEditingId(null)}
                            className="px-2 py-0.5 rounded text-[10px] font-semibold text-slate-600 hover:bg-slate-200"
                            disabled={actionBusy}
                          >
                            Cancel
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleRenameSubmit(wf)}
                            className="px-2 py-0.5 rounded text-[10px] font-semibold bg-indigo-600 text-white hover:bg-indigo-700"
                            disabled={actionBusy}
                          >
                            Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div
                        onClick={() => setSelectedWorkflowId((prev) => (prev === wf.id ? null : wf.id))}
                        className="cursor-pointer px-2.5 py-2 group"
                      >
                        <div className="flex items-start justify-between gap-1">
                          <span className="text-xs font-semibold text-slate-700 truncate group-hover:text-indigo-700 leading-tight">
                            {wf.name}
                          </span>
                          <span className="text-[9px] font-mono text-slate-400 shrink-0 mt-0.5">
                            #{wf.id.slice(-4)}
                          </span>
                        </div>
                        {wf.updatedAt && (
                          <p className="text-[10px] text-slate-400 mt-0.5 truncate">
                            {formatUpdatedAt(wf.updatedAt)}
                          </p>
                        )}
                      </div>
                    )}

                    {/* 3 Action Options (Load, Rename, Delete) when clicked/selected */}
                    {isSelected && !isEditing && (
                      <div className="flex items-center justify-between border-t border-indigo-100 bg-indigo-50/80 px-2 py-1.5 gap-1">
                        <button
                          type="button"
                          onClick={() => onLoadPipeline?.(wf.id)}
                          className="flex-1 flex items-center justify-center gap-1 rounded bg-indigo-600 px-2 py-1 text-[10px] font-semibold text-white hover:bg-indigo-700 transition-colors"
                          title="Load pipeline onto canvas"
                        >
                          <span>📂</span>
                          <span>Load</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(wf.id);
                            setRenameValue(wf.name);
                          }}
                          className="flex items-center justify-center gap-1 rounded border border-indigo-200 bg-white px-2 py-1 text-[10px] font-semibold text-slate-700 hover:bg-indigo-100 transition-colors"
                          title="Rename pipeline"
                        >
                          <span>✏️</span>
                          <span>Rename</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDelete(wf)}
                          className="flex items-center justify-center gap-1 rounded border border-rose-200 bg-white px-2 py-1 text-[10px] font-semibold text-rose-600 hover:bg-rose-50 transition-colors"
                          title="Delete pipeline"
                        >
                          <span>🗑️</span>
                          <span>Delete</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic py-1">No saved pipelines</p>
          )}
        </Section>

        {/* ── Active Run Verdict ─────────────────────────── */}
        <Section title="Active Run Verdict" defaultOpen={true}>
          <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-3 space-y-2">
            {activeRun ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">Verdict</span>
                  <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getStatusBadge(activeRun.status)}`}>
                    {getVerdictLabel(activeRun.status)}
                  </span>
                </div>
                <div className="text-xs text-slate-700">
                  <span className="font-semibold">Attempt:</span> {activeRun.attempt} / {activeRun.maxAttempts}
                </div>
                {activeRun.currentNodeId && (
                  <div className="text-xs text-slate-700 truncate">
                    <span className="font-semibold">Node:</span> {activeRun.currentNodeId}
                  </div>
                )}
                {activeRun.lastError && (
                  <div className="text-[11px] text-rose-600 bg-rose-50 border border-rose-100 rounded p-1.5 line-clamp-2">
                    {activeRun.lastError}
                  </div>
                )}
              </>
            ) : (
              <p className="text-xs text-slate-400 italic py-2">No active run selected</p>
            )}
          </div>
        </Section>

        {/* ── Execution History ──────────────────────────── */}
        <Section title="Execution History" defaultOpen={true}>
          <div className="space-y-1 max-h-[28vh] overflow-y-auto pr-0.5">
            {runs.length > 0 ? (
              runs.map((r) => (
                <button
                  key={r.id}
                  onClick={() => onSelectRun(r)}
                  className={`w-full text-left p-2.5 rounded-lg border text-xs transition-all flex items-center justify-between ${
                    activeRun?.id === r.id
                      ? "border-indigo-300 bg-indigo-50/60 font-semibold"
                      : "border-slate-100 bg-white hover:border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <span className="truncate text-slate-700">{formatRunLabel(r)}</span>
                  <span className={`px-1.5 py-0.5 rounded border text-[9px] font-bold shrink-0 ${getStatusBadge(r.status)}`}>
                    {r.status.toUpperCase()}
                  </span>
                </button>
              ))
            ) : (
              <p className="text-xs text-slate-400 italic py-1">No runs found</p>
            )}
          </div>
        </Section>

      </div>
    </aside>
  );
}
