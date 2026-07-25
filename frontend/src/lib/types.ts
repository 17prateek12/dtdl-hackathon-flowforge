export type NodeType =
  | "agent"
  | "command"
  | "validator"
  | "decision"
  | "humanGate"
  | "success"
  | "stop";

export type NodeStatus =
  | "idle"
  | "running"
  | "completed"
  | "failed"
  | "waiting"
  | "skipped";

export type AgentRole =
  | "successCriteria"
  | "planning"
  | "execution"
  | "validation";

export type RunStatus =
  | "idle"
  | "running"
  | "waiting_for_human"
  | "succeeded"
  | "stopped"
  | "failed";

export interface WorkflowNodeConfig {
  label: string;
  description?: string;
  nodeType: NodeType;
  role?: AgentRole;
  instructions?: string;
  model?: string;
  tools?: string[];
  maxRetries?: number;
  timeout?: number;
  command?: string;
  fileChecks?: string[];
  objective?: string;
  constraints?: string;
  targetRepo?: string;
  mainTargetFile?: string;
  targetFiles?: string[];
  validateCommand?: string;
}

export interface WorkflowNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: WorkflowNodeConfig;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
  label?: string;
  style?: Record<string, string | number>;
  animated?: boolean;
}

export interface Workflow {
  id: string;
  name: string;
  maxAttempts: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface ConsoleEvent {
  id: string;
  ts: string;
  level: "info" | "success" | "warn" | "error";
  nodeId?: string;
  message: string;
}

export interface FileChange {
  path: string;
  action: "created" | "modified" | "deleted";
  linesAdded?: number;
  linesRemoved?: number;
}

export interface NodeExecutionReceipt {
  nodeId: string;
  status: NodeStatus;
  input?: string;
  output?: string;
  evidence?: string;
  commands?: string[];
  filesChanged?: FileChange[];
  retryReason?: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface PendingHumanGate {
  nodeId: string;
  kind: "criteria" | "final" | "extra_files" | "plan";
  title: string;
  summary: string;
  editableText?: string;
  extraFiles?: string[];
}

export interface RunRecord {
  id: string;
  workflowId: string;
  status: RunStatus;
  attempt: number;
  maxAttempts: number;
  currentNodeId?: string;
  nodeStatuses: Record<string, NodeStatus>;
  receipts: Record<string, NodeExecutionReceipt>;
  events: ConsoleEvent[];
  filesChanged: FileChange[];
  pendingGate?: PendingHumanGate;
  objective: string;
  constraints: string;
  targetRepo: string;
  mainTargetFile: string;
  targetFiles: string[];
  approvedExtraFiles?: string[];
  validateCommand: string;
  criteria: string[];
  plan: string;
  validationEvidence?: string;
  lastError?: string;
  startedAt: string;
  updatedAt: string;
  finishedAt?: string;
  baselineCommit?: string;
}

export interface HumanGateDecision {
  action: "approve" | "reject" | "edit";
  editedText?: string;
  feedback?: string;
}
