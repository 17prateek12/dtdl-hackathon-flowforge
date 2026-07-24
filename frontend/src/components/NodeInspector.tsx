"use client";

import type { WorkflowNode } from "@/lib/types";

interface Props {
  node: WorkflowNode | null;
  onChange: (nodeId: string, patch: Partial<WorkflowNode["data"]>) => void;
}

export function NodeInspector({ node, onChange }: Props) {
  if (!node) {
    return (
      <aside className="flex w-72 shrink-0 flex-col border-l border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Node Inspector
        </div>
        <div className="p-4 text-sm text-slate-400">Select a node to inspect</div>
      </aside>
    );
  }

  const d = node.data;
  const showAgent = d.nodeType === "agent" || d.nodeType === "validator";
  const showCommand = d.nodeType === "command";
  const showInput = d.nodeType === "input";

  return (
    <aside className="flex w-72 shrink-0 flex-col border-l border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-3 py-2.5">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Node Inspector
        </div>
        <div className="mt-1 text-sm font-semibold text-slate-900">{d.label}</div>
      </div>
      <div className="flex-1 space-y-3 overflow-auto p-3 text-sm">
        <Field label="Name">
          <input
            className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
            value={d.label}
            onChange={(e) => onChange(node.id, { label: e.target.value })}
          />
        </Field>

        {showInput && (
          <>
            <Field label="Objective">
              <textarea
                className="min-h-[88px] w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
                value={d.objective || ""}
                onChange={(e) => onChange(node.id, { objective: e.target.value })}
              />
            </Field>
            <Field label="Constraints">
              <textarea
                className="min-h-[72px] w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
                value={d.constraints || ""}
                onChange={(e) =>
                  onChange(node.id, { constraints: e.target.value })
                }
              />
            </Field>
            <Field label="Target codebase path">
              <input
                className="w-full rounded-md border border-slate-200 px-2 py-1.5 font-mono text-sm"
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
                className="w-full rounded-md border border-slate-200 px-2 py-1.5 font-mono text-sm"
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
                className="w-full rounded-md border border-slate-200 px-2 py-1.5 font-mono text-sm"
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
                className="min-h-[96px] w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
                value={d.instructions || ""}
                onChange={(e) =>
                  onChange(node.id, { instructions: e.target.value })
                }
              />
            </Field>
            <Field label="Model">
              <input
                className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
                value={d.model || ""}
                onChange={(e) => onChange(node.id, { model: e.target.value })}
              />
            </Field>
            {d.tools && (
              <Field label="Tools">
                <div className="flex flex-wrap gap-1">
                  {d.tools.map((t) => (
                    <span
                      key={t}
                      className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-700"
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
                  className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
                  value={d.maxRetries ?? 2}
                  onChange={(e) =>
                    onChange(node.id, { maxRetries: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Timeout (s)">
                <input
                  type="number"
                  className="w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
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
              className="w-full rounded-md border border-slate-200 px-2 py-1.5 font-mono text-sm"
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

        <div className="rounded-lg bg-slate-50 p-2 text-[11px] text-slate-500">
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
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      {children}
    </label>
  );
}
