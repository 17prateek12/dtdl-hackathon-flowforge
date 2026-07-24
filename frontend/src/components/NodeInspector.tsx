"use client";

import type { WorkflowNode } from "@/lib/types";

const inputClassName =
  "w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm shadow-sm transition-shadow focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";

export interface ModelOption {
  id: string;
  label: string;
  provider: string;
  available: boolean;
  envKey: string;
}

interface Props {
  node: WorkflowNode | null;
  onChange: (nodeId: string, patch: Partial<WorkflowNode["data"]>) => void;
  models?: ModelOption[];
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

export function NodeInspector({
  node,
  onChange,
  models,
  collapsed = false,
  onToggleCollapse,
}: Props) {
  if (collapsed) {
    return (
      <aside className="flex w-11 shrink-0 flex-col items-center border-l border-slate-200 bg-white py-3">
        <button
          type="button"
          onClick={onToggleCollapse}
          title="Show node inspector"
          className="rounded-md p-1.5 text-slate-500 hover:bg-slate-50 hover:text-slate-800 hover:shadow-sm transition-colors"
        >
          <CollapseIcon direction="left" />
        </button>
        <span
          className="mt-6 text-[9px] font-semibold uppercase tracking-widest text-slate-400"
          style={{ writingMode: "vertical-rl", textOrientation: "mixed" }}
        >
          Inspector
        </span>
      </aside>
    );
  }

  if (!node) {
    return (
      <aside className="relative flex w-72 shrink-0 flex-col border-l border-slate-200/80 bg-gradient-to-b from-white to-slate-50/80 transition-[width] duration-200">
        <button
          type="button"
          onClick={onToggleCollapse}
          title="Hide node inspector"
          className="absolute left-2 top-2 z-10 rounded-md p-1 text-slate-400 hover:bg-slate-50 hover:text-slate-700 hover:shadow-sm transition-colors"
        >
          <CollapseIcon direction="right" />
        </button>
        <div className="border-b border-slate-200 px-3 py-2.5 pl-10 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Node Inspector
        </div>
        <div className="p-6 text-center text-sm text-slate-400">
          <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
            </svg>
          </div>
          Select a node to inspect
        </div>
      </aside>
    );
  }

  const d = node.data;
  const showAgent = d.nodeType === "agent" || d.nodeType === "validator";
  const showCommand = d.nodeType === "command";
  const showInput = d.nodeType === "input";

  return (
    <aside className="relative flex w-72 shrink-0 flex-col border-l border-slate-200 bg-white transition-[width] duration-200">
      <button
        type="button"
        onClick={onToggleCollapse}
        title="Hide node inspector"
        className="absolute left-2 top-2 z-10 rounded-md p-1 text-slate-400 hover:bg-slate-50 hover:text-slate-700 hover:shadow-sm transition-colors"
      >
        <CollapseIcon direction="right" />
      </button>
      <div className="border-b border-slate-200 px-3 py-2.5 pl-10">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Node Inspector
        </div>
        <div className="mt-1 text-sm font-semibold text-slate-900">{d.label}</div>
      </div>
      <div className="flex-1 space-y-3 overflow-auto p-3 text-sm">
        <Field label="Name">
          <input
            className={inputClassName}
            value={d.label}
            onChange={(e) => onChange(node.id, { label: e.target.value })}
          />
        </Field>

        {showInput && (
          <>
            <Field label="Objective">
              <textarea
                className={`min-h-[88px] ${inputClassName}`}
                value={d.objective || ""}
                onChange={(e) => onChange(node.id, { objective: e.target.value })}
              />
            </Field>
            <Field label="Constraints">
              <textarea
                className={`min-h-[72px] ${inputClassName}`}
                value={d.constraints || ""}
                onChange={(e) =>
                  onChange(node.id, { constraints: e.target.value })
                }
              />
            </Field>
            <Field label="Target codebase path">
              <input
                className={`${inputClassName} font-mono`}
                placeholder="demo-repo or /absolute/path/to/your/project"
                value={d.targetRepo || ""}
                onChange={(e) =>
                  onChange(node.id, { targetRepo: e.target.value })
                }
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Relative to repo root, or absolute path on your machine.
              </p>
            </Field>
            <Field label="Main target file">
              <input
                className={`${inputClassName} font-mono`}
                placeholder="src/app.js"
                value={d.mainTargetFile || d.targetFiles?.[0] || ""}
                onChange={(e) =>
                  onChange(node.id, {
                    mainTargetFile: e.target.value.trim(),
                    targetFiles: e.target.value.trim()
                      ? [e.target.value.trim()]
                      : [],
                  })
                }
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Primary file the agent should focus on. If it edits other files,
                you will be asked to approve those changes with a reason.
              </p>
            </Field>
            <Field label="Validate command">
              <input
                className={`${inputClassName} font-mono`}
                placeholder="npm test"
                value={d.validateCommand || ""}
                onChange={(e) =>
                  onChange(node.id, { validateCommand: e.target.value })
                }
              />
            </Field>
          </>
        )}

        {showAgent && (
          <>
            <Field label="Instructions">
              <textarea
                className={`min-h-[96px] ${inputClassName}`}
                value={d.instructions || ""}
                onChange={(e) =>
                  onChange(node.id, { instructions: e.target.value })
                }
              />
            </Field>
            <Field label="Model">
              {models && models.length > 0 ? (
                <select
                  className={`${inputClassName} bg-white`}
                  value={d.model || ""}
                  onChange={(e) => onChange(node.id, { model: e.target.value })}
                >
                  <option value="">(None / Default)</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label} {!m.available ? " (missing key)" : ""}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  className={inputClassName}
                  value={d.model || ""}
                  onChange={(e) => onChange(node.id, { model: e.target.value })}
                />
              )}
            </Field>
            {d.tools && (
              <Field label="Tools">
                <div className="flex flex-wrap gap-1">
                  {d.tools.map((t) => (
                    <span
                      key={t}
                      className="rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 ring-1 ring-indigo-100"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </Field>
            )}
            <div className="grid grid-cols-2 gap-2">
              <Field label="Max retries">
                <input
                  type="number"
                  className={inputClassName}
                  value={d.maxRetries ?? 2}
                  onChange={(e) =>
                    onChange(node.id, { maxRetries: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Timeout (s)">
                <input
                  type="number"
                  className={inputClassName}
                  value={d.timeout ?? 300}
                  onChange={(e) =>
                    onChange(node.id, { timeout: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
          </>
        )}

        {showCommand && (
          <Field label="Command">
            <input
              className={`${inputClassName} font-mono`}
              value={d.command || ""}
              onChange={(e) => onChange(node.id, { command: e.target.value })}
            />
          </Field>
        )}

        {d.nodeType === "validator" && d.fileChecks && (
          <Field label="File checks">
            <div className="text-[12px] text-slate-600">
              {d.fileChecks.join(", ")}
            </div>
          </Field>
        )}

        <div className="rounded-xl border border-slate-200/80 bg-white p-2.5 text-[11px] text-slate-500 shadow-sm">
          Type: <span className="font-medium text-slate-700">{d.nodeType}</span>
          {d.role ? (
            <>
              {" "}
              · Role: <span className="font-medium text-slate-700">{d.role}</span>
            </>
          ) : null}
        </div>
      </div>
    </aside>
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
      <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </div>
      {children}
    </label>
  );
}

