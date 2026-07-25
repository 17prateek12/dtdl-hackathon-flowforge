"use client";

import { useEffect, useState } from "react";
import type { PendingHumanGate } from "@/lib/types";

interface Props {
  gate: PendingHumanGate | null;
  busy?: boolean;
  onDecide: (payload: {
    action: "approve" | "reject" | "edit";
    editedText?: string;
    feedback?: string;
  }) => void;
}

export function HumanGateModal({ gate, busy, onDecide }: Props) {
  const [text, setText] = useState("");
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    setText(gate?.editableText || gate?.summary || "");
    setFeedback("");
  }, [gate]);

  if (!gate) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="w-full max-w-xl rounded-2xl bg-white shadow-xl">
        <div className="border-b border-slate-200 px-5 py-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-orange-600">
            Human Gate
          </div>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">
            {gate.title}
          </h2>
        </div>
        <div className="px-5 py-4">
          {gate.kind === "criteria" || gate.kind === "plan" ? (
            <textarea
              className={`${gate.kind === "plan" ? "min-h-[300px]" : "min-h-[180px]"} w-full rounded-lg border border-slate-200 p-3 font-mono text-sm`}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          ) : (
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              {gate.summary}
            </pre>
          )}
          {gate.kind === "extra_files" && gate.extraFiles?.length ? (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Additional files: {gate.extraFiles.join(", ")}
            </div>
          ) : null}
          {gate.kind === "extra_files" ? (
            <label className="mt-3 block">
              <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Instructions for next plan (optional)
              </div>
              <textarea
                className="min-h-[96px] w-full rounded-lg border border-slate-200 p-3 text-sm"
                placeholder="e.g. Keep changes only in src/app.js; do not modify test files."
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Rejecting rolls back all execution changes and sends the agent
                back to planning with your note.
              </p>
            </label>
          ) : null}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-3">
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              onDecide({
                action: "reject",
                feedback: gate.kind === "extra_files" ? feedback.trim() : undefined,
              })
            }
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {gate.kind === "extra_files" ? "Reject & replan" : "Reject"}
          </button>
          {(gate.kind === "criteria" || gate.kind === "plan") && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onDecide({ action: "edit", editedText: text })
              }
              className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
            >
              Save edits & approve
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecide({ action: "approve" })}
            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
          >
            {gate.kind === "extra_files"
              ? "Approve extra changes"
              : "Approve"}
          </button>
        </div>
      </div>
    </div>
  );
}
