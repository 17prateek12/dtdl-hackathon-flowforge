"use client";

import { useEffect, useState } from "react";
import type { PendingHumanGate } from "@/lib/types";

interface Props {
  gate: PendingHumanGate | null;
  busy?: boolean;
  onDecide: (payload: {
    action: "approve" | "reject" | "edit";
    editedText?: string;
  }) => void;
}

export function HumanGateModal({ gate, busy, onDecide }: Props) {
  const [text, setText] = useState("");

  useEffect(() => {
    setText(gate?.editableText || gate?.summary || "");
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
          {gate.kind === "criteria" ? (
            <textarea
              className="min-h-[180px] w-full rounded-lg border border-slate-200 p-3 font-mono text-sm"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          ) : (
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
              {gate.summary}
            </pre>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecide({ action: "reject" })}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Reject
          </button>
          {gate.kind === "criteria" && (
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
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
