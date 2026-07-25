"use client";

import { useEffect, useState } from "react";
import type { WorkflowNode } from "@/lib/types";

interface Props {
  node: WorkflowNode | null;
  onSave: (nodeId: string, patch: Partial<WorkflowNode["data"]>) => void;
  onCancel: () => void;
  models?: any[];
}

export function NodeInspector({ node, onSave, onCancel, models }: Props) {
  const [tempData, setTempData] = useState<WorkflowNode["data"] | null>(null);

  useEffect(() => {
    if (node) {
      setTempData(JSON.parse(JSON.stringify(node.data)));
    } else {
      setTempData(null);
    }
  }, [node]);

  if (!node || !tempData) return null;

  const d = tempData;
  const showAgent = d.nodeType === "agent" || d.nodeType === "validator";
  const showCommand = d.nodeType === "command";

  const handleFieldChange = (patch: Partial<WorkflowNode["data"]>) => {
    setTempData((prev) => (prev ? { ...prev, ...patch } : null));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm">
      <div className="flex flex-col w-full max-w-lg max-h-[85vh] bg-white rounded-xl border border-slate-200 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 bg-slate-50">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Configure {d.nodeType}
            </div>
            <h3 className="text-base font-bold text-slate-800 mt-0.5">
              {d.label}
            </h3>
          </div>
          <button
            onClick={onCancel}
            className="text-slate-400 hover:text-slate-600 p-1.5 hover:bg-slate-100 rounded-lg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5 text-sm">
          <Field label="Name">
            <input
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
              value={d.label}
              onChange={(e) => handleFieldChange({ label: e.target.value })}
            />
          </Field>

          {d.role === "successCriteria" && (
            <>
              <Field label="Objective">
                <textarea
                  className="min-h-[88px] w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                  value={d.objective || ""}
                  onChange={(e) => handleFieldChange({ objective: e.target.value })}
                />
              </Field>
              <Field label="Constraints">
                <textarea
                  className="min-h-[72px] w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                  value={d.constraints || ""}
                  onChange={(e) => handleFieldChange({ constraints: e.target.value })}
                />
              </Field>
              <Field label="Target codebase path">
                <input
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                  placeholder="demo-repo or /absolute/path/to/your/project"
                  value={d.targetRepo || ""}
                  onChange={(e) => handleFieldChange({ targetRepo: e.target.value })}
                />
                <p className="mt-1 text-[11px] text-slate-400">
                  Relative to repo root, or absolute path on your machine.
                </p>
              </Field>
              <Field label="Main target file">
                <input
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                  placeholder="e.g. src/app.js"
                  value={d.mainTargetFile || ""}
                  onChange={(e) => handleFieldChange({ mainTargetFile: e.target.value })}
                />
              </Field>
              <Field label="Validate command">
                <input
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                  placeholder="e.g. npm test"
                  value={d.validateCommand || ""}
                  onChange={(e) => handleFieldChange({ validateCommand: e.target.value })}
                />
              </Field>
            </>
          )}

          {showAgent && (
            <>
              <Field label="Instructions">
                <textarea
                  className="min-h-[96px] w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                  value={d.instructions || ""}
                  onChange={(e) => handleFieldChange({ instructions: e.target.value })}
                />
              </Field>
              <Field label="Model">
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none bg-white transition-all"
                  value={d.model || "mistral-small-latest"}
                  onChange={(e) => handleFieldChange({ model: e.target.value })}
                >
                  {models && models.length > 0 ? (
                    models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))
                  ) : (
                    <>
                      <option value="mistral-small-latest">Mistral · mistral-small-latest</option>
                      <option value="gpt-4o-mini">OpenAI · gpt-4o-mini</option>
                      <option value="claude-sonnet-4-5">Anthropic · claude-sonnet-4-5</option>
                      <option value="gemini-2.0-flash">Gemini · gemini-2.0-flash</option>
                    </>
                  )}
                </select>
              </Field>
              {d.tools && (
                <Field label="Tools">
                  <div className="flex flex-wrap gap-1 mt-1">
                    {d.tools.map((t) => (
                      <span
                        key={t}
                        className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700 font-medium"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </Field>
              )}
              <div className="grid grid-cols-2 gap-3">
                <Field label="Max retries">
                  <input
                    type="number"
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    value={d.maxRetries ?? 2}
                    onChange={(e) => handleFieldChange({ maxRetries: Number(e.target.value) })}
                  />
                </Field>
                <Field label="Timeout (s)">
                  <input
                    type="number"
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                    value={d.timeout ?? 300}
                    onChange={(e) => handleFieldChange({ timeout: Number(e.target.value) })}
                  />
                </Field>
              </div>
            </>
          )}

          {showCommand && (
            <Field label="Command">
              <input
                className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                value={d.command || ""}
                onChange={(e) => handleFieldChange({ command: e.target.value })}
              />
            </Field>
          )}

          {d.nodeType === "validator" && d.fileChecks && (
            <Field label="File checks">
              <div className="text-xs text-slate-600 bg-slate-50 p-2 rounded-lg border border-slate-100 mt-1">
                {d.fileChecks.join(", ")}
              </div>
            </Field>
          )}

          <div className="rounded-lg bg-slate-50 p-2.5 text-xs text-slate-500 flex items-center gap-2 border border-slate-100">
            <span>Type: <span className="font-semibold text-slate-700">{d.nodeType}</span></span>
            {d.role && (
              <>
                <span className="text-slate-300">•</span>
                <span>Role: <span className="font-semibold text-slate-700">{d.role}</span></span>
              </>
            )}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2 border-t border-slate-200 px-5 py-3.5 bg-slate-50">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onSave(node.id, d)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 shadow-sm transition-colors"
          >
            Save Changes
          </button>
        </div>

      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </div>
      {children}
    </label>
  );
}
